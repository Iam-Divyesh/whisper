"""Compact black-and-green glassmorphic recording overlay."""
import threading
import random
import tkinter as tk

# ── Design tokens ──────────────────────────────────────────────────────────────
_W         = 420        # overlay width (compact)
_BAR_N     = 22         # fewer bars → smaller footprint
_BAR_W     = 4
_BAR_GAP   = 4
_CANVAS_H  = 38         # shorter waveform area
_BG        = "#0a0a0a"  # near-black
_ACCENT    = "#9e9e9e"  # medium gray accent
_BAR_DIM   = "#424242"  # dark gray bars at rest
_TEXT_CLR  = "#e0e0e0"  # light gray text
_SUB_CLR   = "#616161"  # dim gray


class TranscriptionOverlay:
    """Borderless acrylic overlay.  Thread-safe — call from any thread."""

    def __init__(self):
        self._root        = None
        self._lock        = threading.Lock()
        self._text        = ""
        self._running     = False
        self._bar_h       = [1.5] * _BAR_N
        self._bar_tgt     = [1.5] * _BAR_N
        self._canvas      = None
        self._bar_ids     = []
        self._text_lbl    = None
        self._accent_strip = None
        self._dot_canvas  = None
        self._dot_oval    = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def show(self):
        self._running = True
        self._text    = ""
        self._bar_h   = [1.5] * _BAR_N
        self._bar_tgt = [1.5] * _BAR_N
        threading.Thread(target=self._run, daemon=True).start()

    def update_text(self, text: str):
        with self._lock:
            self._text = text

    def hide(self):
        self._running = False

    # ── Tkinter thread ─────────────────────────────────────────────────────────

    def _run(self):
        root = tk.Tk()
        self._root = root
        root.overrideredirect(True)
        root.wm_attributes('-topmost', True)
        root.wm_attributes('-alpha', 0.0)
        root.configure(bg=_BG)

        # 2-px gray top bar
        self._accent_strip = tk.Frame(root, bg=_ACCENT, height=2)
        self._accent_strip.pack(fill='x')

        # Header: dot + label
        hdr = tk.Frame(root, bg=_BG, padx=12, pady=6)
        hdr.pack(fill='x')

        self._dot_canvas = tk.Canvas(hdr, width=8, height=8, bg=_BG, highlightthickness=0)
        self._dot_canvas.pack(side='left')
        self._dot_oval = self._dot_canvas.create_oval(1, 1, 7, 7, fill=_ACCENT, outline='')

        tk.Label(
            hdr, text="Listening...",
            bg=_BG, fg=_ACCENT,
            font=('Consolas', 8, 'bold'),
        ).pack(side='left', padx=6)

        # Waveform canvas
        total_px  = _BAR_N * _BAR_W + (_BAR_N - 1) * _BAR_GAP
        cv_w      = _W - 24
        self._canvas = tk.Canvas(root, width=cv_w, height=_CANVAS_H,
                                  bg=_BG, highlightthickness=0)
        self._canvas.pack(padx=12)

        offset_x = (cv_w - total_px) // 2
        cy        = _CANVAS_H // 2
        self._bar_ids = []
        for i in range(_BAR_N):
            x   = offset_x + i * (_BAR_W + _BAR_GAP)
            rid = self._canvas.create_rectangle(
                x, cy - 1, x + _BAR_W, cy + 1,
                fill=_BAR_DIM, outline='',
            )
            self._bar_ids.append(rid)

        # Hairline divider
        tk.Frame(root, bg='#1b5e2044', height=1).pack(fill='x', padx=12, pady=(6, 0))

        # Live transcription text (hidden until text arrives)
        self._text_lbl = tk.Label(
            root, text='',
            bg=_BG, fg=_TEXT_CLR,
            font=('Consolas', 11),
            wraplength=_W - 36,
            justify='left', anchor='w',
        )
        self._text_lbl.pack(fill='x', padx=14, pady=(5, 12))

        root.update_idletasks()
        self._place()
        self._acrylic_glass()
        self._no_activate()
        self._fade_in(0.0)
        root.after(40, self._tick)
        root.mainloop()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _place(self):
        r  = self._root
        r.update_idletasks()
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        h  = r.winfo_reqheight()
        r.geometry(f'{_W}x{h}+{(sw - _W) // 2}+{sh - h - 72}')

    def _acrylic_glass(self):
        try:
            import ctypes

            class _A(ctypes.Structure):
                _fields_ = [('AccentState', ctypes.c_int), ('AccentFlags', ctypes.c_int),
                             ('GradientColor', ctypes.c_int), ('AnimationId', ctypes.c_int)]

            class _W(ctypes.Structure):
                _fields_ = [('Attribute', ctypes.c_int), ('Data', ctypes.POINTER(ctypes.c_int)),
                             ('SizeOfData', ctypes.c_size_t)]

            hwnd   = self._root.winfo_id()
            accent = _A()
            accent.AccentState   = 4           # ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.GradientColor = 0xE00a0a0a  # AABBGGRR — near-black
            wcad = _W()
            wcad.Attribute  = 19               # WCA_ACCENT_POLICY
            wcad.Data       = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))
            wcad.SizeOfData = ctypes.sizeof(accent)
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.pointer(wcad))
        except Exception:
            pass

    def _no_activate(self):
        try:
            import ctypes
            hwnd  = self._root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, -20,
                style | 0x08000000 | 0x00000080,
            )
        except Exception:
            pass

    def _fade_in(self, a: float):
        if not self._running:
            return
        a = min(0.93, a + 0.09)
        try:
            self._root.wm_attributes('-alpha', a)
            if a < 0.93:
                self._root.after(14, lambda: self._fade_in(a))
        except Exception:
            pass

    # ── Animation (~25 fps) ────────────────────────────────────────────────────

    def _tick(self):
        if not self._running:
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        cy    = _CANVAS_H // 2
        max_h = cy - 2

        for i, rid in enumerate(self._bar_ids):
            if random.random() < 0.20:
                self._bar_tgt[i] = random.uniform(1.5, max_h)

            self._bar_h[i] += (self._bar_tgt[i] - self._bar_h[i]) * 0.24
            h = max(1.5, self._bar_h[i])

            x1, _, x2, _ = self._canvas.coords(rid)
            self._canvas.coords(rid, x1, cy - h, x2, cy + h)

            # Dark gray → bright white gradient based on height
            t   = h / max_h
            val = int(66 + t * (220 - 66))
            self._canvas.itemconfig(rid, fill=f'#{val:02x}{val:02x}{val:02x}')

        with self._lock:
            text = self._text

        try:
            if self._text_lbl.cget('text') != text:
                self._text_lbl.config(text=text)
            self._place()
        except Exception:
            pass

        self._root.after(40, self._tick)
