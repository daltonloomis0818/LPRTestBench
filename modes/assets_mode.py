"""
Assets Mode — Vehicle asset management, onboarding wizard, browser, detail view.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timezone
from PIL import Image, ImageTk, ImageDraw

ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
VEHICLES_DIR = os.path.normpath(os.path.join(ROOT_DIR, 'assets', 'vehicles'))

VEHICLE_TYPES = ['Sedan', 'SUV', 'Pickup', 'Van', 'Box Truck', 'Commercial', 'Other']
LIGHTING_CONDITIONS = ['Day Sun', 'Overcast', 'Dusk', 'Night', 'Night IR', 'Rain', 'Snow', 'Fog']
CAMERA_ANGLES = ['Straight', 'Left Offset', 'Right Offset', 'Elevated']
DISTANCES = ['Close', 'Medium', 'Far']

THUMB_W, THUMB_H = 200, 133
CANVAS_W, CANVAS_H = 900, 600


class AssetsMode(tk.Frame):
    def __init__(self, parent, state, app):
        super().__init__(parent, bg='#1e1e2e')
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
        top = tk.Frame(self, bg='#1e1e2e')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Label(top, text="Vehicle Assets", font=('Segoe UI', 16, 'bold'),
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)

        tk.Button(top, text="+ Import Vehicle", font=('Segoe UI', 10),
                  fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=12, pady=4,
                  cursor='hand2', command=self._import_vehicle).pack(side=tk.RIGHT)

        # Filter bar
        filter_frame = tk.Frame(self, bg='#1e1e2e')
        filter_frame.pack(fill=tk.X, padx=16, pady=(4, 8))

        self._filter_type = self._add_filter_dropdown(filter_frame, "Type", ['All'] + VEHICLE_TYPES)
        self._filter_lighting = self._add_filter_dropdown(filter_frame, "Lighting", ['All'] + LIGHTING_CONDITIONS)
        self._filter_angle = self._add_filter_dropdown(filter_frame, "Angle", ['All'] + CAMERA_ANGLES)
        self._filter_distance = self._add_filter_dropdown(filter_frame, "Distance", ['All'] + DISTANCES)

        tk.Label(filter_frame, text="Search:", fg='#cdd6f4', bg='#1e1e2e',
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(12, 4))
        self._filter_search = tk.StringVar()
        self._filter_search.trace_add('write', lambda *_: self._refresh_grid())
        tk.Entry(filter_frame, textvariable=self._filter_search, width=20,
                 bg='#313244', fg='#cdd6f4', insertbackground='#cdd6f4',
                 bd=0, font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # Scrollable grid
        grid_container = tk.Frame(self, bg='#1e1e2e')
        grid_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        canvas = tk.Canvas(grid_container, bg='#1e1e2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(grid_container, orient=tk.VERTICAL, command=canvas.yview)
        self._grid_frame = tk.Frame(canvas, bg='#1e1e2e')

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
        tk.Label(parent, text=f"{label}:", fg='#cdd6f4', bg='#1e1e2e',
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(8, 2))
        var = tk.StringVar(value='All')
        combo = ttk.Combobox(parent, textvariable=var, values=values,
                             state='readonly', width=12)
        combo.pack(side=tk.LEFT)
        combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_grid())
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
            tk.Label(self._grid_frame, text="No registered assets found.\nImport vehicle photos to get started.",
                     font=('Segoe UI', 12), fg='#6c7086', bg='#1e1e2e',
                     justify=tk.CENTER).grid(row=0, column=0, padx=40, pady=60)
            return

        cols = max(1, self._browser_canvas.winfo_width() // 230) if self._browser_canvas.winfo_width() > 100 else 4
        for i, asset in enumerate(assets):
            row, col = divmod(i, cols)
            card = self._build_asset_card(self._grid_frame, asset)
            card.grid(row=row, column=col, padx=8, pady=8, sticky='n')

    def _build_asset_card(self, parent, asset) -> tk.Frame:
        card = tk.Frame(parent, bg='#313244', cursor='hand2')
        card.configure(highlightbackground='#45475a', highlightthickness=1)

        # Thumbnail
        thumb = self._get_thumbnail(asset)
        img_label = tk.Label(card, image=thumb, bg='#313244')
        img_label.image = thumb
        img_label.pack(padx=4, pady=(4, 0))

        # Info
        make_model = f"{asset.get('make', '')} {asset.get('model', '')}".strip() or asset['filename']
        tk.Label(card, text=make_model, font=('Segoe UI', 9, 'bold'),
                 fg='#cdd6f4', bg='#313244', wraplength=190).pack(pady=(2, 0))

        # Badges
        badge_frame = tk.Frame(card, bg='#313244')
        badge_frame.pack(pady=(2, 4))

        vtype = asset.get('vehicle_type', '')
        if vtype:
            tk.Label(badge_frame, text=vtype, font=('Segoe UI', 7),
                     fg='#1e1e2e', bg='#89b4fa', padx=4, pady=1).pack(side=tk.LEFT, padx=1)

        lighting = asset.get('lighting', '').replace('_', ' ').title()
        if lighting:
            tk.Label(badge_frame, text=lighting, font=('Segoe UI', 7),
                     fg='#1e1e2e', bg='#f9e2af', padx=4, pady=1).pack(side=tk.LEFT, padx=1)

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
            padded = Image.new('RGBA', (THUMB_W, THUMB_H), (49, 50, 68, 255))
            x = (THUMB_W - img.width) // 2
            y = (THUMB_H - img.height) // 2
            padded.paste(img, (x, y))
            photo = ImageTk.PhotoImage(padded)
        except Exception:
            # Placeholder
            padded = Image.new('RGBA', (THUMB_W, THUMB_H), (69, 71, 90, 255))
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

        # Top bar
        top = tk.Frame(self, bg='#1e1e2e')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Label(top, text=f"Onboard: {filename}", font=('Segoe UI', 14, 'bold'),
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)

        tk.Button(top, text="Skip / Back to Browser", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._skip_onboarding).pack(side=tk.RIGHT)

        # Instructions
        self._instruction_var = tk.StringVar(
            value="Click the 4 corners of the plate region: Top-Left first"
        )
        tk.Label(self, textvariable=self._instruction_var, font=('Segoe UI', 10),
                 fg='#f9e2af', bg='#1e1e2e').pack(pady=(4, 8))

        # Canvas
        canvas_frame = tk.Frame(self, bg='#1e1e2e')
        canvas_frame.pack(expand=True)

        self._ob_canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H,
                                    bg='#181825', highlightthickness=1,
                                    highlightbackground='#45475a')
        self._ob_canvas.pack()

        # Load and display image
        path = os.path.join(VEHICLES_DIR, filename)
        try:
            self._onboard_pil = Image.open(path).convert('RGBA')
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open image: {e}")
            self._show_browser()
            return

        self._display_scale = min(CANVAS_W / self._onboard_pil.width,
                                  CANVAS_H / self._onboard_pil.height)
        disp_w = int(self._onboard_pil.width * self._display_scale)
        disp_h = int(self._onboard_pil.height * self._display_scale)
        self._display_offset_x = (CANVAS_W - disp_w) // 2
        self._display_offset_y = (CANVAS_H - disp_h) // 2

        resized = self._onboard_pil.resize((disp_w, disp_h), Image.LANCZOS)
        self._ob_photo = ImageTk.PhotoImage(resized)
        self._ob_canvas.create_image(self._display_offset_x, self._display_offset_y,
                                     anchor='nw', image=self._ob_photo, tags='vehicle')

        self._ob_canvas.bind('<Button-1>', self._on_canvas_click)

        # Buttons (hidden until 4 corners placed)
        btn_frame = tk.Frame(self, bg='#1e1e2e')
        btn_frame.pack(pady=8)
        self._confirm_btn = tk.Button(btn_frame, text="Confirm Corners",
                                      font=('Segoe UI', 10, 'bold'),
                                      fg='#1e1e2e', bg='#a6e3a1', bd=0,
                                      padx=16, pady=6, cursor='hand2',
                                      command=self._confirm_corners, state=tk.DISABLED)
        self._confirm_btn.pack(side=tk.LEFT, padx=8)

        self._redo_btn = tk.Button(btn_frame, text="Redo",
                                   font=('Segoe UI', 10),
                                   fg='#cdd6f4', bg='#f38ba8', bd=0,
                                   padx=16, pady=6, cursor='hand2',
                                   command=self._redo_corners)
        self._redo_btn.pack(side=tk.LEFT, padx=8)

    def _on_canvas_click(self, event):
        if len(self._onboard_corners) >= 4:
            return

        x, y = event.x, event.y

        # Convert canvas coords to normalized image coords
        img_x = (x - self._display_offset_x) / (self._onboard_pil.width * self._display_scale)
        img_y = (y - self._display_offset_y) / (self._onboard_pil.height * self._display_scale)

        if not (0.0 <= img_x <= 1.0 and 0.0 <= img_y <= 1.0):
            return

        self._onboard_corners.append([img_x, img_y])
        idx = len(self._onboard_corners)

        # Draw numbered red dot
        r = 6
        dot = self._ob_canvas.create_oval(x - r, y - r, x + r, y + r,
                                           fill='#f38ba8', outline='white', width=1)
        text = self._ob_canvas.create_text(x, y, text=str(idx),
                                            font=('Segoe UI', 8, 'bold'), fill='white')
        self._corner_dots.extend([dot, text])

        labels = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
        if idx < 4:
            self._instruction_var.set(f"Click corner {idx + 1}: {labels[idx]}")
        else:
            self._instruction_var.set("4 corners placed — review the green outline")
            self._draw_corner_polygon()
            self._render_warp_preview()
            self._confirm_btn.configure(state=tk.NORMAL)

    def _draw_corner_polygon(self):
        """Draw green polygon connecting the 4 corners."""
        points = []
        for c in self._onboard_corners:
            cx = c[0] * self._onboard_pil.width * self._display_scale + self._display_offset_x
            cy = c[1] * self._onboard_pil.height * self._display_scale + self._display_offset_y
            points.extend([cx, cy])
        # Close the polygon
        points.extend(points[:2])
        self._ob_canvas.create_line(*points, fill='#a6e3a1', width=2, tags='polygon')

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

    def _redo_corners(self):
        self._onboard_corners.clear()
        for item in self._corner_dots:
            self._ob_canvas.delete(item)
        self._corner_dots.clear()
        self._ob_canvas.delete('polygon')
        self._confirm_btn.configure(state=tk.DISABLED)
        self._instruction_var.set("Click the 4 corners of the plate region: Top-Left first")

        # Restore original image
        disp_w = int(self._onboard_pil.width * self._display_scale)
        disp_h = int(self._onboard_pil.height * self._display_scale)
        resized = self._onboard_pil.resize((disp_w, disp_h), Image.LANCZOS)
        self._ob_photo = ImageTk.PhotoImage(resized)
        self._ob_canvas.delete('vehicle')
        self._ob_canvas.create_image(self._display_offset_x, self._display_offset_y,
                                     anchor='nw', image=self._ob_photo, tags='vehicle')

    def _confirm_corners(self):
        """Corners confirmed — show metadata form."""
        self._show_metadata_form()

    def _skip_onboarding(self):
        """Skip this asset's onboarding and go back to browser."""
        self._show_browser()

    # ── Metadata Form ─────────────────────────────────────────────

    def _show_metadata_form(self):
        self._clear()

        top = tk.Frame(self, bg='#1e1e2e')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(top, text=f"Register: {self._onboard_filename}",
                 font=('Segoe UI', 14, 'bold'), fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)

        form = tk.Frame(self, bg='#1e1e2e')
        form.pack(pady=16, padx=40)

        row = 0
        self._meta_fields = {}

        def add_dropdown(label, values, default=None):
            nonlocal row
            tk.Label(form, text=label, font=('Segoe UI', 10), fg='#cdd6f4',
                     bg='#1e1e2e', anchor='w').grid(row=row, column=0, sticky='w', pady=4, padx=(0, 12))
            var = tk.StringVar(value=default or values[0])
            ttk.Combobox(form, textvariable=var, values=values, state='readonly',
                         width=25).grid(row=row, column=1, sticky='w', pady=4)
            self._meta_fields[label] = var
            row += 1

        def add_entry(label, default=''):
            nonlocal row
            tk.Label(form, text=label, font=('Segoe UI', 10), fg='#cdd6f4',
                     bg='#1e1e2e', anchor='w').grid(row=row, column=0, sticky='w', pady=4, padx=(0, 12))
            var = tk.StringVar(value=default)
            tk.Entry(form, textvariable=var, width=28, bg='#313244', fg='#cdd6f4',
                     insertbackground='#cdd6f4', bd=0, font=('Segoe UI', 10)
                     ).grid(row=row, column=1, sticky='w', pady=4)
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
        btn_frame = tk.Frame(self, bg='#1e1e2e')
        btn_frame.pack(pady=16)

        tk.Button(btn_frame, text="Save Asset", font=('Segoe UI', 11, 'bold'),
                  fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=20, pady=8,
                  cursor='hand2', command=self._save_asset).pack(side=tk.LEFT, padx=8)

        tk.Button(btn_frame, text="Cancel", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=16, pady=8,
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
        top = tk.Frame(self, bg='#1e1e2e')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        tk.Button(top, text="< Back", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._show_browser).pack(side=tk.LEFT)

        make_model = f"{asset.get('make', '')} {asset.get('model', '')}".strip() or asset['filename']
        tk.Label(top, text=make_model, font=('Segoe UI', 14, 'bold'),
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT, padx=16)

        # Main content: image left, metadata right
        content = tk.Frame(self, bg='#1e1e2e')
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Image with corner overlay
        img_frame = tk.Frame(content, bg='#181825')
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
                draw.polygon(pts, outline='#a6e3a1', width=3)
                for i, pt in enumerate(pts):
                    r = 5
                    draw.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                                 fill='#f38ba8', outline='white')

            scale = min(600 / pil_img.width, 450 / pil_img.height)
            disp = pil_img.resize((int(pil_img.width * scale), int(pil_img.height * scale)), Image.LANCZOS)
            self._detail_photo = ImageTk.PhotoImage(disp)
            tk.Label(img_frame, image=self._detail_photo, bg='#181825').pack(padx=4, pady=4)
        except Exception:
            tk.Label(img_frame, text="Image not found", fg='#f38ba8', bg='#181825',
                     font=('Segoe UI', 12)).pack(padx=40, pady=40)

        # Metadata panel
        meta_frame = tk.Frame(content, bg='#1e1e2e')
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
            row = tk.Frame(meta_frame, bg='#1e1e2e')
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{label}:", font=('Segoe UI', 9, 'bold'),
                     fg='#a6adc8', bg='#1e1e2e', width=14, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                     fg='#cdd6f4', bg='#1e1e2e', anchor='w').pack(side=tk.LEFT)

        # Templates referencing this asset
        ref_templates = [t for t in self.state.templates if t.get('vehicle_id') == asset_id]
        if ref_templates:
            tk.Label(meta_frame, text=f"\nUsed in {len(ref_templates)} template(s):",
                     font=('Segoe UI', 9, 'bold'), fg='#89b4fa', bg='#1e1e2e',
                     anchor='w').pack(fill=tk.X, pady=(8, 2))
            for t in ref_templates:
                tk.Label(meta_frame, text=f"  - {t.get('name', t['id'])}",
                         font=('Segoe UI', 9), fg='#cdd6f4', bg='#1e1e2e',
                         anchor='w').pack(fill=tk.X)

        # Action buttons
        btn_frame = tk.Frame(meta_frame, bg='#1e1e2e')
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        tk.Button(btn_frame, text="Edit Metadata", font=('Segoe UI', 9),
                  fg='#1e1e2e', bg='#89b4fa', bd=0, padx=12, pady=4,
                  cursor='hand2',
                  command=lambda: self._edit_metadata(asset_id)).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="Redo Corners", font=('Segoe UI', 9),
                  fg='#1e1e2e', bg='#f9e2af', bd=0, padx=12, pady=4,
                  cursor='hand2',
                  command=lambda: self._redo_asset_corners(asset_id)).pack(side=tk.LEFT, padx=4)

    def _edit_metadata(self, asset_id: int):
        """Open metadata edit dialog for an existing asset."""
        asset = self.state.asset_cache.get(asset_id)
        if not asset:
            return

        win = tk.Toplevel(self)
        win.title(f"Edit: {asset['filename']}")
        win.geometry("400x450")
        win.configure(bg='#1e1e2e')
        win.transient(self)
        win.grab_set()

        form = tk.Frame(win, bg='#1e1e2e')
        form.pack(pady=16, padx=24, fill=tk.BOTH, expand=True)

        fields = {}
        row = 0

        def add_dd(label, values, current):
            nonlocal row
            tk.Label(form, text=label, font=('Segoe UI', 10), fg='#cdd6f4',
                     bg='#1e1e2e').grid(row=row, column=0, sticky='w', pady=4)
            var = tk.StringVar(value=current)
            ttk.Combobox(form, textvariable=var, values=values, state='readonly',
                         width=22).grid(row=row, column=1, sticky='w', pady=4)
            fields[label] = var
            row += 1

        def add_ent(label, current):
            nonlocal row
            tk.Label(form, text=label, font=('Segoe UI', 10), fg='#cdd6f4',
                     bg='#1e1e2e').grid(row=row, column=0, sticky='w', pady=4)
            var = tk.StringVar(value=current)
            tk.Entry(form, textvariable=var, width=25, bg='#313244', fg='#cdd6f4',
                     insertbackground='#cdd6f4', bd=0).grid(row=row, column=1, sticky='w', pady=4)
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

        tk.Button(win, text="Save", font=('Segoe UI', 10, 'bold'),
                  fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=16, pady=6,
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
        """Simplified corner re-mapping that updates existing record."""
        self._clear()
        self._onboard_corners = []
        self._corner_dots = []
        asset = self.state.asset_cache[asset_id]
        filename = asset['filename']

        top = tk.Frame(self, bg='#1e1e2e')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(top, text=f"Redo Corners: {filename}", font=('Segoe UI', 14, 'bold'),
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)
        tk.Button(top, text="Cancel", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=10, pady=4,
                  cursor='hand2', command=lambda: self._show_detail(asset_id)).pack(side=tk.RIGHT)

        self._instruction_var = tk.StringVar(
            value="Click the 4 corners of the plate region: Top-Left first"
        )
        tk.Label(self, textvariable=self._instruction_var, font=('Segoe UI', 10),
                 fg='#f9e2af', bg='#1e1e2e').pack(pady=(4, 8))

        canvas_frame = tk.Frame(self, bg='#1e1e2e')
        canvas_frame.pack(expand=True)

        self._ob_canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H,
                                    bg='#181825', highlightthickness=1,
                                    highlightbackground='#45475a')
        self._ob_canvas.pack()

        path = os.path.join(VEHICLES_DIR, filename)
        self._onboard_pil = Image.open(path).convert('RGBA')
        self._display_scale = min(CANVAS_W / self._onboard_pil.width,
                                  CANVAS_H / self._onboard_pil.height)
        disp_w = int(self._onboard_pil.width * self._display_scale)
        disp_h = int(self._onboard_pil.height * self._display_scale)
        self._display_offset_x = (CANVAS_W - disp_w) // 2
        self._display_offset_y = (CANVAS_H - disp_h) // 2

        resized = self._onboard_pil.resize((disp_w, disp_h), Image.LANCZOS)
        self._ob_photo = ImageTk.PhotoImage(resized)
        self._ob_canvas.create_image(self._display_offset_x, self._display_offset_y,
                                     anchor='nw', image=self._ob_photo, tags='vehicle')
        self._ob_canvas.bind('<Button-1>', self._on_canvas_click)
        self._onboard_filename = filename

        btn_frame = tk.Frame(self, bg='#1e1e2e')
        btn_frame.pack(pady=8)

        def save_corners():
            corners_json = json.dumps(self._onboard_corners)
            cur = self.state.db_conn.cursor()
            cur.execute("UPDATE assets SET corners=? WHERE id=?", (corners_json, asset_id))
            self.state.db_conn.commit()
            self.app.refresh_asset_cache()
            self._show_detail(asset_id)

        self._confirm_btn = tk.Button(btn_frame, text="Save Corners",
                                      font=('Segoe UI', 10, 'bold'),
                                      fg='#1e1e2e', bg='#a6e3a1', bd=0,
                                      padx=16, pady=6, cursor='hand2',
                                      command=save_corners, state=tk.DISABLED)
        self._confirm_btn.pack(side=tk.LEFT, padx=8)

        self._redo_btn = tk.Button(btn_frame, text="Redo",
                                   font=('Segoe UI', 10),
                                   fg='#cdd6f4', bg='#f38ba8', bd=0,
                                   padx=16, pady=6, cursor='hand2',
                                   command=self._redo_corners)
        self._redo_btn.pack(side=tk.LEFT, padx=8)

    # ── Utilities ─────────────────────────────────────────────────

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()
