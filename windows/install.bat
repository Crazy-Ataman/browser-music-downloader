@echo off
TITLE Browser Music Downloader - Setup
CLS

:: ------------------------------------------------------
:: FIX: Switch context to Project Root (One level up)
:: 1. Go to the folder containing this .bat file
cd /d "%~dp0"
:: 2. Go up one level to find the .py file and requirements
cd ..
:: ------------------------------------------------------

echo ==================================================
echo      Browser Music Downloader - Initial Setup
echo ==================================================
echo.

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not detected!
    echo.
    echo Please install Python from the Microsoft Store or Python.org.
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit
)
echo [OK] Python is detected.

:: 2. Upgrade pip and install requirements
echo.
echo [INFO] Installing/Updating dependencies...
python -m pip install --upgrade pip
:: Now works because we moved to the parent directory
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit
)

:: 3. Check for FFmpeg
echo.
echo [INFO] Checking for FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] FFmpeg is NOT found in your system PATH.
    echo.
    echo Functionality will be limited to "Original Audio" only.
    echo To enable MP3 conversion and Metadata:
    echo   1. Download FFmpeg (ffmpeg.exe)
    echo   2. Place it in the PROJECT ROOT folder (next to music_download.py).
    echo.
) else (
    echo [OK] FFmpeg is detected!
)

echo.
echo ==================================================
echo           Setup Complete!
echo ==================================================
echo You can now run "run.bat" inside the windows folder.
echo.
pause
