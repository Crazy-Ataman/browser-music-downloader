@echo off
TITLE Browser Music Downloader
CLS

cd /d "%~dp0"
cd ..

echo Checking for core updates...
python -m pip install --upgrade yt-dlp >nul 2>&1

python music_download.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The script crashed. See error above.
    pause
)
