#!/bin/bash

cd "$(dirname "$0")"

echo "Checking for core updates..."
python3 -m pip install --upgrade yt-dlp > /dev/null 2>&1

python3 ../music_download.py
