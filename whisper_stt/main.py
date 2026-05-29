"""Main entry point for Whisper STT application."""
import sys
import os

# Allow running as `python main.py` directly (adds project root to path)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Fix Windows console encoding for emoji/Unicode output
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

import time
import threading
import ctypes
from pathlib import Path
from typing import Optional

# ─── Single-instance guard ────────────────────────────────────────────────────

def _ensure_single_instance():
    """Allow only one running copy. Second launch exits silently."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\WhisperSTT_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
    return mutex  # keep reference alive for the process lifetime

_MUTEX = _ensure_single_instance()

from whisper_stt import config
from whisper_stt.audio.capture import AudioCapture
from whisper_stt.stt.model import WhisperModel
from whisper_stt.input.hotkeys import HotkeyManager
from whisper_stt.input.typer import KeyboardTyper
from whisper_stt.ui.tray import TrayIcon, TrayState


class WhisperSTTApp:
    """Main application controller."""

    def __init__(self):
        print(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
        self._audio:   Optional[AudioCapture]  = None
        self._model:   Optional[WhisperModel]  = None
        self._hotkeys: Optional[HotkeyManager] = None
        self._typer:   Optional[KeyboardTyper] = None
        self._tray:    Optional[TrayIcon]      = None
        self._recording          = False
        self._processing         = False
        self._target_hwnd        = None
        self._lock               = threading.Lock()
        self._stream_stop: Optional[threading.Event] = None
        self._stream_typed_chunks = 0   # _chunks index of last chunk typed by streaming

    # ── Window focus ──────────────────────────────────────────────────────────

    def _get_foreground_window(self):
        try:
            import ctypes
            return ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            return None

    def _set_foreground_window(self, hwnd):
        if hwnd is None:
            return False
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
            return True
        except Exception as e:
            print(f"Could not restore window focus: {e}")
            return False

    # ── Recording ─────────────────────────────────────────────────────────────

    def _start_recording(self):
        with self._lock:
            if self._recording or self._processing:
                return
            self._recording = True
        self._target_hwnd = self._get_foreground_window()
        print("Recording started...")
        if self._tray:
            self._tray.set_state(TrayState.RECORDING)
        if self._audio:
            self._audio.start_recording()

        # Start real-time streaming transcription thread
        self._stream_typed_chunks = 0
        self._stream_stop = threading.Event()
        threading.Thread(target=self._stream_transcribe, daemon=True).start()

    def _stop_recording(self):
        with self._lock:
            if not self._recording:
                return
            self._recording  = False
            self._processing = True

        # Signal streaming to stop, then let it finish any in-progress type
        if self._stream_stop:
            self._stream_stop.set()
            self._stream_stop = None

        print("Recording stopped, processing...")
        if self._tray:
            self._tray.set_state(TrayState.PROCESSING)

        # Short pause so the streaming thread finishes its current type() call
        # before we stop the audio stream and read the typed-chunk index.
        time.sleep(0.15)

        if self._audio:
            self._audio.stop_recording()

        # Transcribe only the audio the streaming thread hasn't typed yet
        typed_idx = self._stream_typed_chunks
        if typed_idx > 0 and self._audio:
            remaining = self._audio.get_audio_from(typed_idx)
        else:
            remaining = self._audio.peek_audio() if self._audio else None

        if remaining is not None and len(remaining) / config.SAMPLE_RATE >= 0.3:
            try:
                t = threading.Thread(
                    target=self._transcribe_and_type,
                    args=(remaining,),
                    daemon=True,
                )
                t.start()
            except Exception as e:
                print(f"Failed to start transcription thread: {e}")
                self._processing = False
                if self._tray:
                    self._tray.set_state(TrayState.IDLE)
        else:
            print("No remaining audio to transcribe")
            self._processing = False
            if self._tray:
                self._tray.set_state(TrayState.IDLE)

    # ── Streaming transcription (during recording) ────────────────────────────

    def _stream_transcribe(self):
        """Every 2.5 s grab NEW audio since last chunk, transcribe and type it.

        Uses fast greedy decoding (beam_size=1) so latency stays low.
        Tracks _stream_typed_chunks so _stop_recording only re-transcribes
        the audio that wasn't covered here.
        """
        stop = self._stream_stop
        chunk_idx = 0  # index into AudioCapture._chunks processed so far

        while stop and not stop.wait(2.5):
            if not self._recording:
                break
            if self._model is None or self._model._model is None:
                continue  # model not loaded yet — keep waiting

            if not self._audio:
                continue

            audio, new_idx = self._audio.get_new_audio_since(chunk_idx)
            if len(audio) == 0:
                continue
            duration = len(audio) / config.SAMPLE_RATE
            if duration < 0.5:
                continue

            try:
                text = self._model.transcribe_sync(
                    audio,
                    language=config.get_language(),
                    beam_size=1,
                    best_of=1,
                )
                if text:
                    chunk_idx = new_idx
                    self._stream_typed_chunks = new_idx
                    print(f"[stream] {text}")
                    # Restore focus and type directly into the active window
                    if self._target_hwnd:
                        self._set_foreground_window(self._target_hwnd)
                    if self._typer:
                        self._typer.type_text(text + " ")
            except Exception as e:
                print(f"Stream transcription error: {e}")

    # ── Transcription ─────────────────────────────────────────────────────────

    def _transcribe_and_type(self, audio_data):
        try:
            if self._model is None:
                print("Loading Whisper model...")
                self._model = WhisperModel(
                    model_size=config.MODEL_SIZE,
                    device=config.DEVICE,
                    compute_type=config.COMPUTE_TYPE,
                    download_root=str(config.MODEL_DIR),
                )

            import numpy as np
            duration = len(audio_data) / config.SAMPLE_RATE
            rms  = np.sqrt(np.mean(audio_data ** 2))
            peak = np.max(np.abs(audio_data))
            print(f"Transcribing {duration:.1f}s audio (RMS:{rms:.4f} Peak:{peak:.4f})...")

            text = self._model.transcribe_sync(audio_data, language=config.get_language())

            if text:
                print(f"Transcribed: '{text}'")
                if self._tray:
                    self._tray.set_state(TrayState.TYPING)
                if self._target_hwnd:
                    self._set_foreground_window(self._target_hwnd)
                time.sleep(0.15)
                if self._typer:
                    if self._typer.type_text(text):
                        print("Typed into active window")
                    else:
                        print("Failed to type text")
                if self._tray:
                    self._tray.notify("Whisper STT", f"Typed: {text[:50]}")
            else:
                print("No speech detected")

        except Exception as e:
            print(f"Transcription error: {e}")
            if self._tray:
                self._tray.set_state(TrayState.ERROR)
                self._tray.notify("Whisper STT", f"Error: {str(e)[:100]}")
        finally:
            self._processing = False
            if self._tray:
                self._tray.set_state(TrayState.IDLE)

    # ── Tray callbacks ────────────────────────────────────────────────────────

    def _on_toggle(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _on_settings(self):
        print("Settings: run 'whisper' in a terminal to open the settings menu.")

    def _on_exit(self):
        print("Exiting...")
        self.stop()
        sys.exit(0)

    # ── Model pre-load ────────────────────────────────────────────────────────

    def _preload_model(self):
        try:
            print("Pre-loading Whisper model in background...")
            self._model = WhisperModel(
                model_size=config.MODEL_SIZE,
                device=config.DEVICE,
                compute_type=config.COMPUTE_TYPE,
                download_root=str(config.MODEL_DIR),
            )
            self._model._load_model()
            print("Model pre-loaded and ready!")
            if self._tray:
                self._tray.notify("Whisper STT", f"Ready — hold {config.HOTKEY} to record")
        except Exception as e:
            print(f"Model pre-load failed: {e}")
            self._model = None
            if self._tray:
                self._tray.set_state(TrayState.ERROR)
                self._tray.notify("Whisper STT", f"Model failed to load: {str(e)[:80]}")

    # ── Start / stop ──────────────────────────────────────────────────────────

    def start(self):
        try:
            print("Initializing components...")
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                input_devices = [d for d in devices if d.get('max_input_channels', 0) > 0]
                if not input_devices:
                    print("No microphone found! Please connect a microphone and restart.")
                    sys.exit(1)
                try:
                    default_input = sd.query_devices(kind='input')
                    name = default_input.get('name', 'Unknown') if isinstance(default_input, dict) else str(default_input)
                    print(f"Using microphone: {name}")
                except Exception:
                    print(f"Using microphone: {input_devices[0].get('name', 'Unknown')}")
            except SystemExit:
                raise
            except Exception as e:
                print(f"Could not verify microphone: {e}")

            self._audio = AudioCapture(
                sample_rate=config.SAMPLE_RATE,
                channels=config.AUDIO_CHANNELS,
            )
            self._typer = KeyboardTyper(
                delay=config.TYPE_DELAY,
                use_clipboard_fallback=config.USE_CLIPBOARD_FALLBACK,
            )
            self._hotkeys = HotkeyManager()
            self._hotkeys.register_hotkey(
                config.HOTKEY,
                on_press=self._start_recording,
                on_release=self._stop_recording,
            )
            self._hotkeys.start()
            self._tray = TrayIcon(
                on_toggle=self._on_toggle,
                on_settings=self._on_settings,
                on_exit=self._on_exit,
            )

            print(f"Ready! Hold {config.HOTKEY} to record")

            threading.Thread(target=self._preload_model, daemon=True).start()

            import signal
            def _signal_handler(sig, frame):
                print("\nCtrl+C received, exiting...")
                self.stop()
                sys.exit(0)
            signal.signal(signal.SIGINT, _signal_handler)

            self._tray.run()

        except Exception as e:
            print(f"Fatal error: {e}")
            raise

    def stop(self):
        if self._hotkeys:
            self._hotkeys.stop()
        if self._tray:
            self._tray.stop()


# ─── Startup registry helpers ─────────────────────────────────────────────────

_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "WhisperSTT"


def install_startup():
    import winreg
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    cmd = f'"{pythonw}" -m whisper_stt.main'
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, _REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(k)
        print(f"Startup installed: {cmd}")
    except Exception as e:
        print(f"Failed to install startup entry: {e}")
        sys.exit(1)


def uninstall_startup():
    import winreg
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(k, _REG_NAME)
        winreg.CloseKey(k)
        print("Startup entry removed.")
    except FileNotFoundError:
        print("No startup entry found.")
    except Exception as e:
        print(f"Failed to remove startup entry: {e}")
        sys.exit(1)

# ─── Logging ─────────────────────────────────────────────────────────────────

def setup_logging():
    import logging

    logging.basicConfig(
        filename=str(config.LOG_FILE),
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    class LoggingWriter:
        def __init__(self, original, logger, level):
            self.original = original
            self.logger   = logger
            self.level    = level

        def write(self, message):
            if message.strip():
                self.logger.log(self.level, message.strip())
            if self.original:
                try:
                    self.original.write(message)
                    self.original.flush()
                except Exception:
                    pass

        def flush(self):
            if self.original:
                try:
                    self.original.flush()
                except Exception:
                    pass

    logger = logging.getLogger('whisper_stt')
    sys.stdout = LoggingWriter(sys.stdout, logger, logging.INFO)
    sys.stderr = LoggingWriter(sys.stderr, logger, logging.ERROR)

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    # Always work from the project root so imports resolve correctly
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--install":
            install_startup()
            return
        if arg == "--uninstall":
            uninstall_startup()
            return

    # Hide console when running as compiled exe
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass

    setup_logging()
    app = WhisperSTTApp()
    try:
        app.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        app.stop()
    except Exception as e:
        print(f"Error: {e}")
        app.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
