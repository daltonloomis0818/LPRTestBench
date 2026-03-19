"""
Libraries Mode — Library builder and browser.
Libraries are named, ordered collections of templates.
"""

import json
import os
import sys
import uuid
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from datetime import datetime, timezone

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')


class LibrariesMode(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent, fg_color='#0d0d14')
        self.state = state
        self.app = app
        self._show_browser()

    # ── Browser ───────────────────────────────────────────────────

    def _show_browser(self):
        self._clear()

        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text="Libraries", font=('Segoe UI', 16, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="+ New Library", font=('Segoe UI', 10),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                      corner_radius=8, cursor='hand2',
                      command=self._show_builder).pack(side=tk.RIGHT)

        if not self.state.libraries:
            ctk.CTkLabel(self, text="No libraries yet.\nCreate one to group your templates for demos.",
                         font=('Segoe UI', 12), text_color='#555570', fg_color="transparent",
                         justify=tk.CENTER).pack(expand=True)
            return

        # Library list
        list_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 12))

        for lib in self.state.libraries:
            card = ctk.CTkFrame(list_frame, fg_color='#242438', border_color='#2d2d44',
                                border_width=1, corner_radius=8, cursor='hand2')
            card.pack(fill=tk.X, pady=4)

            # Info
            info = ctk.CTkFrame(card, fg_color='#242438')
            info.pack(fill=tk.X, padx=12, pady=8)

            ctk.CTkLabel(info, text=lib.get('name', 'Unnamed'),
                         font=('Segoe UI', 12, 'bold'), text_color='#e0e0e8',
                         fg_color="transparent").pack(anchor='w')

            desc = lib.get('description', '')
            if desc:
                ctk.CTkLabel(info, text=desc, font=('Segoe UI', 9),
                             text_color='#8888a0', fg_color="transparent",
                             wraplength=600, anchor='w').pack(anchor='w')

            # Stats row
            stats = ctk.CTkFrame(info, fg_color='#242438')
            stats.pack(anchor='w', pady=(4, 0))

            template_count = len(lib.get('template_ids', []))
            ctk.CTkLabel(stats, text=f"{template_count} templates",
                         font=('Segoe UI', 8), text_color='#1e3a5f',
                         fg_color="transparent").pack(side=tk.LEFT, padx=(0, 12))

            ctk.CTkLabel(stats, text=f"Cycle: {lib.get('cycle_mode', 'sequential')}",
                         font=('Segoe UI', 8), text_color='#8888a0',
                         fg_color="transparent").pack(side=tk.LEFT, padx=(0, 12))

            last_run = lib.get('last_run', '')
            if last_run:
                ctk.CTkLabel(stats, text=f"Last run: {last_run[:10]}",
                             font=('Segoe UI', 8), text_color='#8888a0',
                             fg_color="transparent").pack(side=tk.LEFT)

            # Action buttons
            btn_frame = ctk.CTkFrame(card, fg_color='#242438')
            btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

            lib_id = lib['id']
            ctk.CTkButton(btn_frame, text="Launch Demo", font=('Segoe UI', 9, 'bold'),
                          text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                          corner_radius=8, cursor='hand2',
                          command=lambda lid=lib_id: self._launch_demo(lid)).pack(side=tk.LEFT, padx=4)

            ctk.CTkButton(btn_frame, text="Edit", font=('Segoe UI', 9),
                          text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#1e3a5f',
                          corner_radius=8, cursor='hand2',
                          command=lambda lid=lib_id: self._edit_library(lid)).pack(side=tk.LEFT, padx=4)

            ctk.CTkButton(btn_frame, text="Duplicate", font=('Segoe UI', 9),
                          text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#1e3a5f',
                          corner_radius=8, cursor='hand2',
                          command=lambda lid=lib_id: self._duplicate_library(lid)).pack(side=tk.LEFT, padx=4)

            ctk.CTkButton(btn_frame, text="Delete", font=('Segoe UI', 9),
                          text_color='#ffffff', fg_color='#dc2626', hover_color='#b91c1c',
                          corner_radius=8, cursor='hand2',
                          command=lambda lid=lib_id: self._delete_library(lid)).pack(side=tk.LEFT, padx=4)

    def _launch_demo(self, library_id: str):
        """Switch to Demo Mode with this library pre-selected."""
        self.app._switch_mode('demo')
        # Pass library_id to demo mode via app state
        if hasattr(self.app, '_current_frame') and self.app._current_frame:
            self.app._current_frame.load_library(library_id)

    def _edit_library(self, library_id: str):
        lib = self._find_library(library_id)
        if lib:
            self._show_builder(edit_library=lib)

    def _duplicate_library(self, library_id: str):
        lib = self._find_library(library_id)
        if not lib:
            return
        new_lib = dict(lib)
        new_lib['id'] = str(uuid.uuid4())
        new_lib['name'] = lib['name'] + ' (Copy)'
        new_lib['created'] = datetime.now(timezone.utc).isoformat()
        new_lib['last_run'] = ''
        self.state.libraries.append(new_lib)
        self.app.save_libraries()
        self._show_browser()

    def _delete_library(self, library_id: str):
        if not messagebox.askyesno("Confirm", "Delete this library?"):
            return
        self.state.libraries = [l for l in self.state.libraries if l['id'] != library_id]
        self.app.save_libraries()
        self._show_browser()

    def _find_library(self, library_id: str) -> dict | None:
        for lib in self.state.libraries:
            if lib['id'] == library_id:
                return lib
        return None

    # ── Builder ───────────────────────────────────────────────────

    def _show_builder(self, edit_library: dict | None = None):
        self._clear()
        self._edit_library = edit_library

        top = ctk.CTkFrame(self, fg_color='#0d0d14')
        top.pack(fill=tk.X, padx=16, pady=(12, 4))

        title = "Edit Library" if edit_library else "New Library"
        ctk.CTkLabel(top, text=title, font=('Segoe UI', 14, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)

        ctk.CTkButton(top, text="< Back", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#1e3a5f',
                      corner_radius=8, cursor='hand2',
                      command=self._show_browser).pack(side=tk.RIGHT)

        # Name / Description
        meta_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        meta_frame.pack(fill=tk.X, padx=16, pady=(8, 4))

        ctk.CTkLabel(meta_frame, text="Name:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT)
        self._lib_name_var = tk.StringVar(value=edit_library.get('name', '') if edit_library else '')
        ctk.CTkEntry(meta_frame, textvariable=self._lib_name_var, width=250,
                     fg_color='#242438', text_color='#e0e0e8',
                     border_color='#2d2d44', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=8)

        ctk.CTkLabel(meta_frame, text="Cycle:", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(side=tk.LEFT, padx=(16, 4))
        self._cycle_var = tk.StringVar(value=edit_library.get('cycle_mode', 'sequential') if edit_library else 'sequential')
        ctk.CTkComboBox(meta_frame, variable=self._cycle_var,
                        values=['sequential', 'random'], state='readonly', width=120,
                        fg_color='#242438', text_color='#e0e0e8',
                        border_color='#2d2d44', button_color='#2d2d44',
                        dropdown_fg_color='#242438', dropdown_text_color='#e0e0e8',
                        dropdown_hover_color='#1e3a5f').pack(side=tk.LEFT)

        desc_frame = ctk.CTkFrame(self, fg_color='#0d0d14')
        desc_frame.pack(fill=tk.X, padx=16, pady=(0, 8))
        ctk.CTkLabel(desc_frame, text="Description:", font=('Segoe UI', 10),
                     text_color='#8888a0', fg_color="transparent").pack(side=tk.LEFT)
        self._lib_desc_var = tk.StringVar(value=edit_library.get('description', '') if edit_library else '')
        ctk.CTkEntry(desc_frame, textvariable=self._lib_desc_var, width=500,
                     fg_color='#242438', text_color='#e0e0e8',
                     border_color='#2d2d44', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=8)

        # Main: left = available templates, right = library contents
        main = ctk.CTkFrame(self, fg_color='#0d0d14')
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # Left: available templates
        left = ctk.CTkFrame(main, fg_color='#0d0d14')
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        ctk.CTkLabel(left, text="Available Templates", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(anchor='w', padx=4, pady=(4, 2))

        # Filter
        filter_bar = ctk.CTkFrame(left, fg_color='#0d0d14')
        filter_bar.pack(fill=tk.X, padx=4, pady=4)
        self._tpl_search = tk.StringVar()
        self._tpl_search.trace_add('write', lambda *_: self._refresh_available())
        ctk.CTkEntry(filter_bar, textvariable=self._tpl_search, width=200,
                     fg_color='#242438', text_color='#e0e0e8',
                     border_color='#2d2d44', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=4)
        ctk.CTkLabel(filter_bar, text="(search)", text_color='#555570', fg_color="transparent",
                     font=('Segoe UI', 8)).pack(side=tk.LEFT)

        self._avail_listbox = tk.Listbox(left, bg='#1a1a2e', fg='#e0e0e8',
                                          selectbackground='#1e3a5f',
                                          selectforeground='#ffffff',
                                          font=('Segoe UI', 9), selectmode=tk.EXTENDED,
                                          bd=0, highlightthickness=0)
        self._avail_listbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        add_btn_frame = ctk.CTkFrame(left, fg_color='#0d0d14')
        add_btn_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        ctk.CTkButton(add_btn_frame, text="Add Selected >>", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                      corner_radius=8, cursor='hand2',
                      command=self._add_selected).pack(side=tk.LEFT)
        ctk.CTkButton(add_btn_frame, text="Add All Filtered >>", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                      corner_radius=8, cursor='hand2',
                      command=self._add_all_filtered).pack(side=tk.LEFT, padx=4)

        # Right: library contents
        right = ctk.CTkFrame(main, fg_color='#0d0d14')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        ctk.CTkLabel(right, text="Library Contents (ordered)", font=('Segoe UI', 10, 'bold'),
                     text_color='#e0e0e8', fg_color="transparent").pack(anchor='w', padx=4, pady=(4, 2))

        self._lib_listbox = tk.Listbox(right, bg='#1a1a2e', fg='#e0e0e8',
                                        selectbackground='#1e3a5f',
                                        selectforeground='#ffffff',
                                        font=('Segoe UI', 9), selectmode=tk.SINGLE,
                                        bd=0, highlightthickness=0)
        self._lib_listbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        order_frame = ctk.CTkFrame(right, fg_color='#0d0d14')
        order_frame.pack(fill=tk.X, padx=4, pady=(0, 4))

        ctk.CTkButton(order_frame, text="Up", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#1e3a5f',
                      corner_radius=8, cursor='hand2',
                      command=self._move_up).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(order_frame, text="Down", font=('Segoe UI', 9),
                      text_color='#e0e0e8', fg_color='#2d2d44', hover_color='#1e3a5f',
                      corner_radius=8, cursor='hand2',
                      command=self._move_down).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(order_frame, text="Remove", font=('Segoe UI', 9),
                      text_color='#ffffff', fg_color='#dc2626', hover_color='#b91c1c',
                      corner_radius=8, cursor='hand2',
                      command=self._remove_selected).pack(side=tk.LEFT, padx=2)

        # Save button
        ctk.CTkButton(self, text="Save Library", font=('Segoe UI', 11, 'bold'),
                      text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                      corner_radius=8, cursor='hand2',
                      command=self._save_library).pack(pady=(4, 12))

        # Track template IDs in library order
        self._lib_template_ids: list[str] = []
        if edit_library:
            self._lib_template_ids = list(edit_library.get('template_ids', []))

        self._avail_template_map: dict[int, str] = {}  # listbox index -> template id
        self._refresh_available()
        self._refresh_lib_list()

    def _refresh_available(self):
        self._avail_listbox.delete(0, tk.END)
        self._avail_template_map.clear()

        search = self._tpl_search.get().lower().strip()
        idx = 0
        for t in self.state.templates:
            name = t.get('name', t['id'])
            if search and search not in name.lower():
                continue
            asset = self.state.asset_cache.get(t.get('vehicle_id'), {})
            vehicle = f"{asset.get('make', '')} {asset.get('model', '')}".strip()
            display = f"{name} ({vehicle}, {t.get('state', '').title()})"
            self._avail_listbox.insert(tk.END, display)
            self._avail_template_map[idx] = t['id']
            idx += 1

    def _refresh_lib_list(self):
        self._lib_listbox.delete(0, tk.END)
        templates_by_id = {t['id']: t for t in self.state.templates}
        for tid in self._lib_template_ids:
            t = templates_by_id.get(tid)
            if t:
                asset = self.state.asset_cache.get(t.get('vehicle_id'), {})
                vehicle = f"{asset.get('make', '')} {asset.get('model', '')}".strip()
                display = f"{t.get('name', tid)} ({vehicle})"
            else:
                display = f"[Missing template: {tid[:8]}]"
            self._lib_listbox.insert(tk.END, display)

    def _add_selected(self):
        sel = self._avail_listbox.curselection()
        for idx in sel:
            tid = self._avail_template_map.get(idx)
            if tid and tid not in self._lib_template_ids:
                self._lib_template_ids.append(tid)
        self._refresh_lib_list()

    def _add_all_filtered(self):
        for idx, tid in self._avail_template_map.items():
            if tid not in self._lib_template_ids:
                self._lib_template_ids.append(tid)
        self._refresh_lib_list()

    def _move_up(self):
        sel = self._lib_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self._lib_template_ids[idx - 1], self._lib_template_ids[idx] = \
            self._lib_template_ids[idx], self._lib_template_ids[idx - 1]
        self._refresh_lib_list()
        self._lib_listbox.selection_set(idx - 1)

    def _move_down(self):
        sel = self._lib_listbox.curselection()
        if not sel or sel[0] >= len(self._lib_template_ids) - 1:
            return
        idx = sel[0]
        self._lib_template_ids[idx + 1], self._lib_template_ids[idx] = \
            self._lib_template_ids[idx], self._lib_template_ids[idx + 1]
        self._refresh_lib_list()
        self._lib_listbox.selection_set(idx + 1)

    def _remove_selected(self):
        sel = self._lib_listbox.curselection()
        if not sel:
            return
        del self._lib_template_ids[sel[0]]
        self._refresh_lib_list()

    def _save_library(self):
        name = self._lib_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Please enter a library name.")
            return

        if not self._lib_template_ids:
            messagebox.showwarning("Empty", "Add at least one template to the library.")
            return

        now = datetime.now(timezone.utc).isoformat()

        if self._edit_library:
            lib = self._edit_library
            lib.update({
                'name': name,
                'description': self._lib_desc_var.get().strip(),
                'template_ids': self._lib_template_ids,
                'cycle_mode': self._cycle_var.get(),
            })
        else:
            lib = {
                'id': str(uuid.uuid4()),
                'name': name,
                'description': self._lib_desc_var.get().strip(),
                'template_ids': self._lib_template_ids,
                'cycle_mode': self._cycle_var.get(),
                'created': now,
                'last_run': '',
                'tags': [],
            }
            self.state.libraries.append(lib)

        self.app.save_libraries()
        self._show_browser()

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()
