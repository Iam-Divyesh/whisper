"""Bootstrap: launch Whisper STT silently via pythonw (no console window)."""
import sys, os

# This file lives in scripts/ — one level below the package root
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from whisper_stt.main import main
main()
