# Browser Music Downloader

A Python automation tool that extracts YouTube links directly from your open browser tabs and downloads them as high-quality audio files.

> **Current Status:** Fully supports **Mozilla Firefox** (Tab Groups) and **Google Chrome** (Active Sessions & Bookmarks).

It handles the entire process: locating browser profiles, decompressing session data, filtering out non-video links (like search results), downloading via `yt-dlp`, and post-processing metadata.

## Features
*   **Multi-Browser Support:** Choose between Firefox and Chrome profiles on launch.
*   **Smart Integration:**
    *   **Firefox:** Decompresses `jsonlz4` session files to find active Tab Groups.
    *   **Chrome:** Scrapes active sessions and parses the Bookmarks JSON.
*   **Fallback System:**
    *   Automatically rotates download strategies to bypass **403 Forbidden** errors or age restrictions.
    *   Attempts download anonymously first, then falls back to using browser cookies (Firefox -> Chrome) if the server blocks the request.
*   **Intelligent Filtering:** Automatically skips YouTube search results, homepages, and duplicate video IDs within a group.
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
2.  **A Supported Browser:** Mozilla Firefox or Google Chrome.
3.  **FFmpeg** (Required for MP3 conversion and metadata embedding).

### Python Dependencies
The script relies on these libraries:
*   `yt-dlp` (Downloading core)
*   `mutagen` (Metadata editing)
*   `lz4` (Decompressing Firefox session files)

## Quick Start (Recommended)

This repository includes helper scripts to automate dependency installation and updates.

### Windows
1.  Navigate to the `windows` folder.
2.  Run **`install.bat`** once to install requirements.
3.  Run **`run.bat`** to start the downloader.
    *   *Note: `run.bat` automatically updates the core download engine (`yt-dlp`) every time to prevent YouTube errors.*

### Linux / macOS
1.  Navigate to the `linux` folder (or where the `.sh` files are located).
2.  Give them execution permission:
    ```bash
    chmod +x setup.sh run.sh
    ```
3.  Run **`./setup.sh`** once to install requirements.
4.  Run **`./run.sh`** to start the downloader.

## Manual Installation

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

4.  **Run the Tool:**
    ```bash
    python music_download.py
    ```

## Usage Guide

### For Mozilla Firefox Users
1.  Organize your videos into **Tab Groups**.
2.  Run the script and select Firefox.
3.  The script will detect your Tab Groups by name.

### For Google Chrome Users
Chrome handles session files differently. To ensure your tabs are detected immediately:
1.  Right-click your music tabs and select **"Add tabs to new group"** (give the group a name).
2.  While Chrome is open, press **`Ctrl+Shift+D`** (Windows/Linux) or **`Cmd+Shift+D`** (Mac) to bookmark all open tabs into a folder.
3.  Run the script and select Google Chrome. It will detect both your active sessions and your bookmark folders.



## How it works

*   **Firefox:** Reads `recovery.jsonlz4`. It decompresses the LZ4 stream, skips the proprietary Mozilla header, and parses the JSON structure to find group titles and tab URLs.
*   **Chrome:**
    *   **Sessions:** Scrapes the binary `Current Session` (SNSS format) using Regex to find YouTube URLs even if the file is partially locked.
    *   **Bookmarks:** Parses the `Bookmarks` JSON file to extract organized folders.
*   **Downloading:** The script uses yt-dlp with a robust strategy loop. It attempts to download without cookies first. If YouTube returns a 403 Forbidden or Sign-in Required error, it automatically retries using cookies from your local browser profiles to authenticate the request.
*   **Post-Processing:** Uses `mutagen` to scrub "provided to YouTube" text and technical tags, leaving you with a clean, professional-looking music library.

## License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute this software. The only requirement is that you preserve the copyright notice.

**Attribution:**
If you use this code in your own projects or share it, a link back to this repository is appreciated.
