# Whisper STT — Project Documentation

## What Is This?

Whisper STT is a Windows desktop app that converts your voice to text and types it directly into whatever window you're focused on. You hold a hotkey, speak, release — the transcribed text appears in your active text field.

It works **fully offline** after the model is downloaded once. No cloud, no subscription, no internet needed.

---

## How It Works (Architecture)

```
User holds hotkey
      │
      ▼
HotkeyManager (pynput)
      │  detects Ctrl+Shift+Space pressed
      ▼
AudioCapture (sounddevice)
      │  records microphone as float32 PCM at 16kHz
      ▼
WhisperModel (faster-whisper)
      │  runs CTranslate2-optimized Whisper inference on CPU/GPU
      │  filters silence (VAD) and hallucinations
      ▼
KeyboardTyper (pyautogui + pyperclip)
      │  pastes text via clipboard (Ctrl+V) — handles Unicode
      ▼
Active window receives transcribed text
```

The app runs as a **system tray icon** (pystray + Pillow). The tray icon changes colour to show state:
- Grey = idle
- Red = recording
- Yellow = processing
- Green = typing
- Orange = error

---

## File Structure

```
whisper-stt/
│
├── bin/
│   └── whisper.js          Node.js entry point — runs when you type `whisper`
│
├── scripts/
│   ├── postinstall.js      Sets up Python venv + installs deps (runs on first launch)
│   └── start_app.py        Python bootstrap — launches the tray app silently
│
├── whisper_stt/            The Python package
│   ├── __init__.py
│   ├── main.py             App controller, hotkey callbacks, transcription thread
│   ├── config.py           Settings loader — reads ~/.whisper_stt/config.json
│   │
│   ├── audio/
│   │   └── capture.py      Microphone capture via sounddevice
│   │
│   ├── stt/
│   │   └── model.py        faster-whisper wrapper, VAD, hallucination filter
│   │
│   ├── input/
│   │   ├── hotkeys.py      Global hotkey listener via pynput
│   │   └── typer.py        Keyboard simulation via pyautogui + clipboard
│   │
│   ├── ui/
│   │   └── tray.py         System tray icon + menu via pystray
│   │
│   └── cli/
│       └── settings_ui.py  Interactive arrow-key settings menu (the `whisper` command)
│
├── package.json            npm package definition — defines the `whisper` bin command
├── setup.py                Python package definition — used by pip
├── requirements.txt        Python dependencies
└── setup.bat               Alternative manual setup for non-npm installs
```

---

## Commands

### `npm i -g github:Iam-Divyesh/whisper`

**What happens:**
1. npm downloads the repo from GitHub into the global node_modules folder  
   → `C:\Users\<you>\AppData\Roaming\npm\node_modules\whisper-stt\`
2. npm registers the `whisper` command globally  
   → creates `C:\Users\<you>\AppData\Roaming\npm\whisper.ps1` + `whisper.cmd`
3. No Python setup yet — that happens on first `whisper` launch

---

### `whisper` (first run after install)

**What happens:**
1. `bin/whisper.js` runs via Node.js
2. Checks if `.venv\Scripts\python.exe` exists inside the package folder
3. **Not found** → runs `scripts/postinstall.js` which:
   - Finds your system Python
   - Creates a virtual environment at `{package_dir}\.venv\`
   - Installs all Python packages (`faster-whisper`, `pynput`, `pyautogui`, etc.)
   - Shows a clean progress UI — you see a spinner, not raw pip output
4. Launches `python -m whisper_stt.cli.settings_ui` with `PYTHONPATH` pointing to the package root
5. The interactive settings menu appears

---

### `whisper` (subsequent runs)

1. `bin/whisper.js` checks for `.venv` → found, skips setup
2. Directly launches the Python settings UI
3. Menu appears immediately

---

## The Settings Menu

```
  ┌──────────────────────────────────────────────────────┐
  │  WHISPER STT  |  Configuration                       │
  ├──────────────────────────────────────────────────────┤
  │                                                      │
  │  ▶  Launch Whisper                                   │
  │                                                      │
  │     Model Size     ◄ [ small      ] ►               │
  │     Language       ◄ [ English    ] ►               │
  │     Hotkey           [ ctrl+shift+space ]            │
  │     Startup on Boot  [ OFF ]        ◄►              │
  │                                                      │
  │  ────────────────────────────────────────────────    │
  │     Uninstall from this device                       │
  │     Exit                                             │
  │                                                      │
  ├──────────────────────────────────────────────────────┤
  │  ↑↓  Navigate    ◄►  Change value    Enter  Select  │
  └──────────────────────────────────────────────────────┘
