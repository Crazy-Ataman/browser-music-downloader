#!/bin/bash

# Auto-update yt-dlp to fix YouTube errors
echo "Checking for core updates..."
python3 -m pip install --upgrade yt-dlp > /dev/null 2>&1

# Run the script
python3 ../music_download.py
