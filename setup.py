from setuptools import setup, find_packages

setup(
    name="whisper-stt",
    version="1.0.0",
    description="Offline speech-to-text for Windows using OpenAI Whisper",
    packages=find_packages(exclude=["*.venv*", "venv*", "*.egg-info*", "docs*", "build*", "dist*"]),
    install_requires=[
        "faster-whisper>=1.0.0",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "pynput>=1.7.6",
        "pyautogui>=0.9.54",
        "pystray>=0.19.4",
        "pillow>=10.0.0",
        "pywin32>=306",
        "pyperclip>=1.8.2",
    ],
    entry_points={
        "console_scripts": [
            "whisper=whisper_stt.cli.settings_ui:main",
        ],
    },
    python_requires=">=3.8",
    platforms=["win32"],
)
