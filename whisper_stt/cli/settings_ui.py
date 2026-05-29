"""Interactive arrow-key settings menu for Whisper STT."""
import os
import sys
import json
import subprocess
import msvcrt
from pathlib import Path

# ─── Paths & defaults ────────────────────────────────────────────────────────

APP_DIR = Path.home() / ".whisper_stt"
CONFIG_FILE = APP_DIR / "config.json"
APP_DIR.mkdir(exist_ok=True)

DEFAULTS = {
    "model_size": "small",
    "language": "en",
    "hotkey": "ctrl+shift+space",
}

# ─── Model options ───────────────────────────────────────────────────────────

MODEL_OPTIONS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
MODEL_DESC = {
    "tiny":     "~75 MB   — fastest, least accurate",
    "base":     "~150 MB  — fast",
    "small":    "~500 MB  — balanced  (recommended)",
    "medium":   "~1.5 GB  — accurate",
    "large-v2": "~3 GB    — very accurate",
    "large-v3": "~3 GB    — most accurate",
}

# ─── Language options ────────────────────────────────────────────────────────

LANGUAGES = [
    ("en", "English"),    ("hi", "Hindi"),      ("es", "Spanish"),
    ("fr", "French"),     ("de", "German"),     ("zh", "Chinese"),
    ("ja", "Japanese"),   ("ko", "Korean"),     ("ar", "Arabic"),
    ("pt", "Portuguese"), ("ru", "Russian"),    ("it", "Italian"),
    ("auto", "Auto-detect"),
]
LANG_CODES = [l[0] for l in LANGUAGES]
LANG_NAMES = {l[0]: l[1] for l in LANGUAGES}

# ─── Package root & bootstrap ────────────────────────────────────────────────

def _pkg_root() -> Path:
    """Find the project root (parent of whisper_stt/).

    Works whether launched via npm (exe in .venv/Scripts/) or pip install.
    """
    # npm path: python.exe lives in {root}/.venv/Scripts/python.exe
    candidate = Path(sys.executable).parent.parent.parent
    if (candidate / "whisper_stt").is_dir():
        return candidate
    # pip / editable install: derive from this file's location
    return Path(__file__).parent.parent.parent


def _bootstrap() -> Path:
    return _pkg_root() / "scripts" / "start_app.py"


def _pythonw() -> Path:
    pw = Path(sys.executable).parent / "pythonw.exe"
    return pw if pw.exists() else Path(sys.executable)


# ─── Startup registry ────────────────────────────────────────────────────────

_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "WhisperSTT"


def _is_startup_enabled() -> bool:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, _REG_NAME)
        winreg.CloseKey(k)
        return True
    except Exception:
        return False


