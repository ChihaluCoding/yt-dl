#!/usr/bin/env python3
"""
YT-DLP Local Server
Chrome拡張機能からのリクエストを受け取り、yt-dlpでダウンロードを実行します。
Port: 9876
"""

import http.server
import json
import subprocess
import sys
import os
import threading
import shutil
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 9876
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "yt-dl")

# CORS headers for Chrome extension
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}

def check_ytdlp():
    """yt-dlpがインストールされているか確認"""
    return shutil.which("yt-dlp") is not None

def get_video_info(url):
    """yt-dlpで動画情報を取得"""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "動画情報の取得に失敗しました")
    return json.loads(result.stdout)

def build_yt_dlp_command(url, fmt, quality, output_dir):
    """yt-dlpコマンドを構築"""
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    cmd = ["yt-dlp", "--no-playlist", "--progress", "-o", output_template]

    audio_only_formats = {"mp3", "m4a", "aac", "opus", "flac"}

    if fmt in audio_only_formats:
        cmd += [
            "-x",
            "--audio-format", fmt,
            "--audio-quality", "0",  # best
        ]
    elif fmt in {"mp4", "mov"}:
        if fmt == "mov":
            video_selector = "bestvideo[ext=mp4][vcodec^=avc1]"
            audio_selector = "bestaudio[ext=m4a][acodec^=mp4a]"
            fallback_selectors = ["best[ext=mp4][vcodec^=avc1]", "best[ext=mp4]"]
        else:
            video_selector = "bestvideo[ext=mp4]"
            audio_selector = "bestaudio[ext=m4a]"
            fallback_selectors = ["best[ext=mp4]", "best"]

        def video_format(max_height=None):
            height_filter = f"[height<={max_height}]" if max_height else ""
            fallbacks = "/".join(f"{selector}{height_filter}" for selector in fallback_selectors)
            return f"{video_selector}{height_filter}+{audio_selector}/{fallbacks}"

        quality_map = {
            "144": video_format("144"),
            "360": video_format("360"),
            "480": video_format("480"),
            "720": video_format("720"),
            "1080": video_format("1080"),
            "1440": video_format("1440"),
            "2160": video_format("2160"),
            "max": video_format(),
        }
        fmt_str = quality_map.get(quality, quality_map["720"])
        cmd += ["-f", fmt_str, "--merge-output-format", fmt, "--remux-video", fmt]
    elif fmt == "webm":
        cmd += ["-f", "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]"]
    else:
        cmd += ["-f", "best"]

    cmd.append(url)
    return cmd

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/ping":
            self.send_json(200, {
                "status": "ok",
                "ytdlp": check_ytdlp(),
                "version": get_ytdlp_version()
            })

        elif parsed.path == "/info":
            qs = parse_qs(parsed.query)
            url = qs.get("url", [None])[0]
            if not url:
                self.send_json(400, {"error": "url parameter required"})
                return
            try:
                info = get_video_info(url)
                self.send_json(200, {
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "formats": summarize_formats(info.get("formats", [])),
                    "view_count": info.get("view_count", 0),
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/download":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                req = json.loads(body)
            except Exception:
                self.send_json(400, {"error": "invalid JSON"})
                return

            url = req.get("url", "")
            fmt = req.get("format", "mp4")
            quality = req.get("quality", "720")
            output_dir = req.get("outputDir", DEFAULT_DOWNLOAD_DIR)

            if not url:
                self.send_json(400, {"error": "url is required"})
                return

            # Run download in background thread
            job_id = str(id(threading.current_thread()))
            self.send_json(200, {"status": "started", "jobId": job_id, "outputDir": output_dir})

            def run():
                cmd = build_yt_dlp_command(url, fmt, quality, output_dir)
                print(f"\n[yt-dlp] Running: {' '.join(cmd)}\n")
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                for line in proc.stdout:
                    print(line, end="")
                proc.wait()
                if proc.returncode == 0:
                    print(f"\n✅ ダウンロード完了: {output_dir}")
                else:
                    print(f"\n❌ ダウンロード失敗 (code {proc.returncode})")

            t = threading.Thread(target=run, daemon=True)
            t.start()
        else:
            self.send_json(404, {"error": "not found"})


def summarize_formats(formats):
    seen = set()
    result = []
    for f in formats:
        h = f.get("height")
        ext = f.get("ext")
        if h and ext and (h, ext) not in seen:
            seen.add((h, ext))
            result.append({"height": h, "ext": ext, "note": f.get("format_note", "")})
    return sorted(result, key=lambda x: x["height"], reverse=True)[:12]


def get_ytdlp_version():
    try:
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def main():
    if not check_ytdlp():
        print("❌ yt-dlpが見つかりません。インストールしてください:")
        print("   pip install yt-dlp")
        print("   または: brew install yt-dlp  (macOS)")
        sys.exit(1)

    print(f"✅ yt-dlp version: {get_ytdlp_version()}")
    print(f"📁 デフォルト保存先: {DEFAULT_DOWNLOAD_DIR}")
    print(f"🚀 サーバー起動中: http://localhost:{PORT}")
    print("   Chrome拡張機能から接続できます。Ctrl+Cで停止。\n")

    server = http.server.ThreadingHTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 サーバーを停止しました")


if __name__ == "__main__":
    main()
