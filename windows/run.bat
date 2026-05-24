@echo off
TITLE Browser Music Downloader
CLS

cd /d "%~dp0"
cd ..

echo Checking for dependency updates...
python -m pip install --upgrade -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Could not update dependencies. Continuing anyway...
    echo.
)

python music_download.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The script crashed. See error above.
    pause
)
