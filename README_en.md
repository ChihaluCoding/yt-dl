# YT-DL

A Chrome extension for downloading videos from YouTube, Niconico, and 2000+ other sites through `yt-dlp`.

## Setup

### 1. Install yt-dlp

```bash
# via pip
pip install yt-dlp

# macOS (Homebrew)
brew install yt-dlp

# Windows (winget)
winget install yt-dlp
```

### 2. Start the Local Server

```bash
python3 server/server.py
```

When the server starts, it prints output like this:

```text
✅ yt-dlp version: 2026.xx.xx
📁 Server direct download folder: ~/Downloads/yt-dl
🚀 Server running: http://localhost:9876
🌐 From another PC on the same Wi-Fi: http://192.168.x.x:9876
```

### 3. Install the Chrome Extension

1. Open `chrome://extensions/` in Chrome.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension/` folder.

---

### Use From Another PC on the Same Wi-Fi

1. On the PC that will run downloads, start the server with `python3 server/server.py`.
2. Check the startup log line: `🌐 From another PC on the same Wi-Fi: http://192.168.x.x:9876`.
3. Load the `extension/` folder into Chrome on the other PC too.
4. Open the extension settings on the other PC, enter the URL from step 2 as the local server URL, and save.

Files are saved to the normal Chrome downloads folder on the PC where you use the extension. The server creates a temporary file only for conversion, transfers it to the browser, then removes the temporary file. You may need to allow incoming Python connections in the macOS or Windows firewall.

---
