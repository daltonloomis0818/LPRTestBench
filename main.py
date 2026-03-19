"""
LPRTestBench — Entry point.
Top navigation bar, mode router, startup initialization.
"""

import os
import sys
import json
import sqlite3
import tkinter as tk
from tkinter import ttk

# Determine project root — works both as script and as frozen EXE
if getattr(sys, 'frozen', False):
    # Running as PyInstaller EXE — use the directory the EXE lives in
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

ASSETS_VEHICLES_DIR = os.path.join(ROOT_DIR, 'assets', 'vehicles')
ASSETS_PLATES_DIR = os.path.join(ROOT_DIR, 'assets', 'plates')
ASSETS_OVERLAYS_DIR = os.path.join(ROOT_DIR, 'assets', 'overlays')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
VAULT_DIR = os.path.join(ROOT_DIR, 'vault')
OUTPUT_DIR = os.path.join(ROOT_DIR, 'output')

DB_PATH = os.path.join(DATA_DIR, 'asset_registry.db')
TEMPLATES_PATH = os.path.join(DATA_DIR, 'templates.json')
LIBRARIES_PATH = os.path.join(DATA_DIR, 'libraries.json')
SESSION_LOG_PATH = os.path.join(DATA_DIR, 'session_log.json')


class AppState:
    """Shared application state passed to all mode frames."""

    def __init__(self):
        self.db_conn: sqlite3.Connection | None = None
        self.templates: list[dict] = []
        self.libraries: list[dict] = []
        self.asset_cache: dict[int, dict] = {}
        self.unregistered_assets: list[str] = []


class LPRTestBenchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LPRTestBench")
        self.geometry("1400x900")
        self.minsize(1100, 700)
        self.configure(bg='#0d0d14')

        self.state_obj = AppState()
        self._current_mode = None
        self._current_frame: tk.Frame | None = None

        self._ensure_directories()
        self._init_database()
        self._load_data()
        self._scan_unregistered_assets()
        self._build_nav()
        self._build_container()

        # Start in Assets mode
        self._switch_mode('assets')

    def _ensure_directories(self):
        for d in [ASSETS_VEHICLES_DIR, ASSETS_PLATES_DIR, ASSETS_OVERLAYS_DIR,
                  DATA_DIR, VAULT_DIR, OUTPUT_DIR]:
            os.makedirs(d, exist_ok=True)

    def _init_database(self):
        self.state_obj.db_conn = sqlite3.connect(DB_PATH)
        self.state_obj.db_conn.row_factory = sqlite3.Row
        cur = self.state_obj.db_conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT NOT NULL UNIQUE,
                vehicle_type TEXT NOT NULL,
                make        TEXT DEFAULT '',
                model       TEXT DEFAULT '',
                color       TEXT DEFAULT '',
                lighting    TEXT NOT NULL DEFAULT 'day_sun',
                angle       TEXT NOT NULL DEFAULT 'straight',
                distance    TEXT NOT NULL DEFAULT 'medium',
                tags        TEXT DEFAULT '',
                corners     TEXT NOT NULL DEFAULT '[]',
                vault_count INTEGER DEFAULT 0,
                date_added  TEXT NOT NULL
            )
        ''')
        self.state_obj.db_conn.commit()

    def _load_data(self):
        # Load asset cache from DB
        cur = self.state_obj.db_conn.cursor()
        cur.execute("SELECT * FROM assets")
        for row in cur.fetchall():
            self.state_obj.asset_cache[row['id']] = dict(row)

        # Load templates
        if os.path.isfile(TEMPLATES_PATH):
            with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
                self.state_obj.templates = json.load(f)

        # Load libraries
        if os.path.isfile(LIBRARIES_PATH):
            with open(LIBRARIES_PATH, 'r', encoding='utf-8') as f:
                self.state_obj.libraries = json.load(f)

    def _scan_unregistered_assets(self):
        """Find PNGs in vehicles dir that aren't in the database."""
        self.state_obj.unregistered_assets.clear()
        if not os.path.isdir(ASSETS_VEHICLES_DIR):
            return
        registered = {a['filename'] for a in self.state_obj.asset_cache.values()}
        for fname in os.listdir(ASSETS_VEHICLES_DIR):
            if fname.lower().endswith('.png') and fname not in registered:
                self.state_obj.unregistered_assets.append(fname)

    def _build_nav(self):
        nav = tk.Frame(self, bg='#0d0d14', height=50)
        nav.pack(side=tk.TOP, fill=tk.X)
        nav.pack_propagate(False)

        self._nav_buttons: dict[str, tk.Button] = {}
        modes = [
            ('assets', 'Assets'),
            ('templates', 'Templates'),
            ('libraries', 'Libraries'),
            ('demo', 'Demo'),
        ]

        for mode_key, label in modes:
            btn = tk.Button(
                nav, text=label,
                font=('Segoe UI', 11, 'bold'),
                fg='#8888a0', bg='#0d0d14',
                activeforeground='#ffffff', activebackground='#1e3a5f',
                bd=0, padx=24, pady=10,
                cursor='hand2',
                command=lambda m=mode_key: self._switch_mode(m),
            )
            btn.pack(side=tk.LEFT)
            self._nav_buttons[mode_key] = btn

        # Plate List editor button
        tk.Button(
            nav, text='Plate List',
            font=('Segoe UI', 10),
            fg='#ffffff', bg='#1e3a5f',
            activeforeground='#ffffff', activebackground='#264d80',
            bd=0, padx=16, pady=10,
            cursor='hand2',
            command=self._open_plate_list_editor,
        ).pack(side=tk.RIGHT)

        # Unregistered asset indicator
        self._unreg_label = tk.Label(
            nav, text='', font=('Segoe UI', 10),
            fg='#dc2626', bg='#0d0d14',
        )
        self._unreg_label.pack(side=tk.RIGHT, padx=16)
        self._update_unreg_indicator()

    def _update_unreg_indicator(self):
        count = len(self.state_obj.unregistered_assets)
        if count > 0:
            self._unreg_label.configure(
                text=f"{count} unregistered asset{'s' if count != 1 else ''}"
            )
        else:
            self._unreg_label.configure(text='')

    def _open_plate_list_editor(self):
        """Open a window to view and edit the plate list."""
        plate_list_path = os.path.join(DATA_DIR, 'plate_list.txt')

        win = tk.Toplevel(self)
        win.title("Plate List")
        win.geometry("340x550")
        win.configure(bg='#0d0d14')
        win.transient(self)

        # Header with count
        header = tk.Frame(win, bg='#0d0d14')
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="Plate List", font=('Segoe UI', 14, 'bold'),
                 fg='#e0e0e8', bg='#0d0d14').pack(side=tk.LEFT)
        count_var = tk.StringVar(value="0 plates")
        tk.Label(header, textvariable=count_var, font=('Segoe UI', 10),
                 fg='#555570', bg='#0d0d14').pack(side=tk.RIGHT)

        # Add row: entry + "+" button
        add_frame = tk.Frame(win, bg='#0d0d14')
        add_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        add_var = tk.StringVar()
        add_entry = tk.Entry(add_frame, textvariable=add_var,
                             bg='#242438', fg='#e0e0e8', insertbackground='#e0e0e8',
                             bd=0, font=('Consolas', 14), width=14)
        add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=4)

        def add_plate():
            plate = add_var.get().strip().upper()
            if not plate:
                return
            # Check for duplicate
            existing = listbox.get(0, tk.END)
            if plate in existing:
                return
            listbox.insert(tk.END, plate)
            add_var.set('')
            update_count()
            listbox.see(tk.END)
            add_entry.focus()

        add_entry.bind('<Return>', lambda e: add_plate())

        tk.Button(add_frame, text="+", font=('Segoe UI', 14, 'bold'),
                  fg='#ffffff', bg='#1e3a5f', bd=0, width=3,
                  cursor='hand2', command=add_plate).pack(side=tk.RIGHT)

        # Listbox with scrollbar
        list_frame = tk.Frame(win, bg='#0d0d14')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, bg='#1a1a2e', fg='#e0e0e8',
                             selectbackground='#1e3a5f', selectforeground='#ffffff',
                             font=('Consolas', 13), bd=0, highlightthickness=0,
                             yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        # Load current plates
        if os.path.isfile(plate_list_path):
            with open(plate_list_path, 'r', encoding='utf-8') as f:
                for line in f:
                    p = line.strip()
                    if p:
                        listbox.insert(tk.END, p)

        def update_count():
            count_var.set(f"{listbox.size()} plates")

        update_count()

        # Remove button: "-" removes selected plates
        remove_frame = tk.Frame(win, bg='#0d0d14')
        remove_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        def remove_selected():
            sel = listbox.curselection()
            if not sel:
                return
            for idx in reversed(sel):
                listbox.delete(idx)
            update_count()

        tk.Button(remove_frame, text="-  Remove Selected", font=('Segoe UI', 10),
                  fg='#ffffff', bg='#dc2626', bd=0, padx=12, pady=4,
                  cursor='hand2', command=remove_selected).pack(side=tk.LEFT)

        tk.Button(remove_frame, text="Clear All", font=('Segoe UI', 10),
                  fg='#e0e0e8', bg='#2d2d44', bd=0, padx=12, pady=4,
                  cursor='hand2',
                  command=lambda: (listbox.delete(0, tk.END), update_count())
                  ).pack(side=tk.RIGHT)

        # Save button
        def save():
            plates = list(listbox.get(0, tk.END))
            with open(plate_list_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(plates) + '\n')
            win.destroy()

        tk.Button(win, text="Save", font=('Segoe UI', 11, 'bold'),
                  fg='#ffffff', bg='#1e3a5f', bd=0, padx=24, pady=8,
                  cursor='hand2', command=save).pack(pady=(0, 12))

        add_entry.focus()

    def _build_container(self):
        self._container = tk.Frame(self, bg='#0d0d14')
        self._container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _switch_mode(self, mode: str):
        if mode == self._current_mode:
            return

        # Update nav button highlighting
        for key, btn in self._nav_buttons.items():
            if key == mode:
                btn.configure(bg='#1e3a5f', fg='#ffffff', padx=24, pady=10)
            else:
                btn.configure(bg='#0d0d14', fg='#8888a0', padx=24, pady=10)

        # Destroy current frame
        if self._current_frame:
            self._current_frame.destroy()

        # Import and instantiate the mode frame
        self._current_mode = mode
        if mode == 'assets':
            from modes.assets_mode import AssetsMode
            self._current_frame = AssetsMode(self._container, self.state_obj, self)
        elif mode == 'templates':
            from modes.templates_mode import TemplatesMode
            self._current_frame = TemplatesMode(self._container, self.state_obj, self)
        elif mode == 'libraries':
            from modes.libraries_mode import LibrariesMode
            self._current_frame = LibrariesMode(self._container, self.state_obj, self)
        elif mode == 'demo':
            from modes.demo_mode import DemoMode
            self._current_frame = DemoMode(self._container, self.state_obj, self)

        if self._current_frame:
            self._current_frame.pack(fill=tk.BOTH, expand=True)

    def refresh_asset_cache(self):
        """Reload asset cache from database."""
        self.state_obj.asset_cache.clear()
        cur = self.state_obj.db_conn.cursor()
        cur.execute("SELECT * FROM assets")
        for row in cur.fetchall():
            self.state_obj.asset_cache[row['id']] = dict(row)
        self._scan_unregistered_assets()
        self._update_unreg_indicator()

    def save_templates(self):
        """Write templates list to JSON."""
        with open(TEMPLATES_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.state_obj.templates, f, indent=2)

    def save_libraries(self):
        """Write libraries list to JSON."""
        with open(LIBRARIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.state_obj.libraries, f, indent=2)


def main():
    app = LPRTestBenchApp()
    app.mainloop()


if __name__ == '__main__':
    main()
