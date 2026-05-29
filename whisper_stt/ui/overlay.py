"""Floating overlay for real-time transcription preview."""
import threading
import tkinter as tk


class TranscriptionOverlay:
    """Borderless always-on-top window that shows live transcription text.

    Runs tkinter in a daemon thread. Updates are posted from any thread via
    update_text() / set_status() and applied by the poll loop every 120 ms.
    """

    def __init__(self):
        self._root = None
        self._label = None
        self._status_lbl = None
        self._lock = threading.Lock()
        self._text = ""
        self._status_text = "🎙  Listening..."
        self._status_color = "#e05252"
        self._running = False

    # ── Public API (call from any thread) ─────────────────────────────────────

    def show(self):
        """Display the overlay. Non-blocking."""
        self._running = True
        self._text = ""
        self._status_text = "🎙  Listening..."
        self._status_color = "#e05252"
        threading.Thread(target=self._run, daemon=True).start()

    def update_text(self, text: str):
        with self._lock:
            self._text = text

    def set_status(self, text: str, color: str = "#e0b352"):
        with self._lock:
            self._status_text = text
            self._status_color = color

    def hide(self):
        self._running = False

    # ── Tkinter thread ────────────────────────────────────────────────────────

    def _run(self):
        root = tk.Tk()
        self._root = root

        root.overrideredirect(True)           # no title bar / borders
        root.wm_attributes('-topmost', True)  # always above other windows
        root.wm_attributes('-alpha', 0.92)
        root.configure(bg='#1e1e3a')

        # Thin accent bar at top
        tk.Frame(root, bg='#e05252', height=3).pack(fill='x')

        inner = tk.Frame(root, bg='#1e1e3a', padx=18, pady=10)
        inner.pack(fill='both', expand=True)

        # Status line (Recording / Processing)
        self._status_lbl = tk.Label(
            inner,
            text=self._status_text,
            bg='#1e1e3a',
            fg=self._status_color,
            font=('Segoe UI', 9, 'bold'),
            anchor='w',
        )
        self._status_lbl.pack(fill='x')

        # Horizontal rule
        tk.Frame(inner, bg='#2e2e5a', height=1).pack(fill='x', pady=(5, 8))

        # Live transcription text
        self._label = tk.Label(
            inner,
            text='',
            bg='#1e1e3a',
            fg='#d4d4ff',
            font=('Segoe UI', 13),
            anchor='w',
            justify='left',
            wraplength=660,
        )
        self._label.pack(fill='x')

        # Bottom breathing room
        tk.Frame(inner, bg='#1e1e3a', height=4).pack()

        root.update_idletasks()
        self._reposition()

        # WS_EX_NOACTIVATE — prevents the overlay from stealing keyboard focus
        try:
            import ctypes
            hwnd = root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            ctypes.windll.user32.SetWindowLongW(
                hwnd, -20,
                style | 0x08000000 | 0x00000080,  # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

        root.after(120, self._poll)
        root.mainloop()

    def _reposition(self):
        r = self._root
        r.update_idletasks()
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        w = min(720, int(sw * 0.62))
        h = r.winfo_reqheight()
        r.geometry(f'{w}x{h}+{(sw - w) // 2}+{sh - h - 72}')

    def _poll(self):
        if not self._running:
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        with self._lock:
            text = self._text
            st = self._status_text
            sc = self._status_color

        try:
            self._label.config(text=text)
            self._status_lbl.config(text=st, fg=sc)
            self._reposition()
        except Exception:
            pass

        self._root.after(120, self._poll)
