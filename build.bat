@echo off
setlocal

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    if not defined NO_PAUSE pause
    exit /b 1
)

python tools\create_icon.py
if errorlevel 1 (
    echo Failed to create icon.
    if not defined NO_PAUSE pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --name SevenSegmentClock --icon assets\app_icon.ico --add-data "assets\app_icon.ico;assets" --add-data "assets\app_icon.png;assets" main.py
if errorlevel 1 (
    echo Build failed.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo Build complete: dist\SevenSegmentClock.exe
if not defined NO_PAUSE pause
