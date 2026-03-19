"""
Assets Mode — Vehicle asset management, onboarding wizard, browser, detail view.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timezone
from PIL import Image, ImageTk, ImageDraw
import customtkinter as ctk

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

VEHICLES_DIR = os.path.normpath(os.path.join(_BASE_DIR, 'assets', 'vehicles'))

VEHICLE_TYPES = ['Sedan', 'SUV', 'Pickup', 'Van', 'Box Truck', 'Commercial', 'Other']
LIGHTING_CONDITIONS = ['Day Sun', 'Overcast', 'Dusk', 'Night', 'Night IR', 'Rain', 'Snow', 'Fog']
CAMERA_ANGLES = ['Straight', 'Left Offset', 'Right Offset', 'Elevated']
DISTANCES = ['Close', 'Medium', 'Far']

THUMB_W, THUMB_H = 200, 133
CANVAS_W, CANVAS_H = 900, 600


class AssetsMode(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent, fg_color='#0d0d14')
        self.state = state
        self.app = app
        self._thumbnails: dict[int, ImageTk.PhotoImage] = {}
        self._view = 'browser'  # 'browser', 'onboarding', 'detail'

        # Check if we need to onboard immediately
        if self.state.unregistered_assets:
            self._show_onboarding(self.state.unregistered_assets[0])
        else:
            self._show_browser()

    # ── Browser View ──────────────────────────────────────────────

    def _show_browser(self):
        self._clear()
        self._view = 'browser'

        # Top bar: title + add button
        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text="Vehicle Assets", font=('Segoe UI', 16, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="+ Import Vehicle", font=('Segoe UI', 10),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#264d80',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._import_vehicle).pack(side=tk.RIGHT)

        # Filter bar
        filter_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        filter_frame.pack(fill=tk.X, padx=16, pady=(4, 8))

        self._filter_type = self._add_filter_dropdown(filter_frame, "Type", ['All'] + VEHICLE_TYPES)
        self._filter_lighting = self._add_filter_dropdown(filter_frame, "Lighting", ['All'] + LIGHTING_CONDITIONS)
        self._filter_angle = self._add_filter_dropdown(filter_frame, "Angle", ['All'] + CAMERA_ANGLES)
        self._filter_distance = self._add_filter_dropdown(filter_frame, "Distance", ['All'] + DISTANCES)

        ctk.CTkLabel(filter_frame, text="Search:", text_color='#e0e0e8', fg_color="transparent",
                     font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(12, 4))
        self._filter_search = tk.StringVar()
        self._filter_search.trace_add('write', lambda *_: self._refresh_grid())
        ctk.CTkEntry(filter_frame, textvariable=self._filter_search, width=160,
                     fg_color='#242438', text_color='#e0e0e8', border_color='#2d2d44',
                     font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # Scrollable grid
        grid_container = ctk.CTkFrame(self, fg_color='#0d0d14')
        grid_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        canvas = tk.Canvas(grid_container, bg='#0d0d14', highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(grid_container, orientation='vertical', command=canvas.yview)
        self._grid_frame = ctk.CTkFrame(canvas, fg_color='#0d0d14')

        self._grid_frame.bind('<Configure>',
                              lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self._grid_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel
        canvas.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>',
                    lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), 'units')))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))

        self._browser_canvas = canvas
        self._refresh_grid()

    def _add_filter_dropdown(self, parent, label, values):
        ctk.CTkLabel(parent, text=f"{label}:", text_color='#e0e0e8', fg_color="transparent",
                     font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(8, 2))
        var = tk.StringVar(value='All')
        combo = ctk.CTkComboBox(parent, variable=var, values=values,
                                state='readonly', width=120,
                                fg_color='#242438', text_color='#e0e0e8',
                                border_color='#2d2d44', button_color='#2d2d44',
                                button_hover_color='#3d3d5c',
                                dropdown_fg_color='#242438', dropdown_text_color='#e0e0e8',
                                dropdown_hover_color='#2d2d44')
        combo.pack(side=tk.LEFT)
        combo.configure(command=lambda _: self._refresh_grid())
        return var

    def _get_filtered_assets(self) -> list[dict]:
        assets = list(self.state.asset_cache.values())
        ft = self._filter_type.get()
        fl = self._filter_lighting.get()
        fa = self._filter_angle.get()
        fd = self._filter_distance.get()
        fs = self._filter_search.get().lower().strip()

        def _norm(val):
            return val.lower().replace(' ', '_') if val else ''

        filtered = []
        for a in assets:
            if ft != 'All' and _norm(a.get('vehicle_type', '')) != _norm(ft):
                continue
            if fl != 'All' and _norm(a.get('lighting', '')) != _norm(fl):
                continue
            if fa != 'All' and _norm(a.get('angle', '')) != _norm(fa):
                continue
            if fd != 'All' and _norm(a.get('distance', '')) != _norm(fd):
                continue
            if fs:
                searchable = ' '.join([
                    a.get('make', ''), a.get('model', ''), a.get('color', ''),
                    a.get('tags', ''), a.get('filename', ''),
                ]).lower()
                if fs not in searchable:
                    continue
            filtered.append(a)
        return filtered

    def _refresh_grid(self):
        for widget in self._grid_frame.winfo_children():
            widget.destroy()
        self._thumbnails.clear()

        assets = self._get_filtered_assets()

        if not assets:
            ctk.CTkLabel(self._grid_frame, text="No registered assets found.\nImport vehicle photos to get started.",
                         font=('Segoe UI', 12), text_color='#555570', fg_color="transparent",
                         justify=tk.CENTER).grid(row=0, column=0, padx=40, pady=60)
            return

        cols = max(1, self._browser_canvas.winfo_width() // 230) if self._browser_canvas.winfo_width() > 100 else 4
        for i, asset in enumerate(assets):
            row, col = divmod(i, cols)
            card = self._build_asset_card(self._grid_frame, asset)
            card.grid(row=row, column=col, padx=8, pady=8, sticky='n')

    def _build_asset_card(self, parent, asset) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color='#242438', corner_radius=8,
                            border_color='#2d2d44', border_width=1)
        card.configure(cursor='hand2')

        # Thumbnail
        thumb = self._get_thumbnail(asset)
        img_label = ctk.CTkLabel(card, image=thumb, text="", fg_color="transparent")
        img_label.image = thumb
        img_label.pack(padx=4, pady=(4, 0))

        # Info
        make_model = f"{asset.get('make', '')} {asset.get('model', '')}".strip() or asset['filename']
        ctk.CTkLabel(card, text=make_model, font=('Segoe UI', 9, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent", wraplength=190).pack(pady=(2, 0))

        # Badges
        badge_frame = ctk.CTkFrame(card, fg_color='#242438')
        badge_frame.pack(pady=(2, 4))

        vtype = asset.get('vehicle_type', '')
        if vtype:
            ctk.CTkLabel(badge_frame, text=vtype, font=('Segoe UI', 7),
                         text_color='#ffffff', fg_color='#1e3a5f',
                         corner_radius=4).pack(side=tk.LEFT, padx=1)

        lighting = asset.get('lighting', '').replace('_', ' ').title()
        if lighting:
            ctk.CTkLabel(badge_frame, text=lighting, font=('Segoe UI', 7),
                         text_color='#e0e0e8', fg_color='#2d2d44',
                         corner_radius=4).pack(side=tk.LEFT, padx=1)

        # Click binding
        aid = asset['id']
        for widget in [card, img_label]:
            widget.bind('<Button-1>', lambda e, a=aid: self._show_detail(a))

        return card

    def _get_thumbnail(self, asset) -> ImageTk.PhotoImage:
        aid = asset['id']
        if aid in self._thumbnails:
            return self._thumbnails[aid]

        path = os.path.join(VEHICLES_DIR, asset['filename'])
        try:
            img = Image.open(path)
            img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
            # Pad to exact size
            padded = Image.new('RGBA', (THUMB_W, THUMB_H), (36, 36, 56, 255))
            x = (THUMB_W - img.width) // 2
            y = (THUMB_H - img.height) // 2
            padded.paste(img, (x, y))
            photo = ImageTk.PhotoImage(padded)
        except Exception:
            # Placeholder
            padded = Image.new('RGBA', (THUMB_W, THUMB_H), (45, 45, 68, 255))
            photo = ImageTk.PhotoImage(padded)

        self._thumbnails[aid] = photo
        return photo

    def _import_vehicle(self):
        paths = filedialog.askopenfilenames(
            title="Select Vehicle Images",
            filetypes=[("PNG Images", "*.png"), ("All Files", "*.*")],
        )
        if not paths:
            return

        import shutil
        for path in paths:
            fname = os.path.basename(path)
            dest = os.path.join(VEHICLES_DIR, fname)
            if not os.path.exists(dest):
                shutil.copy2(path, dest)
            if fname not in self.state.unregistered_assets:
                # Check if already registered
                registered = {a['filename'] for a in self.state.asset_cache.values()}
                if fname not in registered:
                    self.state.unregistered_assets.append(fname)

        self.app._update_unreg_indicator()
        if self.state.unregistered_assets:
            self._show_onboarding(self.state.unregistered_assets[0])

    # ── Onboarding Wizard ─────────────────────────────────────────

    def _show_onboarding(self, filename: str):
        self._clear()
        self._view = 'onboarding'
        self._onboard_filename = filename
        self._onboard_corners: list[list[float]] = []
        self._corner_dots = []

        # Zoom/pan state
        self._zoom_level = 1.0
        self._pan_x = 0.0  # pan offset in image-normalized coords
        self._pan_y = 0.0
        self._drag_start = None  # for middle-click drag panning

        # Top bar
        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text=f"Onboard: {filename}", font=('Segoe UI', 14, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="Skip / Back to Browser", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d5c',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._skip_onboarding).pack(side=tk.RIGHT)

        # Instructions
        self._instruction_var = tk.StringVar(
            value="Left-click: place corner  |  Right-click: undo  |  Scroll: zoom  |  Middle-drag: pan"
        )
        ctk.CTkLabel(self, textvariable=self._instruction_var, font=('Segoe UI', 9),
                     text_color='#8888a0', fg_color="transparent").pack(pady=(2, 2))

        # Buttons ABOVE the canvas
        btn_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        btn_frame.pack(pady=(0, 4))

        self._undo_btn = ctk.CTkButton(btn_frame, text="Undo Last Point",
                                       font=('Segoe UI', 10),
                                       text_color='#e0e0e8', fg_color='#2d2d44',
                                       hover_color='#3d3d5c', border_width=0,
                                       corner_radius=8, cursor='hand2',
                                       command=self._undo_last_corner, state="disabled")
        self._undo_btn.pack(side=tk.LEFT, padx=8)

        self._redo_btn = ctk.CTkButton(btn_frame, text="Reset All",
                                       font=('Segoe UI', 10),
                                       text_color='#ffffff', fg_color='#dc2626',
                                       hover_color='#b91c1c', border_width=0,
                                       corner_radius=8, cursor='hand2',
                                       command=self._redo_corners, state="disabled")
        self._redo_btn.pack(side=tk.LEFT, padx=8)

        self._confirm_btn = ctk.CTkButton(btn_frame, text="Confirm Corners",
                                          font=('Segoe UI', 10, 'bold'),
                                          text_color='#ffffff', fg_color='#1e3a5f',
                                          hover_color='#264d80', border_width=0,
                                          corner_radius=8, cursor='hand2',
                                          command=self._confirm_corners, state="disabled")
        self._confirm_btn.pack(side=tk.LEFT, padx=8)

        self._zoom_label = ctk.CTkLabel(btn_frame, text="1.0x", font=('Segoe UI', 9),
                                        text_color='#555570', fg_color="transparent", width=50)
        self._zoom_label.pack(side=tk.LEFT, padx=(16, 0))

        ctk.CTkButton(btn_frame, text="Reset View", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d5c',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._reset_view).pack(side=tk.LEFT, padx=4)

        # Canvas (stays as tk.Canvas, wrapped in CTkFrame)
        canvas_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        self._ob_canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H,
                                    bg='#0d0d14', highlightthickness=1,
                                    highlightbackground='#2d2d44')
        self._ob_canvas.pack(expand=True)

        # Load and display image
        path = os.path.join(VEHICLES_DIR, filename)
        try:
            self._onboard_pil = Image.open(path).convert('RGBA')
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image: {e}")
            self._show_browser()
            return

        # Base scale to fit image in canvas
        self._base_scale = min(CANVAS_W / self._onboard_pil.width,
                               CANVAS_H / self._onboard_pil.height)

        self._redraw_canvas()

        # Bindings
        self._ob_canvas.bind('<Button-1>', self._on_canvas_click)
        self._ob_canvas.bind('<Button-3>', lambda e: self._undo_last_corner())
        self._ob_canvas.bind('<MouseWheel>', self._on_scroll_zoom)
        self._ob_canvas.bind('<Button-2>', self._on_pan_start)
        self._ob_canvas.bind('<B2-Motion>', self._on_pan_drag)
        self._ob_canvas.bind('<ButtonRelease-2>', self._on_pan_end)
        # Also support Shift+left-drag for pan (no middle button on some mice)
        self._ob_canvas.bind('<Shift-Button-1>', self._on_pan_start)
        self._ob_canvas.bind('<Shift-B1-Motion>', self._on_pan_drag)
        self._ob_canvas.bind('<Shift-ButtonRelease-1>', self._on_pan_end)

    def _canvas_to_normalized(self, cx, cy):
        """Convert canvas pixel coords to normalized image coords (0-1), accounting for zoom/pan."""
        scale = self._base_scale * self._zoom_level
        iw, ih = self._onboard_pil.width, self._onboard_pil.height
        disp_w = iw * scale
        disp_h = ih * scale
        ox = (CANVAS_W - disp_w) / 2 + self._pan_x * scale
        oy = (CANVAS_H - disp_h) / 2 + self._pan_y * scale
        img_x = (cx - ox) / disp_w
        img_y = (cy - oy) / disp_h
        return img_x, img_y

    def _normalized_to_canvas(self, nx, ny):
        """Convert normalized image coords (0-1) to canvas pixel coords."""
        scale = self._base_scale * self._zoom_level
        iw, ih = self._onboard_pil.width, self._onboard_pil.height
        disp_w = iw * scale
        disp_h = ih * scale
        ox = (CANVAS_W - disp_w) / 2 + self._pan_x * scale
        oy = (CANVAS_H - disp_h) / 2 + self._pan_y * scale
        return ox + nx * disp_w, oy + ny * disp_h

    def _on_scroll_zoom(self, event):
        """Zoom in/out with scroll wheel, centered on mouse position."""
        old_zoom = self._zoom_level
        if event.delta > 0:
            self._zoom_level = min(self._zoom_level * 1.2, 10.0)
        else:
            self._zoom_level = max(self._zoom_level / 1.2, 0.5)

        # Adjust pan so zoom is centered on mouse position
        if old_zoom != self._zoom_level:
            # Get normalized coord under mouse at old zoom
            mx, my = self._canvas_to_normalized(event.x, event.y)
            # After zoom change, shift pan so that same coord stays under mouse
            scale = self._base_scale * self._zoom_level
            iw, ih = self._onboard_pil.width, self._onboard_pil.height
            disp_w = iw * scale
            disp_h = ih * scale
            ox_target = event.x - mx * disp_w
            oy_target = event.y - my * disp_h
            ox_center = (CANVAS_W - disp_w) / 2
            oy_center = (CANVAS_H - disp_h) / 2
            self._pan_x = (ox_target - ox_center) / scale
            self._pan_y = (oy_target - oy_center) / scale

        self._zoom_label.configure(text=f"{self._zoom_level:.1f}x")
        self._redraw_canvas()

    def _on_pan_start(self, event):
        self._drag_start = (event.x, event.y, self._pan_x, self._pan_y)

    def _on_pan_drag(self, event):
        if not self._drag_start:
            return
        sx, sy, spx, spy = self._drag_start
        scale = self._base_scale * self._zoom_level
        self._pan_x = spx + (event.x - sx) / scale
        self._pan_y = spy + (event.y - sy) / scale
        self._redraw_canvas()

    def _on_pan_end(self, event):
        self._drag_start = None

    def _reset_view(self):
        """Reset zoom and pan to default."""
        self._zoom_level = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom_label.configure(text="1.0x")
        self._redraw_canvas()

    def _redraw_canvas(self):
        """Redraw the image and all corner markers at current zoom/pan."""
        self._ob_canvas.delete('all')

        scale = self._base_scale * self._zoom_level
        iw, ih = self._onboard_pil.width, self._onboard_pil.height
        disp_w = int(iw * scale)
        disp_h = int(ih * scale)

        resized = self._onboard_pil.resize((max(1, disp_w), max(1, disp_h)), Image.LANCZOS)
        self._ob_photo = ImageTk.PhotoImage(resized)

        ox = (CANVAS_W - disp_w) / 2 + self._pan_x * scale
        oy = (CANVAS_H - disp_h) / 2 + self._pan_y * scale
        self._ob_canvas.create_image(ox, oy, anchor='nw', image=self._ob_photo, tags='vehicle')

        # Redraw corner dots
        self._corner_dots.clear()
        for i, c in enumerate(self._onboard_corners):
            cx, cy = self._normalized_to_canvas(c[0], c[1])
            r = 6
            dot = self._ob_canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                               fill='#dc2626', outline='white', width=1)
            text = self._ob_canvas.create_text(cx, cy, text=str(i + 1),
                                                font=('Segoe UI', 8, 'bold'), fill='white')
            self._corner_dots.append((dot, text))

        # Redraw polygon if 4 corners
        if len(self._onboard_corners) == 4:
            self._draw_corner_polygon()

    def _on_canvas_click(self, event):
        if len(self._onboard_corners) >= 4:
            return

        img_x, img_y = self._canvas_to_normalized(event.x, event.y)

        if not (0.0 <= img_x <= 1.0 and 0.0 <= img_y <= 1.0):
            return

        self._onboard_corners.append([img_x, img_y])
        idx = len(self._onboard_corners)

        # Redraw to show the new dot
        self._redraw_canvas()

        # Enable undo/reset now that we have at least one point
        self._undo_btn.configure(state="normal")
        self._redo_btn.configure(state="normal")

        labels = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
        if idx < 4:
            self._instruction_var.set(f"Corner {idx}/4 placed. Next: {labels[idx]}  |  Right-click: undo  |  Scroll: zoom")
        else:
            self._instruction_var.set("4 corners placed — review the outline, then Confirm or Reset")
            self._render_warp_preview()
            self._confirm_btn.configure(state="normal")

    def _draw_corner_polygon(self):
        """Draw green polygon connecting the 4 corners."""
        points = []
        for c in self._onboard_corners:
            cx, cy = self._normalized_to_canvas(c[0], c[1])
            points.extend([cx, cy])
        points.extend(points[:2])
        self._ob_canvas.create_line(*points, fill='#1e3a5f', width=2, tags='polygon')

    def _render_warp_preview(self):
        """Warp a sample plate into the selected region as a preview."""
        try:
            from engine.plate_renderer import PlateRenderer
            from engine.compositor import Compositor

            renderer = PlateRenderer()
            states = renderer.available_states()
            if not states:
                return

            plate_img = renderer.render(states[0], 'ABC-1234')
            comp = Compositor()
            preview = comp.composite(self._onboard_pil, plate_img, self._onboard_corners)

            disp_w = int(preview.width * self._display_scale)
            disp_h = int(preview.height * self._display_scale)
            resized = preview.resize((disp_w, disp_h), Image.LANCZOS)
            self._ob_preview_photo = ImageTk.PhotoImage(resized)
            self._ob_canvas.delete('vehicle')
            self._ob_canvas.create_image(self._display_offset_x, self._display_offset_y,
                                         anchor='nw', image=self._ob_preview_photo, tags='vehicle')
        except Exception as e:
            print(f"[Onboarding] Preview render failed: {e}")

    def _undo_last_corner(self):
        """Remove the last placed corner point."""
        if not self._onboard_corners:
            return

        self._onboard_corners.pop()
        self._confirm_btn.configure(state="disabled")
        self._redraw_canvas()

        if not self._onboard_corners:
            self._undo_btn.configure(state="disabled")
            self._redo_btn.configure(state="disabled")
            self._instruction_var.set("Left-click: place corner  |  Right-click: undo  |  Scroll: zoom  |  Middle-drag: pan")
        else:
            labels = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
            idx = len(self._onboard_corners)
            self._instruction_var.set(f"Corner {idx}/4 placed. Next: {labels[idx]}  |  Right-click: undo  |  Scroll: zoom")

    def _redo_corners(self):
        """Reset all corners and start over."""
        self._onboard_corners.clear()
        self._corner_dots.clear()
        self._confirm_btn.configure(state="disabled")
        self._undo_btn.configure(state="disabled")
        self._redo_btn.configure(state="disabled")
        self._instruction_var.set("Left-click: place corner  |  Right-click: undo  |  Scroll: zoom  |  Middle-drag: pan")
        self._redraw_canvas()

    def _confirm_corners(self):
        """Corners confirmed — show metadata form."""
        self._show_metadata_form()

    def _skip_onboarding(self):
        """Skip this asset's onboarding and go back to browser."""
        self._show_browser()

    # ── Metadata Form ─────────────────────────────────────────────

    def _show_metadata_form(self):
        self._clear()

        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))
        ctk.CTkLabel(top, text=f"Register: {self._onboard_filename}",
                     font=('Segoe UI', 14, 'bold'), text_color='#e0e0e8',
                     fg_color="transparent").pack(side=tk.LEFT)

        form = ctk.CTkFrame(self, fg_color='#0d0d14')
        form.pack(pady=16, padx=40)

        row = 0
        self._meta_fields = {}

        def add_dropdown(label, values, default=None):
            nonlocal row
            ctk.CTkLabel(form, text=label, font=('Segoe UI', 10), text_color='#e0e0e8',
                         fg_color="transparent", anchor='w').grid(row=row, column=0, sticky='w', pady=4, padx=(0, 12))
            var = tk.StringVar(value=default or values[0])
            ctk.CTkComboBox(form, variable=var, values=values, state='readonly',
                            width=200,
                            fg_color='#242438', text_color='#e0e0e8',
                            border_color='#2d2d44', button_color='#2d2d44',
                            button_hover_color='#3d3d5c',
                            dropdown_fg_color='#242438', dropdown_text_color='#e0e0e8',
                            dropdown_hover_color='#2d2d44').grid(row=row, column=1, sticky='w', pady=4)
            self._meta_fields[label] = var
            row += 1

        def add_entry(label, default=''):
            nonlocal row
            ctk.CTkLabel(form, text=label, font=('Segoe UI', 10), text_color='#e0e0e8',
                         fg_color="transparent", anchor='w').grid(row=row, column=0, sticky='w', pady=4, padx=(0, 12))
            var = tk.StringVar(value=default)
            ctk.CTkEntry(form, textvariable=var, width=200, fg_color='#242438', text_color='#e0e0e8',
                         border_color='#2d2d44',
                         font=('Segoe UI', 10)).grid(row=row, column=1, sticky='w', pady=4)
            self._meta_fields[label] = var
            row += 1

        add_dropdown('Vehicle Type', VEHICLE_TYPES)
        add_entry('Make')
        add_entry('Model')
        add_entry('Color')
        add_dropdown('Lighting', LIGHTING_CONDITIONS, 'Day Sun')
        add_dropdown('Angle', CAMERA_ANGLES, 'Straight')
        add_dropdown('Distance', DISTANCES, 'Medium')
        add_entry('Tags (comma separated)')

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        btn_frame.pack(pady=16)

        ctk.CTkButton(btn_frame, text="Save Asset", font=('Segoe UI', 11, 'bold'),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#264d80',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._save_asset).pack(side=tk.LEFT, padx=8)

        ctk.CTkButton(btn_frame, text="Cancel", font=('Segoe UI', 10),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d5c',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._show_browser).pack(side=tk.LEFT, padx=8)

    def _save_asset(self):
        """Write asset record to database."""
        def _norm(val):
            return val.lower().replace(' ', '_')

        filename = self._onboard_filename
        corners_json = json.dumps(self._onboard_corners)
        now = datetime.now(timezone.utc).isoformat()

        cur = self.state.db_conn.cursor()
        cur.execute('''
            INSERT INTO assets (filename, vehicle_type, make, model, color,
                                lighting, angle, distance, tags, corners, date_added)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            _norm(self._meta_fields['Vehicle Type'].get()),
            self._meta_fields['Make'].get().strip(),
            self._meta_fields['Model'].get().strip(),
            self._meta_fields['Color'].get().strip(),
            _norm(self._meta_fields['Lighting'].get()),
            _norm(self._meta_fields['Angle'].get()),
            _norm(self._meta_fields['Distance'].get()),
            self._meta_fields['Tags (comma separated)'].get().strip(),
            corners_json,
            now,
        ))
        self.state.db_conn.commit()

        # Remove from unregistered list
        if filename in self.state.unregistered_assets:
            self.state.unregistered_assets.remove(filename)

        # Refresh cache
        self.app.refresh_asset_cache()

        # If more unregistered, onboard next; else browser
        if self.state.unregistered_assets:
            self._show_onboarding(self.state.unregistered_assets[0])
        else:
            self._show_browser()

    # ── Detail View ───────────────────────────────────────────────

    def _show_detail(self, asset_id: int):
        self._clear()
        self._view = 'detail'
        asset = self.state.asset_cache.get(asset_id)
        if not asset:
            self._show_browser()
            return

        self._detail_asset_id = asset_id

        # Top bar
        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        ctk.CTkButton(top, text="< Back", font=('Segoe UI', 10),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d5c',
                      border_width=0, corner_radius=8,
                      cursor='hand2', command=self._show_browser).pack(side=tk.LEFT)

        make_model = f"{asset.get('make', '')} {asset.get('model', '')}".strip() or asset['filename']
        ctk.CTkLabel(top, text=make_model, font=('Segoe UI', 14, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT, padx=16)

        # Main content: image left, metadata right
        content = ctk.CTkFrame(self, fg_color='#0d0d14')
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Image with corner overlay
        img_frame = ctk.CTkFrame(content, fg_color='#0d0d14')
        img_frame.pack(side=tk.LEFT, padx=(0, 16))

        path = os.path.join(VEHICLES_DIR, asset['filename'])
        try:
            pil_img = Image.open(path).convert('RGBA')
            # Draw corners
            corners = json.loads(asset['corners']) if isinstance(asset['corners'], str) else asset['corners']
            if corners and len(corners) == 4:
                draw = ImageDraw.Draw(pil_img)
                w, h = pil_img.size
                pts = [(c[0] * w, c[1] * h) for c in corners]
                draw.polygon(pts, outline='#1e3a5f', width=3)
                for i, pt in enumerate(pts):
                    r = 5
                    draw.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                                 fill='#dc2626', outline='white')

            scale = min(600 / pil_img.width, 450 / pil_img.height)
            disp = pil_img.resize((int(pil_img.width * scale), int(pil_img.height * scale)), Image.LANCZOS)
            self._detail_photo = ImageTk.PhotoImage(disp)
            ctk.CTkLabel(img_frame, image=self._detail_photo, text="",
                         fg_color="transparent").pack(padx=4, pady=4)
        except Exception:
            ctk.CTkLabel(img_frame, text="Image not found", text_color='#dc2626',
                         fg_color="transparent", font=('Segoe UI', 12)).pack(padx=40, pady=40)

        # Metadata panel
        meta_frame = ctk.CTkFrame(content, fg_color='#0d0d14')
        meta_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        fields = [
            ('Filename', asset.get('filename', '')),
            ('Vehicle Type', asset.get('vehicle_type', '').replace('_', ' ').title()),
            ('Make', asset.get('make', '')),
            ('Model', asset.get('model', '')),
            ('Color', asset.get('color', '')),
            ('Lighting', asset.get('lighting', '').replace('_', ' ').title()),
            ('Angle', asset.get('angle', '').replace('_', ' ').title()),
            ('Distance', asset.get('distance', '').title()),
            ('Tags', asset.get('tags', '')),
            ('Vault Count', str(asset.get('vault_count', 0))),
            ('Date Added', asset.get('date_added', '')),
        ]

        for label, value in fields:
            row = ctk.CTkFrame(meta_frame, fg_color='#0d0d14')
            row.pack(fill=tk.X, pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=('Segoe UI', 9, 'bold'),
                         text_color='#8888a0', fg_color="transparent", width=112,
                         anchor='w').pack(side=tk.LEFT)
            ctk.CTkLabel(row, text=value, font=('Segoe UI', 9),
                         text_color='#e0e0e8', fg_color="transparent",
                         anchor='w').pack(side=tk.LEFT)

        # Templates referencing this asset
        ref_templates = [t for t in self.state.templates if t.get('vehicle_id') == asset_id]
        if ref_templates:
            ctk.CTkLabel(meta_frame, text=f"\nUsed in {len(ref_templates)} template(s):",
                         font=('Segoe UI', 9, 'bold'), text_color='#1e3a5f',
                         fg_color="transparent", anchor='w').pack(fill=tk.X, pady=(8, 2))
            for t in ref_templates:
                ctk.CTkLabel(meta_frame, text=f"  - {t.get('name', t['id'])}",
                             font=('Segoe UI', 9), text_color='#e0e0e8',
                             fg_color="transparent", anchor='w').pack(fill=tk.X)

        # Action buttons
        btn_frame = ctk.CTkFrame(meta_frame, fg_color='#0d0d14')
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        ctk.CTkButton(btn_frame, text="Edit Metadata", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#264d80',
                      border_width=0, corner_radius=8,
                      cursor='hand2',
                      command=lambda: self._edit_metadata(asset_id)).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(btn_frame, text="Redo Corners", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d5c',
                      border_width=0, corner_radius=8,
                      cursor='hand2',
                      command=lambda: self._redo_asset_corners(asset_id)).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(btn_frame, text="Delete Asset", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#dc2626', hover_color='#b91c1c',
                      border_width=0, corner_radius=8,
                      cursor='hand2',
                      command=lambda: self._delete_asset(asset_id)).pack(side=tk.RIGHT, padx=4)

    def _delete_asset(self, asset_id: int):
        """Delete an asset from the database and optionally remove the file."""
        asset = self.state.asset_cache.get(asset_id)
        if not asset:
            return

        # Check if templates reference this asset
        ref_templates = [t for t in self.state.templates if t.get('vehicle_id') == asset_id]
        msg = f"Delete \"{asset.get('make', '')} {asset.get('model', '')}\" ({asset['filename']})?"
        if ref_templates:
            msg += f"\n\nWarning: {len(ref_templates)} template(s) reference this asset and will break."

        if not messagebox.askyesno("Delete Asset", msg):
            return

        # Ask about the file
        delete_file = messagebox.askyesno("Delete File",
                                          f"Also delete the image file?\n{asset['filename']}")

        # Remove from database
        cur = self.state.db_conn.cursor()
        cur.execute("DELETE FROM assets WHERE id=?", (asset_id,))
        self.state.db_conn.commit()

        # Remove file if requested
        if delete_file:
            file_path = os.path.join(VEHICLES_DIR, asset['filename'])
            if os.path.isfile(file_path):
                os.remove(file_path)

        self.app.refresh_asset_cache()
        self._show_browser()

    def _edit_metadata(self, asset_id: int):
        """Open metadata edit dialog for an existing asset."""
        asset = self.state.asset_cache.get(asset_id)
        if not asset:
            return

        win = ctk.CTkToplevel(self)
        win.title(f"Edit: {asset['filename']}")
        win.geometry("400x450")
        win.configure(fg_color='#0d0d14')
        win.transient(self)
        win.grab_set()

        form = ctk.CTkFrame(win, fg_color='#0d0d14')
        form.pack(pady=16, padx=24, fill=tk.BOTH, expand=True)

        fields = {}
        row = 0

        def add_dd(label, values, current):
            nonlocal row
            ctk.CTkLabel(form, text=label, font=('Segoe UI', 10), text_color='#e0e0e8',
                         fg_color="transparent").grid(row=row, column=0, sticky='w', pady=4)
            var = tk.StringVar(value=current)
            ctk.CTkComboBox(form, variable=var, values=values, state='readonly',
                            width=180,
                            fg_color='#242438', text_color='#e0e0e8',
                            border_color='#2d2d44', button_color='#2d2d44',
                            button_hover_color='#3d3d5c',
                            dropdown_fg_color='#242438', dropdown_text_color='#e0e0e8',
                            dropdown_hover_color='#2d2d44').grid(row=row, column=1, sticky='w', pady=4)
            fields[label] = var
            row += 1

        def add_ent(label, current):
            nonlocal row
            ctk.CTkLabel(form, text=label, font=('Segoe UI', 10), text_color='#e0e0e8',
                         fg_color="transparent").grid(row=row, column=0, sticky='w', pady=4)
            var = tk.StringVar(value=current)
            ctk.CTkEntry(form, textvariable=var, width=180, fg_color='#242438', text_color='#e0e0e8',
                         border_color='#2d2d44').grid(row=row, column=1, sticky='w', pady=4)
            fields[label] = var
            row += 1

        def _display(val, options):
            for o in options:
                if o.lower().replace(' ', '_') == val:
                    return o
            return options[0]

        add_dd('Vehicle Type', VEHICLE_TYPES, _display(asset.get('vehicle_type', ''), VEHICLE_TYPES))
        add_ent('Make', asset.get('make', ''))
        add_ent('Model', asset.get('model', ''))
        add_ent('Color', asset.get('color', ''))
        add_dd('Lighting', LIGHTING_CONDITIONS, _display(asset.get('lighting', ''), LIGHTING_CONDITIONS))
        add_dd('Angle', CAMERA_ANGLES, _display(asset.get('angle', ''), CAMERA_ANGLES))
        add_dd('Distance', DISTANCES, _display(asset.get('distance', ''), DISTANCES))
        add_ent('Tags', asset.get('tags', ''))

        def save():
            def _norm(val):
                return val.lower().replace(' ', '_')
            cur = self.state.db_conn.cursor()
            cur.execute('''
                UPDATE assets SET vehicle_type=?, make=?, model=?, color=?,
                    lighting=?, angle=?, distance=?, tags=?
                WHERE id=?
            ''', (
                _norm(fields['Vehicle Type'].get()),
                fields['Make'].get().strip(),
                fields['Model'].get().strip(),
                fields['Color'].get().strip(),
                _norm(fields['Lighting'].get()),
                _norm(fields['Angle'].get()),
                _norm(fields['Distance'].get()),
                fields['Tags'].get().strip(),
                asset_id,
            ))
            self.state.db_conn.commit()
            self.app.refresh_asset_cache()
            win.destroy()
            self._show_detail(asset_id)

        ctk.CTkButton(win, text="Save", font=('Segoe UI', 10, 'bold'),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#264d80',
                      border_width=0, corner_radius=8,
                      command=save).pack(pady=8)

    def _redo_asset_corners(self, asset_id: int):
        """Re-enter corner mapping for an existing asset."""
        asset = self.state.asset_cache.get(asset_id)
        if not asset:
            return
        self._onboard_filename = asset['filename']
        self._detail_asset_id = asset_id
        self._onboard_corners = []
        self._corner_dots = []
        # Use onboarding flow but save as update instead of insert
        self._show_corner_redo(asset_id)

    def _show_corner_redo(self, asset_id: int):
        """Re-map corners for existing asset — reuses the full onboarding flow with zoom/pan."""
        asset = self.state.asset_cache[asset_id]
        filename = asset['filename']

        # Set up state so _show_onboarding works
        self._redo_asset_id = asset_id

        # Show full onboarding canvas (has zoom/pan/undo)
        self._show_onboarding(filename)

        # Override the confirm button to update instead of insert
        def save_corners():
            if len(self._onboard_corners) != 4:
                messagebox.showwarning("Incomplete", "Please place all 4 corners.")
                return
            corners_json = json.dumps(self._onboard_corners)
            cur = self.state.db_conn.cursor()
            cur.execute("UPDATE assets SET corners=? WHERE id=?", (corners_json, asset_id))
            self.state.db_conn.commit()
            self.app.refresh_asset_cache()
            self._redo_asset_id = None
            self._show_detail(asset_id)

        self._confirm_btn.configure(command=save_corners, text="Save Corners")

    # ── Utilities ─────────────────────────────────────────────────

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()
