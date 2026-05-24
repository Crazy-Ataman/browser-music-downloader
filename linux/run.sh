#!/bin/bash

cd "$(dirname "$0")/.."

echo "Checking for dependency updates..."
python3 -m pip install --upgrade -r requirements.txt || {
    echo "[WARNING] Could not update dependencies. Continuing anyway..."
}

python3 music_download.py
