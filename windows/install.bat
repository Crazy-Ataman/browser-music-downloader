@echo off
TITLE Browser Music Downloader - Setup
CLS

cd /d "%~dp0"
cd ..


echo ==================================================
echo      Browser Music Downloader - Initial Setup
echo ==================================================
echo.

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

echo.
echo [INFO] Installing/Updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit
)

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
echo [INFO] Checking for Deno (JavaScript runtime for YouTube signature solving)...
where.exe deno >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Deno is NOT found in your system PATH.
    echo.
    echo YouTube signature solving may fail without Deno.
    echo To install Deno:
    echo   1. Run: install_deno.bat (in this folder)
    echo   2. Or visit: https://deno.land
    echo   3. Or run: powershell -Command "irm https://deno.land/install.ps1 | iex"
    echo.
    echo After installation, restart your terminal.
    echo.
) else (
    echo [OK] Deno is detected!
    deno --version
)

echo.
echo ==================================================
echo           Setup Complete!
echo ==================================================
echo You can now run "run.bat" inside the windows folder.
echo.
pause
