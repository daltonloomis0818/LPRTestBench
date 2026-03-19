"""
Templates Mode — Template builder and browser.
A template is a named composite configuration referencing an asset by ID.
"""

import json
import os
import sys
import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone
from PIL import Image, ImageTk
import threading
import customtkinter as ctk

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

VEHICLES_DIR = os.path.normpath(os.path.join(_BASE_DIR, 'assets', 'vehicles'))

VEHICLE_TYPES = ['Sedan', 'SUV', 'Pickup', 'Van', 'Box Truck', 'Commercial', 'Other']
LIGHTING_OPTIONS = ['Inherit from Asset', 'Day Sun', 'Overcast', 'Dusk', 'Night', 'Night IR', 'Rain', 'Snow', 'Fog']
WEATHER_OPTIONS = ['None', 'Rain', 'Snow', 'Fog', 'IR']
PLATE_SOURCES = ['random', 'list', 'mixed']


class TemplatesMode(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent, fg_color='#0d0d14')
        self.state = state
        self.app = app
        self._preview_photo = None
        self._preview_timer = None
        self._show_browser()

    # ── Browser ───────────────────────────────────────────────────

    def _show_browser(self):
        self._clear()

        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text="Templates", font=('Segoe UI', 16, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="+ New Template", font=('Segoe UI', 10),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2a4f7a',
                      corner_radius=8, command=self._show_builder).pack(side=tk.RIGHT)

        # Filter bar
        fbar = ctk.CTkFrame(self, fg_color='#0d0d14')
        fbar.pack(fill=tk.X, padx=16, pady=(4, 8))

        ctk.CTkLabel(fbar, text="Sort:", text_color='#e0e0e8', fg_color="transparent",
                     font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 4))
        self._sort_var = tk.StringVar(value='name')
        sort_combo = ctk.CTkComboBox(fbar, variable=self._sort_var,
                                     values=['name', 'created', 'last_used', 'vault_count'],
                                     state='readonly', width=120, fg_color="#242438",
                                     border_color="#2d2d44", button_color="#1e3a5f",
                                     dropdown_fg_color="#242438", dropdown_text_color="#e0e0e8",
                                     text_color="#e0e0e8")
        sort_combo.pack(side=tk.LEFT)
        self._sort_var.trace_add('write', lambda *_: self._refresh_list())

        ctk.CTkLabel(fbar, text="Search:", text_color='#e0e0e8', fg_color="transparent",
                     font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(12, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', lambda *_: self._refresh_list())
        ctk.CTkEntry(fbar, textvariable=self._search_var, width=160,
                     fg_color="#242438", text_color="#e0e0e8",
                     border_color="#2d2d44", font=('Segoe UI', 9)).pack(side=tk.LEFT)

        # Bulk action buttons
        ctk.CTkButton(fbar, text="Delete Selected", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#dc2626', hover_color='#b91c1c',
                      corner_radius=8, command=self._delete_selected).pack(side=tk.RIGHT, padx=4)

        # Template list — ttk.Treeview with dark styling
        list_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#1a1a2e', foreground='#e0e0e8', fieldbackground='#1a1a2e', rowheight=28)
        style.configure('Treeview.Heading', background='#242438', foreground='#e0e0e8')
        style.map('Treeview', background=[('selected', '#1e3a5f')])

        cols = ('name', 'vehicle', 'state', 'plate_source', 'vault_count', 'created')
        self._tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='extended')
        self._tree.heading('name', text='Name')
        self._tree.heading('vehicle', text='Vehicle')
        self._tree.heading('state', text='State')
        self._tree.heading('plate_source', text='Plate Source')
        self._tree.heading('vault_count', text='Vault')
        self._tree.heading('created', text='Created')

        self._tree.column('name', width=200)
        self._tree.column('vehicle', width=180)
        self._tree.column('state', width=80)
        self._tree.column('plate_source', width=100)
        self._tree.column('vault_count', width=60)
        self._tree.column('created', width=140)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind('<Double-1>', self._on_template_double_click)

        self._selected_ids: set[str] = set()
        self._refresh_list()

    def _refresh_list(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        templates = list(self.state.templates)
        search = self._search_var.get().lower().strip()
        if search:
            templates = [t for t in templates if search in t.get('name', '').lower()
                         or search in t.get('state', '').lower()
                         or search in ' '.join(t.get('tags', [])).lower()]

        sort_key = self._sort_var.get()
        reverse = sort_key in ('vault_count', 'last_used', 'created')
        templates.sort(key=lambda t: t.get(sort_key, ''), reverse=reverse)

        for t in templates:
            asset = self.state.asset_cache.get(t.get('vehicle_id'))
            vehicle_name = ''
            if asset:
                vehicle_name = f"{asset.get('make', '')} {asset.get('model', '')}".strip() or asset['filename']

            self._tree.insert('', 'end', iid=t['id'], values=(
                t.get('name', ''),
                vehicle_name,
                t.get('state', '').title(),
                t.get('plate_source', ''),
                t.get('vault_count', 0),
                t.get('created', '')[:10],
            ))

    def _on_template_double_click(self, event):
        sel = self._tree.selection()
        if sel:
            self._show_template_detail(sel[0])

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(sel)} template(s)?"):
            return
        ids_to_remove = set(sel)
        self.state.templates = [t for t in self.state.templates if t['id'] not in ids_to_remove]
        self.app.save_templates()
        self._refresh_list()

    # ── Template Detail ───────────────────────────────────────────

    def _show_template_detail(self, template_id: str):
        template = None
        for t in self.state.templates:
            if t['id'] == template_id:
                template = t
                break
        if not template:
            return

        self._show_builder(edit_template=template)

    # ── Builder ───────────────────────────────────────────────────

    def _show_builder(self, edit_template: dict | None = None):
        self._clear()
        self._edit_template = edit_template

        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        title = "Edit Template" if edit_template else "New Template"
        ctk.CTkLabel(top, text=title, font=('Segoe UI', 14, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="< Back", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#3d3d54',
                      corner_radius=8, command=self._show_browser).pack(side=tk.RIGHT)

        # Main layout: left = form, right = preview
        main = ctk.CTkFrame(self, fg_color='#0d0d14')
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        form_frame = ctk.CTkFrame(main, fg_color='#0d0d14')
        form_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))

        preview_frame = ctk.CTkFrame(main, fg_color='#0d0d14', border_color='#2d2d44',
                                     border_width=1)
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._preview_label = ctk.CTkLabel(preview_frame, text="Select a vehicle to preview",
                                           text_color='#555570', fg_color="transparent",
                                           font=('Segoe UI', 11))
        self._preview_label.pack(expand=True)

        # Form fields
        row = 0

        # Vehicle picker
        ctk.CTkLabel(form_frame, text="Vehicle:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=4)
        row += 1

        # Build vehicle options from asset cache
        self._vehicle_options: dict[str, int] = {}
        vehicle_labels = []
        for aid, asset in self.state.asset_cache.items():
            label = f"{asset.get('make', '')} {asset.get('model', '')} ({asset['filename']})".strip()
            self._vehicle_options[label] = aid
            vehicle_labels.append(label)

        self._vehicle_var = tk.StringVar()
        vehicle_combo = ctk.CTkComboBox(form_frame, variable=self._vehicle_var,
                                        values=vehicle_labels, state='readonly', width=280,
                                        fg_color="#242438", border_color="#2d2d44",
                                        button_color="#1e3a5f", dropdown_fg_color="#242438",
                                        dropdown_text_color="#e0e0e8", text_color="#e0e0e8",
                                        command=lambda _: self._schedule_preview())
        vehicle_combo.grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # State plate
        ctk.CTkLabel(form_frame, text="State Plate:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 4))
        row += 1

        from engine.plate_renderer import PlateRenderer
        self._builder_renderer = PlateRenderer()
        states = self._builder_renderer.available_states()

        self._state_var = tk.StringVar(value=states[0] if states else 'texas')
        state_combo = ctk.CTkComboBox(form_frame, variable=self._state_var,
                                      values=[s.title() for s in states], state='readonly', width=180,
                                      fg_color="#242438", border_color="#2d2d44",
                                      button_color="#1e3a5f", dropdown_fg_color="#242438",
                                      dropdown_text_color="#e0e0e8", text_color="#e0e0e8",
                                      command=lambda _: self._schedule_preview())
        state_combo.grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Lighting override
        ctk.CTkLabel(form_frame, text="Lighting:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 4))
        row += 1
        self._lighting_var = tk.StringVar(value='Inherit from Asset')
        light_combo = ctk.CTkComboBox(form_frame, variable=self._lighting_var,
                                      values=LIGHTING_OPTIONS, state='readonly', width=180,
                                      fg_color="#242438", border_color="#2d2d44",
                                      button_color="#1e3a5f", dropdown_fg_color="#242438",
                                      dropdown_text_color="#e0e0e8", text_color="#e0e0e8",
                                      command=lambda _: self._schedule_preview())
        light_combo.grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Weather override
        ctk.CTkLabel(form_frame, text="Weather:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 4))
        row += 1
        self._weather_var = tk.StringVar(value='None')
        weather_combo = ctk.CTkComboBox(form_frame, variable=self._weather_var,
                                        values=WEATHER_OPTIONS, state='readonly', width=180,
                                        fg_color="#242438", border_color="#2d2d44",
                                        button_color="#1e3a5f", dropdown_fg_color="#242438",
                                        dropdown_text_color="#e0e0e8", text_color="#e0e0e8",
                                        command=lambda _: self._schedule_preview())
        weather_combo.grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Zoom slider
        ctk.CTkLabel(form_frame, text="Zoom:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 4))
        row += 1
        self._zoom_var = tk.DoubleVar(value=1.0)
        zoom_frame = ctk.CTkFrame(form_frame, fg_color='#0d0d14')
        zoom_frame.grid(row=row, column=0, sticky='w', pady=2)
        self._zoom_label = ctk.CTkLabel(zoom_frame, text="1.0x", font=('Segoe UI', 9),
                                        text_color='#e0e0e8', fg_color="transparent", width=40)
        self._zoom_label.pack(side=tk.RIGHT)
        zoom_slider = ctk.CTkSlider(zoom_frame, from_=0.5, to=3.0,
                                    variable=self._zoom_var, width=200,
                                    fg_color="#2d2d44", button_color="#1e3a5f",
                                    progress_color="#1e3a5f",
                                    command=lambda v: (self._zoom_label.configure(text=f"{float(v):.1f}x"),
                                                       self._schedule_preview()))
        zoom_slider.pack(side=tk.LEFT)
        row += 1

        # Plate source
        ctk.CTkLabel(form_frame, text="Plate Source:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 4))
        row += 1
        self._plate_source_var = tk.StringVar(value='random')
        ps_frame = ctk.CTkFrame(form_frame, fg_color='#0d0d14')
        ps_frame.grid(row=row, column=0, sticky='w', pady=2)
        for ps in PLATE_SOURCES:
            ctk.CTkRadioButton(ps_frame, text=ps.title(), variable=self._plate_source_var,
                               value=ps, fg_color="#1e3a5f", text_color="#e0e0e8",
                               border_color="#2d2d44", hover_color="#2a4f7a"
                               ).pack(side=tk.LEFT, padx=4)
        row += 1

        # Mix ratio (shown only for mixed)
        self._ratio_var = tk.DoubleVar(value=0.3)
        ratio_frame = ctk.CTkFrame(form_frame, fg_color='#0d0d14')
        ratio_frame.grid(row=row, column=0, sticky='w', pady=2)
        ctk.CTkLabel(ratio_frame, text="List ratio:", font=('Segoe UI', 9),
                     text_color='#8888a0', fg_color="transparent").pack(side=tk.LEFT)
        self._ratio_label = ctk.CTkLabel(ratio_frame, text="0.30", font=('Segoe UI', 9),
                                         text_color='#e0e0e8', fg_color="transparent", width=35)
        self._ratio_label.pack(side=tk.RIGHT)
        ctk.CTkSlider(ratio_frame, from_=0.0, to=1.0,
                      variable=self._ratio_var, width=150,
                      fg_color="#2d2d44", button_color="#1e3a5f",
                      progress_color="#1e3a5f",
                      command=lambda v: self._ratio_label.configure(text=f"{float(v):.2f}")
                      ).pack(side=tk.LEFT)
        row += 1

        # Locked plate
        ctk.CTkLabel(form_frame, text="Locked Plate (optional):", font=('Segoe UI', 10),
                     text_color='#8888a0', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 2))
        row += 1
        self._locked_plate_var = tk.StringVar()
        ctk.CTkEntry(form_frame, textvariable=self._locked_plate_var, width=150,
                     fg_color="#242438", text_color="#e0e0e8",
                     border_color="#2d2d44", font=('Segoe UI', 10)).grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Tags
        ctk.CTkLabel(form_frame, text="Tags (comma separated):", font=('Segoe UI', 10),
                     text_color='#8888a0', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 2))
        row += 1
        self._tags_var = tk.StringVar()
        ctk.CTkEntry(form_frame, textvariable=self._tags_var, width=240,
                     fg_color="#242438", text_color="#e0e0e8",
                     border_color="#2d2d44", font=('Segoe UI', 10)).grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Name
        ctk.CTkLabel(form_frame, text="Template Name:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").grid(row=row, column=0, sticky='w', pady=(8, 2))
        row += 1
        self._name_var = tk.StringVar()
        ctk.CTkEntry(form_frame, textvariable=self._name_var, width=240,
                     fg_color="#242438", text_color="#e0e0e8",
                     border_color="#2d2d44", font=('Segoe UI', 10)).grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # Save button
        ctk.CTkButton(form_frame, text="Save Template", font=('Segoe UI', 11, 'bold'),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2a4f7a',
                      corner_radius=8, command=self._save_template
                      ).grid(row=row, column=0, sticky='w', pady=(16, 0))

        # If editing, populate fields
        if edit_template:
            self._populate_builder(edit_template)

    def _populate_builder(self, t: dict):
        """Fill builder fields from an existing template."""
        # Find vehicle label
        vid = t.get('vehicle_id')
        for label, aid in self._vehicle_options.items():
            if aid == vid:
                self._vehicle_var.set(label)
                break

        self._state_var.set(t.get('state', 'texas').title())

        lo = t.get('lighting_override')
        if lo:
            self._lighting_var.set(lo.replace('_', ' ').title())
        else:
            self._lighting_var.set('Inherit from Asset')

        wo = t.get('weather_override')
        self._weather_var.set(wo.title() if wo else 'None')

        self._zoom_var.set(t.get('zoom', 1.0))
        self._zoom_label.configure(text=f"{t.get('zoom', 1.0):.1f}x")

        self._plate_source_var.set(t.get('plate_source', 'random'))
        self._ratio_var.set(t.get('mix_ratio', 0.3))
        self._ratio_label.configure(text=f"{t.get('mix_ratio', 0.3):.2f}")
        self._locked_plate_var.set(t.get('locked_plate', '') or '')
        self._tags_var.set(', '.join(t.get('tags', [])))
        self._name_var.set(t.get('name', ''))

        self._schedule_preview()

    def _schedule_preview(self):
        """Debounced preview update — waits 500ms after last change."""
        if self._preview_timer:
            self.after_cancel(self._preview_timer)
        self._preview_timer = self.after(500, self._update_preview)

    def _update_preview(self):
        """Render a preview composite on a background thread."""
        vehicle_label = self._vehicle_var.get()
        vehicle_id = self._vehicle_options.get(vehicle_label)
        if not vehicle_id:
            return

        asset = self.state.asset_cache.get(vehicle_id)
        if not asset:
            return

        state = self._state_var.get().lower()
        lighting = self._lighting_var.get()
        weather = self._weather_var.get()
        zoom = self._zoom_var.get()

        def render():
            try:
                from engine.compositor import Compositor
                from engine import effects

                vehicle_path = os.path.join(VEHICLES_DIR, asset['filename'])
                vehicle_img = Image.open(vehicle_path).convert('RGBA')

                plate_img = self._builder_renderer.render(state, 'ABC-1234')

                corners = asset['corners']
                if isinstance(corners, str):
                    corners = json.loads(corners)

                comp = Compositor()
                result = comp.composite(vehicle_img, plate_img, corners)

                # Lighting
                if lighting != 'Inherit from Asset':
                    tag = lighting.lower().replace(' ', '_')
                else:
                    tag = asset.get('lighting', 'day_sun')
                result = effects.apply_lighting(result, tag)

                # Weather
                if weather != 'None':
                    result = effects.apply_weather(result, weather.lower())

                # Zoom
                if zoom > 1.0:
                    result = effects.apply_zoom(result, zoom)

                # Scale for preview
                max_w, max_h = 550, 420
                scale = min(max_w / result.width, max_h / result.height, 1.0)
                if scale < 1.0:
                    result = result.resize((int(result.width * scale), int(result.height * scale)),
                                           Image.LANCZOS)

                self._preview_photo = ImageTk.PhotoImage(result)
                self._preview_label.configure(image=self._preview_photo, text='')

            except Exception as e:
                self._preview_label.configure(text=f"Preview error: {e}", image='')

        threading.Thread(target=render, daemon=True).start()

    def _save_template(self):
        vehicle_label = self._vehicle_var.get()
        vehicle_id = self._vehicle_options.get(vehicle_label)
        if not vehicle_id:
            messagebox.showwarning("Missing", "Please select a vehicle.")
            return

        state = self._state_var.get().lower()
        lighting = self._lighting_var.get()
        weather = self._weather_var.get()

        lighting_override = None
        if lighting != 'Inherit from Asset':
            lighting_override = lighting.lower().replace(' ', '_')

        weather_override = None
        if weather != 'None':
            weather_override = weather.lower()

        tags = [t.strip() for t in self._tags_var.get().split(',') if t.strip()]
        locked = self._locked_plate_var.get().strip() or None

        # Auto-generate name if empty
        name = self._name_var.get().strip()
        if not name:
            asset = self.state.asset_cache.get(vehicle_id, {})
            name = f"{asset.get('make', '')} {asset.get('model', '')} - {state.title()}".strip(' -')

        now = datetime.now(timezone.utc).isoformat()

        if self._edit_template:
            # Update existing
            template = self._edit_template
            template.update({
                'name': name,
                'vehicle_id': vehicle_id,
                'state': state,
                'lighting_override': lighting_override,
                'weather_override': weather_override,
                'zoom': self._zoom_var.get(),
                'plate_source': self._plate_source_var.get(),
                'mix_ratio': self._ratio_var.get(),
                'locked_plate': locked,
                'tags': tags,
                'last_used': now,
            })
        else:
            template = {
                'id': str(uuid.uuid4()),
                'name': name,
                'vehicle_id': vehicle_id,
                'state': state,
                'lighting_override': lighting_override,
                'weather_override': weather_override,
                'zoom': self._zoom_var.get(),
                'plate_source': self._plate_source_var.get(),
                'mix_ratio': self._ratio_var.get(),
                'locked_plate': locked,
                'tags': tags,
                'library_ids': [],
                'created': now,
                'last_used': now,
                'vault_count': 0,
            }
            self.state.templates.append(template)

        self.app.save_templates()
        self._show_browser()

    def _clear(self):
        if self._preview_timer:
            self.after_cancel(self._preview_timer)
            self._preview_timer = None
        for widget in self.winfo_children():
            widget.destroy()
