"""Glassmorphic recording overlay — dark acrylic glass + animated waveform bars."""
import threading
import random
import tkinter as tk

# ── Design constants ───────────────────────────────────────────────────────────
_W          = 620          # overlay width
_BAR_N      = 30           # number of waveform bars
_BAR_W      = 4            # bar pixel width
_BAR_GAP    = 5            # gap between bars
_CANVAS_H   = 54           # height of waveform canvas
_BG         = "#0d0d1a"    # fallback bg (acrylic replaces this visually)
_COL_REC    = "#ff4757"    # red — listening
_COL_PROC   = "#ffa502"    # amber — processing
_COL_TEXT   = "#dde1ff"    # soft lavender text
_COL_SUB    = "#7b7fa8"    # dim subtitle


class TranscriptionOverlay:
    """Borderless acrylic-glass overlay.  Thread-safe — call from any thread."""

    def __init__(self):
        self._root          = None
        self._lock          = threading.Lock()
        self._text          = ""
        self._status_text   = "Listening..."
        self._status_color  = _COL_REC
        self._running       = False
        self._bar_h         = [1.5] * _BAR_N
        self._bar_tgt       = [1.5] * _BAR_N
        self._dot_oval      = None
        self._status_lbl    = None
        self._text_lbl      = None
        self._canvas        = None
        self._bar_ids       = []
        self._accent_strip  = None

    # ── Public API (call from any thread) ─────────────────────────────────────

    def show(self):
        self._running       = True
        self._text          = ""
        self._status_text   = "Listening..."
        self._status_color  = _COL_REC
        self._bar_h         = [1.5] * _BAR_N
        self._bar_tgt       = [1.5] * _BAR_N
        threading.Thread(target=self._run, daemon=True).start()

    def update_text(self, text: str):
        with self._lock:
            self._text = text

    def set_status(self, text: str, color: str = _COL_PROC):
        with self._lock:
            self._status_text  = text
            self._status_color = color

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

        # ── Top accent strip (2-px coloured line)
        self._accent_strip = tk.Frame(root, bg=_COL_REC, height=2)
        self._accent_strip.pack(fill='x')

        # ── Header row: pulsing dot + status label
        hdr = tk.Frame(root, bg=_BG, padx=16, pady=8)
        hdr.pack(fill='x')

        dot_canvas = tk.Canvas(hdr, width=10, height=10, bg=_BG, highlightthickness=0)
        dot_canvas.pack(side='left')
        self._dot_oval = dot_canvas.create_oval(1, 1, 9, 9, fill=_COL_REC, outline='')
        self._dot_canvas = dot_canvas

        self._status_lbl = tk.Label(
            hdr, text="Listening...",
            bg=_BG, fg=_COL_REC,
            font=('Segoe UI Semibold', 9),
        )
        self._status_lbl.pack(side='left', padx=8)

        # ── Waveform canvas
        total_bars_px = _BAR_N * _BAR_W + (_BAR_N - 1) * _BAR_GAP
        cv_w          = _W - 32
        self._canvas  = tk.Canvas(root, width=cv_w, height=_CANVAS_H,
                                   bg=_BG, highlightthickness=0)
        self._canvas.pack(padx=16)

        offset_x = (cv_w - total_bars_px) // 2
        cy        = _CANVAS_H // 2
        self._bar_ids = []
        for i in range(_BAR_N):
            x = offset_x + i * (_BAR_W + _BAR_GAP)
            rid = self._canvas.create_rectangle(
                x, cy - 1, x + _BAR_W, cy + 1,
                fill='#4ecdc4', outline='',
            )
            self._bar_ids.append(rid)

        # ── Hairline divider
        tk.Frame(root, bg='#ffffff14', height=1).pack(fill='x', padx=16, pady=(8, 0))

        # ── Live transcription text
        self._text_lbl = tk.Label(
            root, text='',
            bg=_BG, fg=_COL_TEXT,
            font=('Segoe UI', 12),
            wraplength=_W - 52,
            justify='left', anchor='w',
        )
        self._text_lbl.pack(fill='x', padx=22, pady=(8, 16))

        root.update_idletasks()
        self._place()
        self._acrylic_glass()
        self._no_activate()
        self._fade_in(0.0)
        root.after(40, self._tick)
        root.mainloop()

    # ── Window placement ───────────────────────────────────────────────────────

    def _place(self):
        r  = self._root
        r.update_idletasks()
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        h  = r.winfo_reqheight()
        r.geometry(f'{_W}x{h}+{(sw - _W) // 2}+{sh - h - 76}')

    # ── Windows glass / acrylic blur ──────────────────────────────────────────

    def _acrylic_glass(self):
        try:
            import ctypes

            class _ACCENT(ctypes.Structure):
                _fields_ = [
                    ('AccentState',   ctypes.c_int),
                    ('AccentFlags',   ctypes.c_int),
                    ('GradientColor', ctypes.c_int),
                    ('AnimationId',   ctypes.c_int),
                ]

            class _WCAD(ctypes.Structure):
                _fields_ = [
                    ('Attribute',  ctypes.c_int),
                    ('Data',       ctypes.POINTER(ctypes.c_int)),
                    ('SizeOfData', ctypes.c_size_t),
                ]

            hwnd   = self._root.winfo_id()
            accent = _ACCENT()
            # AccentState=4 → ACCENT_ENABLE_ACRYLICBLURBEHIND (Win10 1803+)
            accent.AccentState   = 4
            # GradientColor: AABBGGRR — 0xCC alpha, dark navy #1a1a2e
            accent.GradientColor = 0xCC2e1a1a

            wcad           = _WCAD()
            wcad.Attribute = 19   # WCA_ACCENT_POLICY
            wcad.Data      = ctypes.cast(ctypes.pointer(accent), ctypes.POINTER(ctypes.c_int))
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
                style | 0x08000000 | 0x00000080,  # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            )
        except Exception:
            pass

    # ── Fade-in ────────────────────────────────────────────────────────────────

    def _fade_in(self, alpha: float):
        if not self._running:
            return
        alpha = min(0.94, alpha + 0.08)
        try:
            self._root.wm_attributes('-alpha', alpha)
            if alpha < 0.94:
                self._root.after(14, lambda: self._fade_in(alpha))
        except Exception:
            pass

    # ── Animation tick (~25 fps) ──────────────────────────────────────────────

    def _tick(self):
        if not self._running:
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        cy     = _CANVAS_H // 2
        max_h  = cy - 2

        for i, rid in enumerate(self._bar_ids):
            # Randomise targets to produce organic-looking animation
            if random.random() < 0.20:
                self._bar_tgt[i] = random.uniform(1.5, max_h)

            # Smooth lerp (spring-like)
            self._bar_h[i] += (self._bar_tgt[i] - self._bar_h[i]) * 0.24
            h = max(1.5, self._bar_h[i])

            x1, _, x2, _ = self._canvas.coords(rid)
            self._canvas.coords(rid, x1, cy - h, x2, cy + h)

            # Colour gradient: teal → magenta as height increases
            t  = h / max_h
            r  = int(78  + t * (255 - 78))
            g  = int(205 + t * (70  - 205))
            b  = int(196 + t * (153 - 196))
            self._canvas.itemconfig(rid, fill=f'#{r:02x}{g:02x}{b:02x}')

        # Pull shared state
        with self._lock:
            text = self._text
            st   = self._status_text
            sc   = self._status_color

        try:
            if self._text_lbl.cget('text') != text:
                self._text_lbl.config(text=text)
            if self._status_lbl.cget('text') != st:
                self._status_lbl.config(text=st, fg=sc)
                self._dot_canvas.itemconfig(self._dot_oval, fill=sc)
                self._accent_strip.configure(bg=sc)
            self._place()
        except Exception:
            pass

        self._root.after(40, self._tick)
