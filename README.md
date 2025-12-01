# Browser Music Downloader

A Python automation tool that extracts YouTube links directly from your open browser tabs and downloads them as high-quality audio files.

> **Current Status:** Fully supports **Mozilla Firefox** (including Tab Groups).

It handles the entire process: locating the Firefox session file, decompressing the proprietary LZ4 format, extracting links by group name, downloading via `yt-dlp`, and post-processing metadata.

## Features

*   **Smart Integration:** Automatically detects open Tab Groups and extracts links without manual copy-pasting.
*   **Format Options:**
    *   **Best MP3:** High quality (~240-320kbps VBR) with ID3 tags.
    *   **Standard MP3:** 192kbps for general use.
    *   **Original Audio:** Raw source (Opus/M4A) for archival (no re-encoding).
*   **Smart Metadata:**
    *   Embeds thumbnails as cover art.
    *   Cleans junk tags (tracking IDs, comments).
    *   Attempts to find the **original release year** instead of the YouTube upload year.
    *   Forces ID3v2.3 compatibility for Windows Explorer and Car Audio systems.
*   **Cross-Platform:** Works on Windows, macOS, and Linux (Standard, Snap, and Flatpak installations).

## Requirements

To use this tool fully, you need the following:

1.  **Python 3.8+**
2.  **Mozilla Firefox** (must be installed and have active tabs).
3.  **FFmpeg** (Required for MP3 conversion and metadata embedding).

### Python Dependencies
The script relies on these libraries:
*   `yt-dlp` (Downloading core)
*   `mutagen` (Metadata editing)
*   `lz4` (Decompressing Firefox session files)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Crazy-Ataman/browser-music-downloader.git
    cd your-repo-name
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup FFmpeg:**
    Download the binaries from the **[official FFmpeg website](https://ffmpeg.org/download.html)**.
    *   **Windows:** Download `ffmpeg.exe`, `ffprobe.exe`, and `ffplay.exe` and place them in the **same folder** as the script, OR add them to your system PATH.
    *   **Mac/Linux:** Install via terminal (e.g., `brew install ffmpeg` or `sudo apt install ffmpeg`).

    > **Note:** If FFmpeg is missing, the script will default to "Original Audio" mode (no MP3 conversion or cover art).

## Usage

1.  Open Firefox and organize your music videos into a **Tab Group** (or just have them open).
2.  Run the script:
    ```bash
    python music_download.py
    ```
3.  The script will:
    *   Detect your Firefox profile.
    *   List all found Tab Groups containing YouTube links.
    *   Ask you to select a group.
    *   Ask for desired audio quality.
4.  Files will be saved in the `downloads/Group Name` folder.

## How it works

Firefox stores its session data (open tabs) in a file called `recovery.jsonlz4`. This is a non-standard format compressed with LZ4.

This script:
1.  Locates the correct profile folder across different OS structures.
2.  Decompresses the LZ4 stream (skipping the proprietary header).
3.  Parses the JSON to find "Tab Groups" (grouping logic).
4.  Passes valid URLs to `yt-dlp` for processing.

## License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute this software. The only requirement is that you preserve the copyright notice.

**Attribution:**
If you use this code in your own projects or share it, a link back to this repository is appreciated.
