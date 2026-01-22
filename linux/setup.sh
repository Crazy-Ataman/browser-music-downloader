#!/bin/bash

echo "=================================================="
echo "     Browser Music Downloader - Initial Setup"
echo "=================================================="

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Please install it (e.g., sudo apt install python3 python3-pip)"
    exit 1
fi
echo "[OK] Python 3 is detected."

# 2. Install dependencies
echo ""
echo "[INFO] Installing dependencies..."
# We use python3 -m pip to avoid path issues
python3 -m pip install -r ../requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to install dependencies."
    echo "If you are on Ubuntu/Debian, try: sudo apt install python3-yt-dlp python3-mutagen python3-lz4"
    echo "Or use a virtual environment."
    exit 1
fi

# 3. Check for FFmpeg
echo ""
echo "[INFO] Checking for FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "[WARNING] FFmpeg is NOT found."
    echo "Please install it to enable MP3 conversion:"
    echo "  - Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  - Arch: sudo pacman -S ffmpeg"
    echo "  - Fedora: sudo dnf install ffmpeg"
    echo "  - macOS: brew install ffmpeg"
else
    echo "[OK] FFmpeg is detected!"
fi

echo ""
echo "=================================================="
echo "           Setup Complete!"
echo "=================================================="
echo "You can now run ./run.sh"
