"""
Demo Mode — Live showcase runner with cache-driven display.
Smooth, professional, zero lag. Display layer only consumes from cache.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
from PIL import Image, ImageTk

ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')
OUTPUT_DIR = os.path.normpath(os.path.join(ROOT_DIR, 'output'))
SESSION_LOG_PATH = os.path.normpath(os.path.join(ROOT_DIR, 'data', 'session_log.json'))

SPEED_OPTIONS = {
    'Manual': 0,
    '0.5s': 500,
    '1s': 1000,
    '3s': 3000,
    '5s': 5000,
    '10s': 10000,
}


class DemoMode(tk.Frame):
    def __init__(self, parent, state, app):
        super().__init__(parent, bg='#0d0d14')
        self.state = state
        self.app = app
        self._cache_engine = None
        self._auto_timer = None
        self._current_image: Image.Image | None = None
        self._current_metadata: dict | None = None
        self._current_photo: ImageTk.PhotoImage | None = None
        self._is_running = False
        self._is_fullscreen = False

        self._show_library_selector()

    def _show_library_selector(self):
        self._clear()

        tk.Label(self, text="Select a Library to Demo",
                 font=('Segoe UI', 18, 'bold'), fg='#cdd6f4', bg='#0d0d14'
                 ).pack(pady=(60, 20))

        if not self.state.libraries:
            tk.Label(self, text="No libraries available.\nCreate one in Libraries mode first.",
                     font=('Segoe UI', 12), fg='#6c7086', bg='#0d0d14',
                     justify=tk.CENTER).pack(pady=20)
            return

        for lib in self.state.libraries:
            template_count = len(lib.get('template_ids', []))
            btn_text = f"{lib['name']}  ({template_count} templates)"
            tk.Button(self, text=btn_text, font=('Segoe UI', 12),
                      fg='#cdd6f4', bg='#313244', bd=0, padx=20, pady=10,
                      cursor='hand2', activebackground='#45475a',
                      activeforeground='#cdd6f4',
                      command=lambda lid=lib['id']: self._start_demo(lid)
                      ).pack(pady=4)

    def load_library(self, library_id: str):
        """Called externally when launched from Libraries mode."""
        self._start_demo(library_id)

    def _start_demo(self, library_id: str):
        """Initialize cache engine, prewarm, and start demo display."""
        lib = None
        for l in self.state.libraries:
            if l['id'] == library_id:
                lib = l
                break
        if not lib:
            messagebox.showerror("Error", "Library not found.")
            return

        # Resolve templates
        templates_by_id = {t['id']: t for t in self.state.templates}
        templates = []
        for tid in lib.get('template_ids', []):
            t = templates_by_id.get(tid)
            if t:
                templates.append({**t, 'enabled': True})

        if not templates:
            messagebox.showwarning("Empty", "This library has no valid templates.")
            return

        self._active_library = lib
        self._clear()

        # Show loading screen
        self._loading_label = tk.Label(self, text="Preparing demo...\nPre-warming cache",
                                        font=('Segoe UI', 14), fg='#f9e2af', bg='#0d0d14',
                                        justify=tk.CENTER)
        self._loading_label.pack(expand=True)
        self.update()

        # Initialize cache engine
        from engine.cache_engine import CacheEngine
        self._cache_engine = CacheEngine(
            templates=templates,
            asset_lookup=self.state.asset_cache,
            cycle_mode=lib.get('cycle_mode', 'sequential'),
        )

        # Prewarm
        self._cache_engine.prewarm(20)

        # Update library last_run
        lib['last_run'] = datetime.now(timezone.utc).isoformat()
        self.app.save_libraries()

        # Build demo UI
        self._build_demo_ui()

        # Start cache engine background thread
        self._cache_engine.start()

        # Show first image
        self._advance()

    def _build_demo_ui(self):
        self._clear()

        # Main canvas
        self._canvas = tk.Canvas(self, bg='#0d0d14', highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Overlay panel (top-right)
        self._overlay_frame = tk.Frame(self._canvas, bg='#11111bcc')
        self._overlay_window = self._canvas.create_window(
            10, 10, anchor='nw', window=self._overlay_frame
        )

        self._overlay_lib_name = tk.Label(self._overlay_frame, text="",
                                           font=('Segoe UI', 10, 'bold'),
                                           fg='#89b4fa', bg='#11111b')
        self._overlay_lib_name.pack(anchor='w', padx=8, pady=(4, 0))

        self._overlay_template = tk.Label(self._overlay_frame, text="",
                                           font=('Segoe UI', 9), fg='#cdd6f4', bg='#11111b')
        self._overlay_template.pack(anchor='w', padx=8)

        self._overlay_plate = tk.Label(self._overlay_frame, text="",
                                        font=('Segoe UI', 14, 'bold'),
                                        fg='#a6e3a1', bg='#11111b')
        self._overlay_plate.pack(anchor='w', padx=8)

        self._overlay_vehicle = tk.Label(self._overlay_frame, text="",
                                          font=('Segoe UI', 9), fg='#a6adc8', bg='#11111b')
        self._overlay_vehicle.pack(anchor='w', padx=8)

        self._overlay_cache = tk.Label(self._overlay_frame, text="Cache: --",
                                        font=('Segoe UI', 8), fg='#6c7086', bg='#11111b')
        self._overlay_cache.pack(anchor='w', padx=8, pady=(2, 4))

        self._overlay_lib_name.configure(text=self._active_library.get('name', ''))

        # Control bar (bottom)
        ctrl = tk.Frame(self, bg='#11111b', height=50)
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)
        ctrl.pack_propagate(False)

        tk.Button(ctrl, text="Prev", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=12, pady=4,
                  cursor='hand2', command=self._prev).pack(side=tk.LEFT, padx=4, pady=8)

        tk.Button(ctrl, text="Next", font=('Segoe UI', 10),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=12, pady=4,
                  cursor='hand2', command=self._advance).pack(side=tk.LEFT, padx=4, pady=8)

        self._play_btn = tk.Button(ctrl, text="Start", font=('Segoe UI', 10, 'bold'),
                                    fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=14, pady=4,
                                    cursor='hand2', command=self._toggle_auto)
        self._play_btn.pack(side=tk.LEFT, padx=4, pady=8)

        tk.Label(ctrl, text="Speed:", fg='#a6adc8', bg='#11111b',
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(12, 4))
        self._speed_var = tk.StringVar(value='3s')
        speed_combo = ttk.Combobox(ctrl, textvariable=self._speed_var,
                                   values=list(SPEED_OPTIONS.keys()),
                                   state='readonly', width=8)
        speed_combo.pack(side=tk.LEFT)

        # Right side controls
        tk.Button(ctrl, text="Fullscreen", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#45475a', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._toggle_fullscreen).pack(side=tk.RIGHT, padx=4, pady=8)

        tk.Button(ctrl, text="Export Batch", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#89b4fa', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._export_batch).pack(side=tk.RIGHT, padx=4, pady=8)

        tk.Button(ctrl, text="Export Current", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#89b4fa', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._export_current).pack(side=tk.RIGHT, padx=4, pady=8)

        tk.Button(ctrl, text="Back", font=('Segoe UI', 9),
                  fg='#cdd6f4', bg='#f38ba8', bd=0, padx=10, pady=4,
                  cursor='hand2', command=self._exit_demo).pack(side=tk.RIGHT, padx=4, pady=8)

        # Keyboard bindings
        self.winfo_toplevel().bind('<Right>', lambda e: self._advance())
        self.winfo_toplevel().bind('<Left>', lambda e: self._prev())
        self.winfo_toplevel().bind('<space>', lambda e: self._toggle_auto())
        self.winfo_toplevel().bind('<F11>', lambda e: self._toggle_fullscreen())
        self.winfo_toplevel().bind('<Escape>', lambda e: self._exit_fullscreen())

        # Update cache indicator periodically
        self._update_cache_indicator()

    def _advance(self):
        """Display next image from cache."""
        if not self._cache_engine:
            return

        result = self._cache_engine.get_next()
        if result:
            self._display(result[0], result[1])
        # else: hold current frame (cache empty)

    def _prev(self):
        """Display previous image from history."""
        if not self._cache_engine:
            return

        result = self._cache_engine.get_prev()
        if result:
            self._display(result[0], result[1])

    def _display(self, image: Image.Image, metadata: dict):
        """Show image on canvas and update overlay."""
        self._current_image = image
        self._current_metadata = metadata

        # Scale to canvas
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 1200, 750

        scale = min(cw / image.width, ch / image.height, 1.0)
        disp_w = int(image.width * scale)
        disp_h = int(image.height * scale)

        display_img = image.resize((disp_w, disp_h), Image.LANCZOS)
        self._current_photo = ImageTk.PhotoImage(display_img)

        self._canvas.delete('display')
        self._canvas.create_image(cw // 2, ch // 2, anchor='center',
                                  image=self._current_photo, tags='display')

        # Raise overlay above image
        self._canvas.tag_raise(self._overlay_window)

        # Update overlay
        self._overlay_template.configure(text=metadata.get('template_name', ''))
        self._overlay_plate.configure(text=metadata.get('plate_text', ''))
        self._overlay_vehicle.configure(text=metadata.get('vehicle_info', ''))

        # Log to session
        self._log_session(metadata)

        # Write to vault
        self._write_vault(image, metadata)

    def _log_session(self, metadata: dict):
        """Append to session log."""
        entry = {
            'template_id': metadata.get('template_id', ''),
            'vehicle_id': metadata.get('vehicle_id', ''),
            'plate_text': metadata.get('plate_text', ''),
            'state': metadata.get('state', ''),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        log = []
        if os.path.isfile(SESSION_LOG_PATH):
            try:
                with open(SESSION_LOG_PATH, 'r', encoding='utf-8') as f:
                    log = json.load(f)
            except (json.JSONDecodeError, IOError):
                log = []

        log.append(entry)
        with open(SESSION_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2)

    def _write_vault(self, image: Image.Image, metadata: dict):
        """Save to vault for reuse."""
        from engine.cache_engine import write_to_vault
        try:
            write_to_vault(metadata['template_id'], metadata['plate_text'], image)

            # Increment vault_count on template
            for t in self.state.templates:
                if t['id'] == metadata['template_id']:
                    t['vault_count'] = t.get('vault_count', 0) + 1
                    break
        except Exception:
            pass

    def _toggle_auto(self):
        if self._is_running:
            self._stop_auto()
        else:
            self._start_auto()

    def _start_auto(self):
        self._is_running = True
        self._play_btn.configure(text="Stop", bg='#f38ba8')
        self._auto_cycle()

    def _stop_auto(self):
        self._is_running = False
        self._play_btn.configure(text="Start", bg='#a6e3a1')
        if self._auto_timer:
            self.after_cancel(self._auto_timer)
            self._auto_timer = None

    def _auto_cycle(self):
        if not self._is_running:
            return
        self._advance()
        speed_ms = SPEED_OPTIONS.get(self._speed_var.get(), 3000)
        if speed_ms > 0:
            self._auto_timer = self.after(speed_ms, self._auto_cycle)

    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        self.winfo_toplevel().attributes('-fullscreen', self._is_fullscreen)

    def _exit_fullscreen(self):
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.winfo_toplevel().attributes('-fullscreen', False)

    def _export_current(self):
        if not self._current_image or not self._current_metadata:
            return

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        meta = self._current_metadata
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        plate = meta.get('plate_text', 'UNKNOWN').replace('-', '')
        vid = meta.get('vehicle_id', 'unknown')
        fname = f"{plate}_{vid}_{timestamp}.png"
        path = os.path.join(OUTPUT_DIR, fname)
        self._current_image.save(path, 'PNG')
        messagebox.showinfo("Exported", f"Saved: {fname}")

    def _export_batch(self):
        if not self._cache_engine:
            return

        count_str = tk.simpledialog.askstring("Export Batch", "Number of images to export:",
                                               parent=self) if hasattr(tk, 'simpledialog') else None
        if not count_str:
            # Fallback: use a simple dialog
            win = tk.Toplevel(self)
            win.title("Export Batch")
            win.geometry("300x100")
            win.configure(bg='#1e1e2e')
            win.transient(self)

            tk.Label(win, text="Number of images:", fg='#cdd6f4', bg='#1e1e2e',
                     font=('Segoe UI', 10)).pack(pady=(12, 4))
            count_var = tk.StringVar(value='20')
            entry = tk.Entry(win, textvariable=count_var, width=10, bg='#313244',
                             fg='#cdd6f4', insertbackground='#cdd6f4', bd=0)
            entry.pack()
            entry.focus()

            def do_export():
                try:
                    count = int(count_var.get())
                except ValueError:
                    return
                win.destroy()
                self._run_batch_export(count)

            tk.Button(win, text="Export", font=('Segoe UI', 10, 'bold'),
                      fg='#1e1e2e', bg='#a6e3a1', bd=0, padx=12, pady=4,
                      command=do_export).pack(pady=8)
            return

    def _run_batch_export(self, count: int):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Progress window
        prog_win = tk.Toplevel(self)
        prog_win.title("Exporting...")
        prog_win.geometry("350x80")
        prog_win.configure(bg='#1e1e2e')
        prog_win.transient(self)

        prog_label = tk.Label(prog_win, text="Exporting 0/{count}...",
                               fg='#cdd6f4', bg='#1e1e2e', font=('Segoe UI', 10))
        prog_label.pack(pady=(12, 4))
        prog_bar = ttk.Progressbar(prog_win, maximum=count, length=300)
        prog_bar.pack(pady=4)

        def export_next(i):
            if i >= count:
                prog_win.destroy()
                messagebox.showinfo("Done", f"Exported {count} images to output/")
                return

            result = self._cache_engine.get_next()
            if result:
                image, meta = result
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                plate = meta.get('plate_text', 'UNKNOWN').replace('-', '')
                vid = meta.get('vehicle_id', 'unknown')
                fname = f"{plate}_{vid}_{timestamp}.png"
                image.save(os.path.join(OUTPUT_DIR, fname), 'PNG')

            prog_label.configure(text=f"Exporting {i + 1}/{count}...")
            prog_bar['value'] = i + 1
            self.after(10, lambda: export_next(i + 1))

        export_next(0)

    def _update_cache_indicator(self):
        if self._cache_engine and hasattr(self, '_overlay_cache'):
            depth = self._cache_engine.queue_depth()
            self._overlay_cache.configure(text=f"Cache: {depth}/20")
        if self.winfo_exists():
            self.after(1000, self._update_cache_indicator)

    def _exit_demo(self):
        """Stop cache engine and return to library selector."""
        self._stop_auto()
        if self._cache_engine:
            self._cache_engine.stop()
            self._cache_engine = None

        # Unbind keyboard shortcuts
        self.winfo_toplevel().unbind('<Right>')
        self.winfo_toplevel().unbind('<Left>')
        self.winfo_toplevel().unbind('<space>')
        self.winfo_toplevel().unbind('<F11>')
        self.winfo_toplevel().unbind('<Escape>')

        self._exit_fullscreen()
        self._show_library_selector()

    def _clear(self):
        self._stop_auto()
        for widget in self.winfo_children():
            widget.destroy()

    def _stop_auto(self):
        self._is_running = False
        if self._auto_timer:
            self.after_cancel(self._auto_timer)
            self._auto_timer = None

    def destroy(self):
        """Clean up on frame destruction."""
        self._stop_auto()
        if self._cache_engine:
            self._cache_engine.stop()
        # Unbind keyboard shortcuts safely
        try:
            self.winfo_toplevel().unbind('<Right>')
            self.winfo_toplevel().unbind('<Left>')
            self.winfo_toplevel().unbind('<space>')
            self.winfo_toplevel().unbind('<F11>')
            self.winfo_toplevel().unbind('<Escape>')
        except Exception:
            pass
        super().destroy()