def _set_startup(enable: bool) -> bool:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            cmd = f'"{_pythonw()}" "{_bootstrap()}"'
            winreg.SetValueEx(k, _REG_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, _REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
        return True
    except Exception:
        return False

# ─── Config I/O ──────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    cfg["startup"] = _is_startup_enabled()
    return cfg


def save_config(cfg: dict) -> None:
    to_save = {k: v for k, v in cfg.items() if k != "startup"}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
    except Exception:
        pass

# ─── App launch ──────────────────────────────────────────────────────────────

def _launch_app() -> bool:
    try:
        subprocess.Popen(
            [str(_pythonw()), str(_bootstrap())],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return True
    except Exception:
        return False

# ─── Box drawing ─────────────────────────────────────────────────────────────

CW = 54  # content width inside box (between the two ║ chars, includes 1-space padding each side)


def _top():    print(f"  ╔{'═' * CW}╗")
def _bot():    print(f"  ╚{'═' * CW}╝")
def _dsep():   print(f"  ╠{'═' * CW}╣")
def _tsep():   print(f"  ╟{'─' * CW}╢")


def _row(text: str = "", bold: bool = False):
    text = str(text)
    inner = CW - 2  # subtract the two padding spaces
    if len(text) > inner:
        text = text[:inner]
    print(f"  ║ {text:<{inner}} ║")

# ─── ASCII banner ────────────────────────────────────────────────────────────

BANNER = r"""
 __        ___     _                       ____  _____ _____
 \ \      / / |__ (_)___ _ __   ___ _ __ / ___||_   _|_   _|
  \ \ /\ / /| '_ \| / __| '_ \ / _ \ '__\___ \  | |   | |
   \ V  V / | | | | \__ \ |_) |  __/ |   ___) | | |   | |
    \_/\_/  |_| |_|_|___/ .__/ \___|_|  |____/  |_|   |_|
                         |_|                                 """

# ─── Menu definition ─────────────────────────────────────────────────────────

# ("key", "label") — "---" is a visual separator (not selectable)
MENU = [
    ("launch",     ""),
    ("model_size", "Model Size"),
    ("language",   "Language"),
    ("hotkey",     "Hotkey"),
    ("startup",    "Startup on Boot"),
    ("---",        ""),
    ("uninstall",  "Uninstall from this device"),
    ("exit",       "Exit"),
]
SELECTABLE = [i for i, (k, _) in enumerate(MENU) if k != "---"]
N = len(SELECTABLE)


def _item_key(sel: int) -> str:
    return MENU[SELECTABLE[sel]][0]

# ─── Keyboard input ──────────────────────────────────────────────────────────

def _read_key() -> str:
    ch = msvcrt.getch()
    if ch in (b'\xe0', b'\x00'):
        ch2 = msvcrt.getch()
        return {b'H': 'up', b'P': 'down', b'K': 'left', b'M': 'right'}.get(ch2, 'other')
    if ch == b'\r':   return 'enter'
    if ch == b'\x1b': return 'esc'
    return ch.decode('utf-8', errors='ignore')

# ─── Draw ────────────────────────────────────────────────────────────────────

def _draw(cfg: dict, sel: int, status: str = ""):
    os.system("cls")
    print(BANNER)
    print()
    _top()
    _row()
    _row("  WHISPER STT  |  Configuration")
    _row()
    _dsep()
    _row()

    for row_idx, (key, label) in enumerate(MENU):
        if key == "---":
            _tsep()
            continue

        sel_row  = SELECTABLE.index(row_idx) if row_idx in SELECTABLE else -1
        selected = sel_row == sel
        cur      = "▶ " if selected else "  "

        if key == "launch":
            _row(f"{cur} ►  Launch Whisper")

        elif key == "model_size":
            val  = cfg.get("model_size", "small")
            desc = MODEL_DESC.get(val, "")
            _row(f"{cur}  Model Size     ◄ [ {val:<10} ] ►")
            if selected:
                _row(f"        {desc}")

        elif key == "language":
            val  = cfg.get("language", "en")
            name = LANG_NAMES.get(val, val)
            _row(f"{cur}  Language       ◄ [ {name:<12} ] ►")

        elif key == "hotkey":
            val = cfg.get("hotkey", "ctrl+shift+space")
            _row(f"{cur}  Hotkey           [ {val} ]")
            if selected:
                _row("        Press Enter to change")

        elif key == "startup":
            val = "ON " if cfg.get("startup") else "OFF"
            _row(f"{cur}  Startup on Boot  [ {val} ]       ◄►")

        elif key == "uninstall":
            _row(f"{cur}  Uninstall from this device")

        elif key == "exit":
            _row(f"{cur}  Exit")

    _row()

    if status:
        _dsep()
        _row(f"  {status}")

    _dsep()
    _row("  ↑↓  Navigate    ◄►  Change value    Enter  Select")
    _bot()
    print()

# ─── Uninstall ───────────────────────────────────────────────────────────────

def _uninstall():
    """Remove all Whisper STT traces from this device."""
    os.system("cls")
    print(BANNER)
    print()
    _top()
    _row()
    _row("  Uninstall Whisper STT from this device")
    _row()
    _row("  This will remove:")
    _row("    • Startup on boot entry")
    _row("    • Config and log files  (~/.whisper_stt/)")
    _row("    • Downloaded models     (~/.whisper_stt/models/)")
    _row("    • npm global package    (whisper command)")
    _row()
    _row("  The source folder is NOT deleted.")
    _row()
    _dsep()
    _row("  Are you sure?  Press Y to confirm, any other key to cancel.")
    _bot()
    print()

    ch = msvcrt.getch()
    if ch.lower() != b'y':
        return False

    os.system("cls")
    print(BANNER)
    print()
    _top()
    _row("  Uninstalling...")
    _row()

    # 1. Remove startup registry entry
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(k, _REG_NAME)
        winreg.CloseKey(k)
        _row("  [OK]  Startup entry removed.")
    except FileNotFoundError:
        _row("  [--]  Startup entry not set.")
    except Exception as e:
        _row(f"  [!!]  Startup: {e}")

    # 2. Remove app data dir
    import shutil
    app_dir = Path.home() / ".whisper_stt"
    if app_dir.exists():
        try:
            shutil.rmtree(app_dir)
            _row("  [OK]  App data and models deleted.")
        except Exception as e:
            _row(f"  [!!]  App data: {e}")
    else:
        _row("  [--]  No app data found.")

    # 3. Uninstall npm package
    try:
        import subprocess
        r = subprocess.run(
            ["npm", "uninstall", "-g", "whisper-stt"],
            capture_output=True, text=True, shell=True,
        )
        if r.returncode == 0:
            _row("  [OK]  npm package uninstalled.")
        else:
            _row("  [!!]  npm uninstall failed — run manually:")
            _row("        npm uninstall -g whisper-stt")
    except Exception as e:
        _row(f"  [!!]  npm: {e}")

    _row()
    _row("  Uninstall complete. This window will close.")
    _bot()
    print()
    import time
    time.sleep(3)
    return True


# ─── Hotkey prompt ───────────────────────────────────────────────────────────

def _prompt_hotkey(current: str) -> str:
    os.system("cls")
    print(BANNER)
    print()
    print(f"  Current hotkey:  {current}")
    print()
    print("  Type a new hotkey combination and press Enter.")
    print("  Examples:  ctrl+shift+space   ctrl+alt+r   f9")
    print()
    print("  Leave blank and press Enter to keep current.")
    print()
    print("  New hotkey: ", end="", flush=True)
    val = input().strip()
    return val if val else current

# ─── Cycle helpers ───────────────────────────────────────────────────────────

def _cycle(lst, current, direction):
    try:
        idx = lst.index(current)
    except ValueError:
        idx = 0
    return lst[(idx + direction) % len(lst)]

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass

    cfg    = load_config()
    sel    = 0
    status = ""

    while True:
        _draw(cfg, sel, status)
        status = ""

        key = _read_key()
        ik  = _item_key(sel)

        if key == "up":
            sel = (sel - 1) % N

        elif key == "down":
            sel = (sel + 1) % N

        elif key in ("left", "right"):
            d = 1 if key == "right" else -1
            if ik == "model_size":
                cfg["model_size"] = _cycle(MODEL_OPTIONS, cfg.get("model_size", "small"), d)
                save_config(cfg)
            elif ik == "language":
                cfg["language"] = _cycle(LANG_CODES, cfg.get("language", "en"), d)
                save_config(cfg)
            elif ik == "startup":
                cfg["startup"] = not cfg.get("startup", False)
                if _set_startup(cfg["startup"]):
                    state = "enabled" if cfg["startup"] else "disabled"
                    status = f"Startup on boot {state}."
                else:
                    status = "Could not update startup — try running as Administrator."

        elif key == "enter":
            if ik == "launch":
                if _launch_app():
                    os.system("cls")
                    print(BANNER)
                    print()
                    hk = cfg.get("hotkey", "ctrl+shift+space")
                    _top()
                    _row()
                    _row("  Whisper STT is now running in your system tray.")
                    _row()
                    _row(f"  Hold  {hk}  to start recording.")
                    _row("  Release to transcribe and type.")
                    _row()
                    _row("  Right-click the tray icon to stop or exit.")
                    _row()
                    _bot()
                    print()
                    print("  Press any key to close this window...")
                    msvcrt.getch()
                    sys.exit(0)
                else:
                    status = "Failed to launch. Check ~/.whisper_stt/app.log"

            elif ik == "model_size":
                cfg["model_size"] = _cycle(MODEL_OPTIONS, cfg.get("model_size", "small"), 1)
                save_config(cfg)

            elif ik == "language":
                cfg["language"] = _cycle(LANG_CODES, cfg.get("language", "en"), 1)
                save_config(cfg)

            elif ik == "hotkey":
                new_hk = _prompt_hotkey(cfg.get("hotkey", "ctrl+shift+space"))
                if new_hk != cfg.get("hotkey"):
                    cfg["hotkey"] = new_hk
                    save_config(cfg)
                    status = f"Hotkey set to:  {new_hk}"
                else:
                    status = "Hotkey unchanged."

            elif ik == "startup":
                cfg["startup"] = not cfg.get("startup", False)
                if _set_startup(cfg["startup"]):
                    state = "enabled" if cfg["startup"] else "disabled"
                    status = f"Startup on boot {state}."
                else:
                    status = "Could not update startup — try running as Administrator."

            elif ik == "uninstall":
                if _uninstall():
                    sys.exit(0)

            elif ik == "exit":
                sys.exit(0)

        elif key == "esc":
            sys.exit(0)


if __name__ == "__main__":
    main()