```

**Navigation:**
- `↑` / `↓` — move between menu items
- `◄` / `►` — cycle through values (model, language, startup)
- `Enter` — confirm / toggle / open sub-prompt
- `Esc` — exit

**Settings are saved immediately** to `C:\Users\<you>\.whisper_stt\config.json` when you change them.

---

### Launch Whisper

1. Settings UI finds `scripts\start_app.py` in the package root
2. Spawns `pythonw.exe start_app.py` as a detached background process
3. `start_app.py` imports and calls `main()` from `whisper_stt.main`
4. A **Windows mutex** (`WhisperSTT_SingleInstance`) is created — prevents duplicate launches
5. The system tray icon appears
6. Whisper model is downloaded (first time) or loaded from cache
7. Settings UI shows "Running in your tray" and exits

---

### Model Size

| Model | Download Size | RAM Used | Speed |
|---|---|---|---|
| tiny | ~75 MB | ~390 MB | ~32x realtime |
| base | ~150 MB | ~500 MB | ~16x realtime |
| **small** | ~500 MB | ~1 GB | ~6x realtime ← default |
| medium | ~1.5 GB | ~2.6 GB | ~2x realtime |
| large-v2 | ~3 GB | ~5 GB | ~1x realtime |
| large-v3 | ~3 GB | ~5 GB | ~1x realtime |

Models are cached at `C:\Users\<you>\.whisper_stt\models\` after first download.  
Changing model takes effect next time you launch the app.

---

### Language

Sets the transcription language. `Auto-detect` lets Whisper detect the language from the audio, but is slightly slower. Setting it explicitly (e.g. `English`) is faster and more accurate for known languages.

---

### Hotkey

Press Enter on this setting to type a new combination.  
Format: `ctrl+shift+space`, `ctrl+alt+r`, `f9`, `ctrl+shift+r`

The hotkey is **global** — works in any application, even games, because it uses `pynput` which hooks into the Windows keyboard at the driver level.

> **Note:** Some apps running as Administrator may block global hotkeys unless Whisper STT is also run as Administrator.

---

### Startup on Boot

Toggles a **Windows registry entry** that launches the app silently on login.

**When ON — writes this to the registry:**
```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  WhisperSTT = "C:\...\pythonw.exe" "C:\...\scripts\start_app.py"
```

Uses `pythonw.exe` (not `python.exe`) so no console window appears.

**When OFF — deletes that registry key.**

---

## Where Data Is Stored

| Location | Contents |
|---|---|
| `~/.whisper_stt/config.json` | Your settings (model, language, hotkey) |
| `~/.whisper_stt/models/` | Downloaded Whisper model files |
| `~/.whisper_stt/app.log` | App log (debug info, transcription history) |
| `HKCU\...\Run\WhisperSTT` | Startup registry entry (only if boot enabled) |

`~` = `C:\Users\<your-username>`

---

## How Recording Works (Step by Step)

1. You **press and hold** the hotkey (`Ctrl+Shift+Space`)
2. `HotkeyManager` detects the combination and calls `_start_recording()`
3. The active window handle is saved (so focus can be restored after transcription)
4. `sounddevice.InputStream` opens and begins streaming audio at 16kHz mono
5. Audio chunks arrive in a queue every ~20ms via the callback
6. You **release** the hotkey
7. `_stop_recording()` is called — sets flags, stops the audio stream
8. A background thread starts `_transcribe_and_type(audio_data)`
9. faster-whisper runs Silero VAD to filter silence, then Whisper inference
10. The transcribed text is copied to clipboard, the original window gets focus back
11. `pyautogui.hotkey('ctrl', 'v')` pastes the text
12. Clipboard is restored to what it was before

---

## Uninstalling from the Device

### Via the `whisper` settings menu (recommended)

Select **Uninstall from this device** → press `Y` to confirm. This:
1. Kills all running Whisper/pythonw processes
2. Removes the startup registry entry
3. Deletes `~/.whisper_stt/` (config, logs, all models — ~500 MB+)
4. Uninstalls the pip package from the venv
5. Runs `npm uninstall -g whisper-stt`

### Manually (if the menu is unavailable)

```powershell
# 1. Kill the running process
Get-Process | Where-Object { $_.Path -like "*whisper*" } | Stop-Process -Force

# 2. Remove startup registry entry
Remove-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WhisperSTT"

# 3. Delete app data + models
Remove-Item "$env:USERPROFILE\.whisper_stt" -Recurse -Force

# 4. Uninstall npm package
npm uninstall -g whisper-stt
```

---

## Troubleshooting

**Hotkey does nothing**
→ Check the tray icon is visible (look for the microphone icon)  
→ Try running from `whisper` → Launch Whisper as Administrator  
→ Check for conflicting software using the same hotkey

**"No microphone found"**
→ Windows Settings → Privacy & Security → Microphone → enable access  
→ Reconnect and restart the app

**App starts but tray icon is orange (error)**
→ Model failed to load — check `~/.whisper_stt/app.log`  
→ Could be a corrupt model download — delete `~/.whisper_stt/models/` and restart

**Two tray icons appear**
→ Fixed in latest version via single-instance mutex  
→ If it still happens: open Task Manager, end all `pythonw.exe` processes, relaunch

**Text not typing in the target window**
→ Some apps block simulated input — try a different text field first  
→ Make sure you release the hotkey before typing resumes in the app

---

## Tech Stack

| Library | Purpose |
|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2-optimized Whisper inference |
| [sounddevice](https://python-sounddevice.readthedocs.io) | Real-time microphone capture |
| [pynput](https://pynput.readthedocs.io) | Global hotkey listener |
| [pyautogui](https://pyautogui.readthedocs.io) | Keyboard/clipboard simulation |
| [pystray](https://pystray.readthedocs.io) | Windows system tray icon |
| [Pillow](https://pillow.readthedocs.io) | Tray icon image generation |
| [pyperclip](https://pyperclip.readthedocs.io) | Cross-app clipboard access |
| [pywin32](https://github.com/mhammond/pywin32) | Windows API (window focus, registry) |

---

## License

MIT — free to use, modify, and distribute.
