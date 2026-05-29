# Whisper STT

Offline speech-to-text for Windows. Hold a hotkey, speak, release — your words are typed into whatever window is active.

No internet required after first run. All processing happens on your machine.

```
 __        ___     _                       ____  _____ _____
 \ \      / / |__ (_)___ _ __   ___ _ __ / ___||_   _|_   _|
  \ \ /\ / /| '_ \| / __| '_ \ / _ \ '__\___ \  | |   | |
   \ V  V / | | | | \__ \ |_) |  __/ |   ___) | | |   | |
    \_/\_/  |_| |_|_|___/ .__/ \___|_|  |____/  |_|   |_|
                         |_|
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/whisper-stt.git
cd whisper-stt

# 2. Setup (Windows — run once)
setup.bat

# 3. Launch (open a new terminal after setup)
whisper
```

## Usage

1. Run `whisper` — the settings menu opens
2. Configure model, hotkey, language, and startup behavior
3. Select **Launch Whisper** — the app starts in your system tray
4. Focus any text field, hold your hotkey, speak, release
5. Transcribed text is typed directly into the active window

## Settings (via `whisper` command)

| Setting | Options | Default |
|---|---|---|
| Model Size | tiny / base / small / medium / large-v2 / large-v3 | small |
| Language | English, Hindi, Spanish, French, German, Chinese, Japanese, and more | English |
| Hotkey | Any key combination | Ctrl+Shift+Space |
| Startup on Boot | ON / OFF | OFF |

Navigate with **↑↓**, change values with **◄►**, confirm with **Enter**.

## Model sizes

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| tiny | ~75 MB | Fastest | Basic |
| base | ~150 MB | Fast | Good |
| **small** | ~500 MB | Balanced | **Recommended** |
| medium | ~1.5 GB | Slow | Great |
| large-v2 | ~3 GB | Slowest | Excellent |
| large-v3 | ~3 GB | Slowest | Best |

The model downloads automatically on first use and is cached at `~/.whisper_stt/models/`.

## Requirements

- Windows 10 or later
- Python 3.8+
- A microphone

## Troubleshooting

**"Microphone access denied"**
→ Windows Settings › Privacy & Security › Microphone › enable access

**Hotkey not working in some apps**
→ Try running `whisper` as Administrator, or choose a different hotkey

**First transcription is slow**
→ The model loads once on startup. Subsequent transcriptions are fast.

**Logs**
→ `%USERPROFILE%\.whisper_stt\app.log`

## Tech stack

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — optimised Whisper inference
- [sounddevice](https://python-sounddevice.readthedocs.io/) — microphone capture
- [pynput](https://pynput.readthedocs.io/) — global hotkeys
- [pyautogui](https://pyautogui.readthedocs.io/) — keyboard simulation
- [pystray](https://pystray.readthedocs.io/) — system tray icon

## License

MIT
