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
        self.configure(bg='#1e1e2e')

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
        nav = tk.Frame(self, bg='#11111b', height=50)
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
                fg='#cdd6f4', bg='#11111b',
                activeforeground='#cdd6f4', activebackground='#313244',
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
            fg='#a6e3a1', bg='#11111b',
            activeforeground='#a6e3a1', activebackground='#313244',
            bd=0, padx=16, pady=10,
            cursor='hand2',
            command=self._open_plate_list_editor,
        ).pack(side=tk.RIGHT)

        # Unregistered asset indicator
        self._unreg_label = tk.Label(
            nav, text='', font=('Segoe UI', 10),
            fg='#f38ba8', bg='#11111b',
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
        win.title("Plate List Editor")
        win.geometry("420x600")
        win.configure(bg='#1e1e2e')
        win.transient(self)

        # Header
        header = tk.Frame(win, bg='#1e1e2e')
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="Plate List", font=('Segoe UI', 14, 'bold'),
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)

        # Count label
        count_var = tk.StringVar()
        tk.Label(header, textvariable=count_var, font=('Segoe UI', 10),
                 fg='#6c7086', bg='#1e1e2e').pack(side=tk.RIGHT)

        # Instructions
        tk.Label(win, text="One plate per line. Used by templates set to List or Mixed mode.",
                 font=('Segoe UI', 9), fg='#a6adc8', bg='#1e1e2e',
                 wraplength=380).pack(padx=16, pady=(0, 8))

        # Text area with scrollbar
        text_frame = tk.Frame(win, bg='#1e1e2e')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_area = tk.Text(text_frame, bg='#313244', fg='#cdd6f4',
                            insertbackground='#cdd6f4', font=('Consolas', 12),
                            bd=0, padx=8, pady=8, undo=True,
                            yscrollcommand=scrollbar.set)
        text_area.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_area.yview)

        # Load current plates
        if os.path.isfile(plate_list_path):
            with open(plate_list_path, 'r', encoding='utf-8') as f:
                text_area.insert('1.0', f.read())

        def update_count(*_):
            content = text_area.get('1.0', 'end-1c')
            plates = [l.strip() for l in content.splitlines() if l.strip()]
            count_var.set(f"{len(plates)} plates")

        text_area.bind('<KeyRelease>', update_count)
        update_count()

        # Add plate entry
        add_frame = tk.Frame(win, bg='#1e1e2e')
        add_frame.pack(fill=tk.X, padx=16, pady=(0, 4))

        add_var = tk.StringVar()
        add_entry = tk.Entry(add_frame, textvariable=add_var, width=15,
                             bg='#313244', fg='#cdd6f4', insertbackground='#cdd6f4',
                             bd=0, font=('Consolas', 12))
        add_entry.pack(side=tk.LEFT, padx=(0, 8))
        add_entry.bind('<Return>', lambda e: add_plate())

        def add_plate():
            plate = add_var.get().strip().upper()
            if plate:
                content = text_area.get('1.0', 'end-1c')
                if content and not content.endswith('\n'):
                    text_area.insert('end', '\n')
                text_area.insert('end', plate + '\n')
                add_var.set('')
                text_area.see('end')
                update_count()

        tk.Button(add_frame, text="Add Plate", font=('Segoe UI', 10),
                  fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=12, pady=4,
                  cursor='hand2', command=add_plate).pack(side=tk.LEFT)

        # Bottom buttons
        btn_frame = tk.Frame(win, bg='#1e1e2e')
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        def save_and_close():
            content = text_area.get('1.0', 'end-1c')
            # Clean: strip blank lines, uppercase, remove dupes while preserving order
            plates = []
            seen = set()
            for line in content.splitlines():
                p = line.strip().upper()
                if p and p not in seen:
                    plates.append(p)
                    seen.add(p)
            with open(plate_list_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(plates) + '\n')
            win.destroy()

        def clear_all():
            text_area.delete('1.0', 'end')
            update_count()

        tk.Button(btn_frame, text="Save & Close", font=('Segoe UI', 10, 'bold'),
                  fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=16, pady=6,
                  cursor='hand2', command=save_and_close).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="Clear All", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#f38ba8', bd=0, padx=12, pady=6,
                  cursor='hand2', command=clear_all).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_frame, text="Cancel", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=12, pady=6,
                  cursor='hand2', command=win.destroy).pack(side=tk.RIGHT, padx=4)

        add_entry.focus()

    def _build_container(self):
        self._container = tk.Frame(self, bg='#1e1e2e')
        self._container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _switch_mode(self, mode: str):
        if mode == self._current_mode:
            return

        # Update nav button highlighting
        for key, btn in self._nav_buttons.items():
            if key == mode:
                btn.configure(bg='#313244')
            else:
                btn.configure(bg='#11111b')

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
