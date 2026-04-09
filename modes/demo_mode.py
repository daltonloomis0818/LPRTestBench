"""
Demo Mode — Live showcase runner with cache-driven display.
Smooth, professional, zero lag. Display layer only consumes from cache.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from datetime import datetime, timezone
from PIL import Image, ImageTk

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

OUTPUT_DIR = os.path.normpath(os.path.join(_BASE_DIR, 'output'))
SESSION_LOG_PATH = os.path.normpath(os.path.join(_BASE_DIR, 'data', 'session_log.json'))
LOGO_PATH = os.path.normpath(os.path.join(_BASE_DIR, 'assets', 'overlays', 'patriot_lpr_logo.png'))

SPEED_OPTIONS = {
    'Manual': 0,
    '0.5s': 500,
    '1s': 1000,
    '3s': 3000,
    '5s': 5000,
    '10s': 10000,
}


class DemoMode(ctk.CTkFrame):
    def __init__(self, parent, state, app):
        super().__init__(parent, fg_color='#0d0d14')
        self.state = state
        self.app = app
        self._cache_engine = None
        self._auto_timer = None
        self._current_image: Image.Image | None = None
        self._current_metadata: dict | None = None
        self._current_photo: ImageTk.PhotoImage | None = None
        self._is_running = False
        self._is_fullscreen = False
        self._overlay_visible = True
        self._overlay_hide_timer = None
        self._ctrl_frame = None
        self._configure_redraw_timer = None
        self._corner_logo_photo: ImageTk.PhotoImage | None = None
        self._corner_logo_pil: Image.Image | None = None

        self._show_library_selector()

    def _show_library_selector(self):
        self._clear()

        # Patriot LPR logo — splash
        try:
            if os.path.isfile(LOGO_PATH):
                logo_img = Image.open(LOGO_PATH).convert('RGBA')
                # Scale logo up for prominent splash display
                target_w = 320
                ratio = target_w / logo_img.width
                target_h = int(logo_img.height * ratio)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img,
                                        size=(target_w, target_h))
                logo_label = ctk.CTkLabel(self, image=logo_ctk, text="",
                                          fg_color="transparent")
                # Keep strong ref so GC doesn't drop it
                logo_label.image = logo_ctk
                logo_label.pack(pady=(50, 10))
        except Exception:
            pass

        ctk.CTkLabel(self, text="Select a Library to Demo",
                     font=('Segoe UI', 18, 'bold'), text_color='#e0e0e8',
                     fg_color="transparent").pack(pady=(10, 20))

        if not self.state.libraries:
            ctk.CTkLabel(self, text="No libraries available.\nCreate one in Libraries mode first.",
                         font=('Segoe UI', 12), text_color='#555570', fg_color="transparent",
                         justify=tk.CENTER).pack(pady=20)
            return

        for lib in self.state.libraries:
            template_count = len(lib.get('template_ids', []))
            btn_text = f"{lib['name']}  ({template_count} templates)"
            ctk.CTkButton(self, text=btn_text, font=('Segoe UI', 12),
                          text_color='#e0e0e8', fg_color='#1a1a2e', hover_color='#242438',
                          corner_radius=8, cursor='hand2',
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

        # Verify all template assets exist
        missing = []
        for t in templates:
            asset = self.state.asset_cache.get(t.get('vehicle_id'))
            if not asset:
                missing.append(t.get('name', t['id'][:8]))
            else:
                import os as _os
                vpath = _os.path.join(_os.path.normpath(
                    _os.path.join(_BASE_DIR, 'assets', 'vehicles')), asset['filename'])
                if not _os.path.isfile(vpath):
                    missing.append(f"{t.get('name', '')} (file missing: {asset['filename']})")
        if missing:
            messagebox.showerror("Missing Assets",
                                 f"These templates reference missing assets:\n" +
                                 "\n".join(f"  - {m}" for m in missing))
            return

        self._active_library = lib
        self._clear()

        # Show loading screen with progress
        self._loading_label = ctk.CTkLabel(self, text="Preparing demo...\nPre-warming cache (0/10)",
                                            font=('Segoe UI', 14), text_color='#8888a0',
                                            fg_color="transparent", justify=tk.CENTER)
        self._loading_label.pack(expand=True)

        self._loading_back_btn = ctk.CTkButton(self, text="Cancel", font=('Segoe UI', 10),
                                                text_color='#ffffff', fg_color='#dc2626',
                                                hover_color='#b91c1c', corner_radius=8,
                                                cursor='hand2', command=self._show_library_selector)
        self._loading_back_btn.pack(pady=8)
        self.update()

        # Initialize cache engine
        try:
            from engine.cache_engine import CacheEngine
            self._cache_engine = CacheEngine(
                templates=templates,
                asset_lookup=self.state.asset_cache,
                cycle_mode=lib.get('cycle_mode', 'sequential'),
            )
        except Exception as e:
            messagebox.showerror("Engine Error", f"Failed to initialize cache engine:\n{e}")
            self._show_library_selector()
            return

        # Prewarm on background thread so UI stays responsive
        self._prewarm_done = False
        self._prewarm_error = None
        import threading
        threading.Thread(target=self._prewarm_worker, args=(10,), daemon=True).start()
        self._poll_prewarm(lib)

    def _prewarm_worker(self, count: int):
        """Run prewarm on background thread."""
        try:
            self._cache_engine.prewarm(count)
            self._prewarm_done = True
        except Exception as e:
            self._prewarm_error = str(e)
            self._prewarm_done = True

    def _poll_prewarm(self, lib: dict):
        """Poll for prewarm completion without blocking UI."""
        if self._prewarm_error:
            messagebox.showerror("Prewarm Error", f"Failed to generate images:\n{self._prewarm_error}")
            self._show_library_selector()
            return

        if not self._prewarm_done:
            depth = self._cache_engine.queue_depth() if self._cache_engine else 0
            if hasattr(self, '_loading_label') and self._loading_label.winfo_exists():
                self._loading_label.configure(text=f"Preparing demo...\nPre-warming cache ({depth}/10)")
            self.after(100, lambda: self._poll_prewarm(lib))
            return

        # Prewarm complete — launch demo
        depth = self._cache_engine.queue_depth() if self._cache_engine else 0
        if depth == 0:
            messagebox.showwarning("No Images",
                                   "Cache engine could not generate any images.\n"
                                   "Check that your templates reference valid registered assets.")
            self._show_library_selector()
            return

        lib['last_run'] = datetime.now(timezone.utc).isoformat()
        self.app.save_libraries()

        try:
            self._build_demo_ui()
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to build demo UI:\n{e}")
            self._show_library_selector()
            return

        self._cache_engine.start()
        self._advance()

    def _build_demo_ui(self):
        self._clear()
        self._overlay_visible = True

        # Ensure this frame actually expands in its parent container
        self.pack(fill=tk.BOTH, expand=True)

        # Main canvas — fills everything
        self._canvas = tk.Canvas(self, bg='#000000', highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # ── Persistent Patriot LPR corner logo (top-right) ──
        self._corner_logo_photo = None
        self._corner_logo_pil = None
        try:
            if os.path.isfile(LOGO_PATH):
                self._corner_logo_pil = Image.open(LOGO_PATH).convert('RGBA')
        except Exception:
            self._corner_logo_pil = None

        # ── Info overlay (top-left, floats over canvas) ──
        self._overlay_frame = ctk.CTkFrame(self._canvas, fg_color='#000000',
                                            corner_radius=10, bg_color='#000000')
        self._overlay_frame.configure(fg_color=('#1a1a2e', '#1a1a2e'))
        self._info_window = self._canvas.create_window(
            12, 12, anchor='nw', window=self._overlay_frame
        )

        self._overlay_lib_name = ctk.CTkLabel(self._overlay_frame, text="",
                                               font=('Segoe UI', 11, 'bold'),
                                               text_color='#ffffff', fg_color="transparent")
        self._overlay_lib_name.pack(anchor='w', padx=10, pady=(6, 0))

        self._overlay_plate = ctk.CTkLabel(self._overlay_frame, text="",
                                            font=('Segoe UI', 18, 'bold'),
                                            text_color='#4a9eff', fg_color="transparent")
        self._overlay_plate.pack(anchor='w', padx=10)

        self._overlay_vehicle = ctk.CTkLabel(self._overlay_frame, text="",
                                              font=('Segoe UI', 9), text_color='#8888a0',
                                              fg_color="transparent")
        self._overlay_vehicle.pack(anchor='w', padx=10)

        self._overlay_cache = ctk.CTkLabel(self._overlay_frame, text="",
                                            font=('Segoe UI', 8), text_color='#555570',
                                            fg_color="transparent")
        self._overlay_cache.pack(anchor='w', padx=10, pady=(0, 6))

        self._overlay_lib_name.configure(text=self._active_library.get('name', ''))

        # ── Control bar (bottom, floats over canvas) ──
        self._ctrl_frame = ctk.CTkFrame(self._canvas, fg_color='#1a1a2e',
                                         corner_radius=12, height=52)
        self._ctrl_window = self._canvas.create_window(
            0, 0, anchor='s', window=self._ctrl_frame  # positioned in _reposition_controls
        )

        self._speed_var = tk.StringVar(value='3s')

        # Left controls
        ctk.CTkButton(self._ctrl_frame, text="< Back", width=70,
                      font=('Segoe UI', 10), text_color='#ffffff',
                      fg_color='#dc2626', hover_color='#b91c1c',
                      corner_radius=8, command=self._exit_demo
                      ).pack(side=tk.LEFT, padx=(10, 16), pady=8)

        ctk.CTkButton(self._ctrl_frame, text="Prev", width=60,
                      font=('Segoe UI', 10), text_color='#e0e0e8',
                      fg_color='#2d2d44', hover_color='#3d3d5c',
                      corner_radius=8, command=self._prev
                      ).pack(side=tk.LEFT, padx=3, pady=8)

        self._play_btn = ctk.CTkButton(self._ctrl_frame, text="Start", width=80,
                                        font=('Segoe UI', 11, 'bold'),
                                        text_color='#ffffff', fg_color='#1e3a5f',
                                        hover_color='#264d80', corner_radius=8,
                                        command=self._toggle_auto)
        self._play_btn.pack(side=tk.LEFT, padx=3, pady=8)

        ctk.CTkButton(self._ctrl_frame, text="Next", width=60,
                      font=('Segoe UI', 10), text_color='#e0e0e8',
                      fg_color='#2d2d44', hover_color='#3d3d5c',
                      corner_radius=8, command=self._advance
                      ).pack(side=tk.LEFT, padx=3, pady=8)

        # Speed
        ctk.CTkLabel(self._ctrl_frame, text="Speed:", text_color='#8888a0',
                     fg_color="transparent", font=('Segoe UI', 9)
                     ).pack(side=tk.LEFT, padx=(12, 2))
        ctk.CTkComboBox(self._ctrl_frame, variable=self._speed_var,
                        values=list(SPEED_OPTIONS.keys()),
                        state='readonly', width=85,
                        fg_color='#242438', text_color='#e0e0e8',
                        border_color='#2d2d44', button_color='#2d2d44',
                        dropdown_fg_color='#242438', dropdown_text_color='#e0e0e8',
                        dropdown_hover_color='#1e3a5f'
                        ).pack(side=tk.LEFT, padx=3)

        # Right controls
        ctk.CTkButton(self._ctrl_frame, text="Fullscreen", width=90,
                      font=('Segoe UI', 9), text_color='#e0e0e8',
                      fg_color='#2d2d44', hover_color='#3d3d5c',
                      corner_radius=8, command=self._toggle_fullscreen
                      ).pack(side=tk.RIGHT, padx=(3, 10), pady=8)

        ctk.CTkButton(self._ctrl_frame, text="Export Batch", width=100,
                      font=('Segoe UI', 9), text_color='#ffffff',
                      fg_color='#1e3a5f', hover_color='#264d80',
                      corner_radius=8, command=self._export_batch
                      ).pack(side=tk.RIGHT, padx=3, pady=8)

        ctk.CTkButton(self._ctrl_frame, text="Export Current", width=110,
                      font=('Segoe UI', 9), text_color='#ffffff',
                      fg_color='#1e3a5f', hover_color='#264d80',
                      corner_radius=8, command=self._export_current
                      ).pack(side=tk.RIGHT, padx=3, pady=8)

        # ── Mouse motion shows overlays, inactivity hides them ──
        self._canvas.bind('<Motion>', self._on_mouse_move)
        self._canvas.bind('<Configure>', self._on_canvas_configure)

        # Keyboard bindings
        self.winfo_toplevel().bind('<Right>', lambda e: self._advance())
        self.winfo_toplevel().bind('<Left>', lambda e: self._prev())
        self.winfo_toplevel().bind('<space>', lambda e: self._toggle_auto())
        self.winfo_toplevel().bind('<F11>', lambda e: self._toggle_fullscreen())
        self.winfo_toplevel().bind('<Escape>', lambda e: self._exit_fullscreen())

        # Position controls and start auto-hide timer
        self.after(100, self._reposition_controls)
        self._schedule_overlay_hide()
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
        """Show image on canvas, update overlay, log, and write to vault.

        Side-effects (log + vault) happen here. Pure redraw lives in
        _render_current_image so Configure/fullscreen rescales don't
        duplicate logs.
        """
        self._current_image = image
        self._current_metadata = metadata
        self._render_current_image()

        # Log to session
        self._log_session(metadata)

        # Write to vault
        self._write_vault(image, metadata)

    def _render_current_image(self):
        """Idempotent canvas redraw of the current image at current canvas size.

        Safe to call from Configure events, fullscreen toggles, etc. — does
        NOT log or write to vault. Fits image to the full canvas, upscaling
        when needed so fullscreen actually fills the screen.
        """
        if self._current_image is None or not hasattr(self, '_canvas'):
            return
        try:
            if not self._canvas.winfo_exists():
                return
        except Exception:
            return

        image = self._current_image
        metadata = self._current_metadata or {}

        # Flush pending geometry so winfo_width/height reflect reality
        try:
            self._canvas.update_idletasks()
        except Exception:
            pass

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 1200, 750

        # Fit to canvas — allow upscaling (no 1.0 clamp) so fullscreen fills
        scale = min(cw / image.width, ch / image.height)
        disp_w = max(1, int(image.width * scale))
        disp_h = max(1, int(image.height * scale))

        try:
            display_img = image.resize((disp_w, disp_h), Image.LANCZOS)
            self._current_photo = ImageTk.PhotoImage(display_img)
        except Exception:
            return

        self._canvas.delete('display')
        self._canvas.create_image(cw // 2, ch // 2, anchor='center',
                                  image=self._current_photo, tags='display')

        # Redraw persistent corner logo (sized proportional to canvas)
        self._draw_corner_logo(cw, ch)

        # Raise overlays above image + logo
        try:
            if hasattr(self, '_info_window'):
                self._canvas.tag_raise(self._info_window)
            if hasattr(self, '_ctrl_window'):
                self._canvas.tag_raise(self._ctrl_window)
        except Exception:
            pass

        # Update overlay text (cheap — no side effects)
        if hasattr(self, '_overlay_plate'):
            self._overlay_plate.configure(text=metadata.get('plate_text', ''))
        if hasattr(self, '_overlay_vehicle'):
            self._overlay_vehicle.configure(
                text=f"{metadata.get('template_name', '')}  —  {metadata.get('vehicle_info', '')}"
            )

    def _draw_corner_logo(self, cw: int, ch: int):
        """Draw Patriot LPR logo in the top-right corner of the demo canvas.

        Scales with canvas size so it stays prominent in fullscreen but
        subtle in windowed mode.
        """
        if self._corner_logo_pil is None:
            return
        try:
            # Target width: ~9% of canvas width, clamped to sensible range
            target_w = max(90, min(220, int(cw * 0.09)))
            ratio = target_w / self._corner_logo_pil.width
            target_h = max(1, int(self._corner_logo_pil.height * ratio))

            logo_resized = self._corner_logo_pil.resize(
                (target_w, target_h), Image.LANCZOS
            )
            self._corner_logo_photo = ImageTk.PhotoImage(logo_resized)

            self._canvas.delete('corner_logo')
            pad = 18
            self._canvas.create_image(
                cw - pad, pad, anchor='ne',
                image=self._corner_logo_photo, tags='corner_logo'
            )
        except Exception:
            pass

    def _on_canvas_configure(self, event=None):
        """Handle canvas resize — reposition controls + debounce redraw."""
        self._reposition_controls()
        # Debounce rescale: collapse rapid Configure bursts during fullscreen
        # transitions into a single redraw once the size settles.
        if self._configure_redraw_timer is not None:
            try:
                self.after_cancel(self._configure_redraw_timer)
            except Exception:
                pass
        self._configure_redraw_timer = self.after(60, self._render_current_image)

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
        self._play_btn.configure(text="Stop", fg_color='#dc2626', text_color='#ffffff')
        self._auto_cycle()

    def _auto_cycle(self):
        if not self._is_running:
            return
        self._advance()
        speed_ms = SPEED_OPTIONS.get(self._speed_var.get(), 3000)
        if speed_ms > 0:
            self._auto_timer = self.after(speed_ms, self._auto_cycle)

    def _on_mouse_move(self, event=None):
        """Show overlays on mouse movement, schedule hide."""
        if not self._overlay_visible:
            self._show_overlays()
        self._schedule_overlay_hide()

    def _schedule_overlay_hide(self):
        """Hide overlays after 3 seconds of no mouse movement."""
        if self._overlay_hide_timer:
            self.after_cancel(self._overlay_hide_timer)
        self._overlay_hide_timer = self.after(3000, self._hide_overlays)

    def _show_overlays(self):
        """Fade in the info and control overlays."""
        self._overlay_visible = True
        if hasattr(self, '_info_window'):
            self._canvas.itemconfigure(self._info_window, state='normal')
        if hasattr(self, '_ctrl_window'):
            self._canvas.itemconfigure(self._ctrl_window, state='normal')

    def _hide_overlays(self):
        """Fade out the info and control overlays."""
        self._overlay_visible = False
        if hasattr(self, '_info_window'):
            self._canvas.itemconfigure(self._info_window, state='hidden')
        if hasattr(self, '_ctrl_window'):
            self._canvas.itemconfigure(self._ctrl_window, state='hidden')

    def _reposition_controls(self):
        """Keep the control bar centered at the bottom of the canvas."""
        if not hasattr(self, '_ctrl_window') or not hasattr(self, '_canvas'):
            return
        try:
            cw = self._canvas.winfo_width()
            ch = self._canvas.winfo_height()
            if cw > 10 and ch > 10:
                self._canvas.coords(self._ctrl_window, cw // 2, ch - 16)
        except Exception:
            pass

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._is_fullscreen = True
        top = self.winfo_toplevel()
        # Save current geometry to restore later
        self._pre_fs_geometry = top.geometry()
        # Hide nav bar
        if hasattr(self.app, '_nav_frame'):
            self.app._nav_frame.pack_forget()
        # True fullscreen — covers taskbar and everything
        top.attributes('-fullscreen', True)
        top.attributes('-topmost', True)
        top.after(200, lambda: top.attributes('-topmost', False))
        # Force geometry propagation so winfo_width/height reflect fullscreen
        try:
            top.update_idletasks()
            self._canvas.update_idletasks()
        except Exception:
            pass
        # Redraw at new canvas size — multiple passes as belt-and-suspenders
        # because -fullscreen attribute application is async on Windows.
        self.after(50, self._reposition_controls)
        self.after(60, self._render_current_image)
        self.after(200, self._render_current_image)
        self.after(400, self._render_current_image)

    def _exit_fullscreen(self):
        if not self._is_fullscreen:
            return
        self._is_fullscreen = False
        top = self.winfo_toplevel()
        top.attributes('-fullscreen', False)
        # Restore nav bar
        if hasattr(self.app, '_nav_frame'):
            self.app._nav_frame.pack(side=tk.TOP, fill=tk.X, before=self.app._container)
        # Restore previous geometry
        if hasattr(self, '_pre_fs_geometry'):
            top.geometry(self._pre_fs_geometry)
        try:
            top.update_idletasks()
            self._canvas.update_idletasks()
        except Exception:
            pass
        self.after(50, self._reposition_controls)
        self.after(60, self._render_current_image)
        self.after(200, self._render_current_image)

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
            win = ctk.CTkToplevel(self)
            win.title("Export Batch")
            win.geometry("300x120")
            win.configure(fg_color='#0d0d14')
            win.transient(self)

            ctk.CTkLabel(win, text="Number of images:", text_color='#e0e0e8',
                         fg_color="transparent", font=('Segoe UI', 10)).pack(pady=(12, 4))
            count_var = tk.StringVar(value='20')
            entry = ctk.CTkEntry(win, textvariable=count_var, width=100,
                                 fg_color='#242438', text_color='#e0e0e8',
                                 border_color='#2d2d44')
            entry.pack()
            entry.focus()

            def do_export():
                try:
                    count = int(count_var.get())
                except ValueError:
                    return
                win.destroy()
                self._run_batch_export(count)

            ctk.CTkButton(win, text="Export", font=('Segoe UI', 10, 'bold'),
                          text_color='#ffffff', fg_color='#1e3a5f', hover_color='#2d2d44',
                          corner_radius=8, command=do_export).pack(pady=8)
            return

    def _run_batch_export(self, count: int):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Progress window
        prog_win = ctk.CTkToplevel(self)
        prog_win.title("Exporting...")
        prog_win.geometry("350x100")
        prog_win.configure(fg_color='#0d0d14')
        prog_win.transient(self)

        prog_label = ctk.CTkLabel(prog_win, text=f"Exporting 0/{count}...",
                                   text_color='#e0e0e8', fg_color="transparent",
                                   font=('Segoe UI', 10))
        prog_label.pack(pady=(12, 4))
        prog_bar = ctk.CTkProgressBar(prog_win, width=300,
                                       progress_color='#1e3a5f',
                                       fg_color='#242438')
        prog_bar.pack(pady=4)
        prog_bar.set(0.0)

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
            prog_bar.set((i + 1) / count)
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
        if hasattr(self, '_play_btn') and self._play_btn.winfo_exists():
            self._play_btn.configure(text="Start", fg_color='#1e3a5f', text_color='#ffffff')

    def destroy(self):
        """Clean up on frame destruction."""
        self._stop_auto()
        if self._configure_redraw_timer is not None:
            try:
                self.after_cancel(self._configure_redraw_timer)
            except Exception:
                pass
            self._configure_redraw_timer = None
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
