@echo off
TITLE Browser Music Downloader
CLS

:: ------------------------------------------------------
:: FIX: Switch context to Project Root (One level up)
:: 1. Go to the folder containing this .bat file
cd /d "%~dp0"
:: 2. Go up one level to find the .py file
cd ..
:: ------------------------------------------------------

:: Auto-update yt-dlp every time to prevent YouTube errors
echo Checking for core updates...
pip install --upgrade yt-dlp >nul 2>&1

:: Run the script
python music_download.py

:: Keep window open if it crashes
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The script crashed. See error above.
    pause
)
