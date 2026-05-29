"""Configuration settings for Whisper STT — reads from ~/.whisper_stt/config.json."""
import os
import json
from pathlib import Path

APP_NAME    = "Whisper STT"
APP_VERSION = "1.0.0"

# Fixed audio/model parameters
SAMPLE_RATE            = 16000
AUDIO_CHANNELS         = 1
CHUNK_DURATION         = 1.0
MAX_RECORDING_DURATION = 60.0
COMPUTE_TYPE           = "int8"
DEVICE                 = "auto"
BEAM_SIZE              = 5
BEST_OF                = 5

# Paths
APP_DIR     = Path.home() / ".whisper_stt"
MODEL_DIR   = APP_DIR / "models"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE    = APP_DIR / "app.log"

os.makedirs(APP_DIR,   exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# User-configurable defaults
_DEFAULTS = {
    "model_size": "small",
    "language":   "en",
    "hotkey":     "ctrl+shift+space",
}

# Load persisted settings
_user: dict = {}
if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as _f:
            _user = json.load(_f)
    except Exception:
        pass

MODEL_SIZE             = _user.get("model_size", _DEFAULTS["model_size"])
LANGUAGE               = _user.get("language",   _DEFAULTS["language"])
HOTKEY                 = _user.get("hotkey",     _DEFAULTS["hotkey"])


def get_language() -> "str | None":
    """Return the current language setting, re-reading config.json every call.

    Returns None for 'auto' (faster-whisper auto-detects when language=None).
    This lets the user change language in settings without restarting the app.
    """
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, encoding="utf-8") as _f:
                lang = json.load(_f).get("language", _DEFAULTS["language"])
            return None if lang == "auto" else lang
    except Exception:
        pass
    return _DEFAULTS["language"]

# Typing / UI
TYPE_DELAY             = 0.01
USE_CLIPBOARD_FALLBACK = True
SHOW_NOTIFICATIONS     = True
NOTIFICATION_DURATION  = 3.0
DEBUG                  = False
VERBOSE                = False
