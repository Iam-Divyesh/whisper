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
from pathlib import Path
from typing import Optional

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
        self._recording   = False
        self._processing  = False
        self._target_hwnd = None
        self._lock        = threading.Lock()

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

    def _stop_recording(self):
        with self._lock:
            if not self._recording:
                return
            self._recording  = False
            self._processing = True
        print("Recording stopped, processing...")
        if self._tray:
            self._tray.set_state(TrayState.PROCESSING)
        audio_data = self._audio.stop_recording() if self._audio else None
        if audio_data is not None and len(audio_data) > 0:
            threading.Thread(
                target=self._transcribe_and_type,
                args=(audio_data,),
                daemon=True,
            ).start()
        else:
            print("No audio captured")
            self._processing = False
            if self._tray:
                self._tray.set_state(TrayState.IDLE)

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

            text = self._model.transcribe_sync(audio_data, language=config.LANGUAGE)

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
        except Exception as e:
            print(f"Model pre-load failed (will retry on first use): {e}")
            self._model = None

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
                default_input = sd.query_devices(kind='input')
                print(f"Using microphone: {default_input['name']}")
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
