@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================================
echo    W H I S P E R   S T T   ^|   Setup
echo    Offline Speech-to-Text for Windows
echo  ============================================================
echo.

REM ── Step 1: Check Python ─────────────────────────────────────────────────
echo  [1/4]  Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python not found.
    echo  Download Python 3.8+ from https://python.org
    echo  Make sure to tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo         Found: %%v
echo.

REM ── Step 2: Create virtual environment ───────────────────────────────────
echo  [2/4]  Creating virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo         Already exists — skipping.
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo         Created .venv\
)
echo.

REM ── Step 3: Install dependencies ─────────────────────────────────────────
echo  [3/4]  Installing dependencies (this may take a few minutes)...
echo         Downloading packages from PyPI...
echo.
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo.

REM ── Step 4: Install whisper command ──────────────────────────────────────
echo  [4/4]  Installing whisper command...
.venv\Scripts\pip install -e . --quiet
if errorlevel 1 (
    echo  ERROR: Failed to install package.
    pause
    exit /b 1
)
echo         Done.
echo.

REM ── Add .venv\Scripts to user PATH ───────────────────────────────────────
echo  Adding to PATH...
set "SCRIPTS=%CD%\.venv\Scripts"
powershell -NoProfile -Command ^
  "$cur = [Environment]::GetEnvironmentVariable('PATH','User'); ^
   if ($cur -notlike '*%SCRIPTS%*') { ^
     [Environment]::SetEnvironmentVariable('PATH', $cur + ';%SCRIPTS%', 'User') ^
   }"
echo         Done.
echo.

REM ── Also create a whisper.bat wrapper in project root ─────────────────────
echo  @echo off > whisper.bat
echo  "%%~dp0.venv\Scripts\whisper.exe" %%* >> whisper.bat

echo.
echo  ============================================================
echo    Setup Complete!
echo  ============================================================
echo.
echo  NEXT STEPS:
echo.
echo    1. Close this window and open a NEW terminal.
echo    2. Type:   whisper
echo.
echo    Alternatively, from this folder type:   whisper.bat
echo.
pause
