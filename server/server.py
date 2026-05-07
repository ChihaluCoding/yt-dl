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
import argparse
import socket
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

PORT = 9876
HOST = "0.0.0.0"
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "yt-dl")
DEFAULT_COOKIES_FROM_BROWSER = "chrome"
DEFAULT_JS_RUNTIMES = "deno"
DEFAULT_REMOTE_COMPONENTS = "ejs:npm"
DOWNLOAD_JOBS = {}
DOWNLOAD_JOBS_LOCK = threading.Lock()
JOB_TTL_SECONDS = 60 * 60
YTDLP_EXTRA_ARGS = []

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

def check_ffmpeg():
    """ffmpegがインストールされているか確認"""
    return shutil.which("ffmpeg") is not None

def check_deno():
    """Denoがインストールされているか確認"""
    return shutil.which("deno") is not None

def get_video_info(url):
    """yt-dlpで動画情報を取得"""
    cmd = [
        "yt-dlp",
        "--ignore-config",
        *YTDLP_EXTRA_ARGS,
        "--dump-json",
        "--no-playlist",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise Exception("動画情報の取得がタイムアウトしました。もう一度試すか、yt-dlpを更新してください。")
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "動画情報の取得に失敗しました")
    return json.loads(result.stdout)

def build_yt_dlp_command(url, fmt, quality, output_dir, metadata=None):
    """yt-dlpコマンドを構築"""
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    cmd = ["yt-dlp", "--ignore-config", *YTDLP_EXTRA_ARGS, "--no-playlist", "--progress", "-o", output_template]

    audio_only_formats = {"mp3", "m4a", "aac", "opus", "flac"}

    if fmt in audio_only_formats:
        audio_selector = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"
        if fmt != "m4a":
            audio_selector = "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio"

        cmd += [
            "-x",
            "--audio-format", fmt,
            "--audio-quality", "0",  # best
            "--prefer-ffmpeg",
            "-f", audio_selector,
            # サムネイルをjpgに変換して埋め込み、元ファイルを残さない
            "--embed-thumbnail",
            "--convert-thumbnails", "jpg",
            "--ppa", "ThumbnailsConvertor:-q:v 2",
            # 中間ファイル（.webp, .webm等）を残さない
            "--no-keep-video",
        ]
        metadata_args = build_metadata_args(metadata or {})
        if metadata_args:
            cmd += metadata_args
    elif fmt in {"mp4", "mov"}:
        metadata_args = build_metadata_args(metadata or {})
        if metadata_args:
            cmd += metadata_args
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
        metadata_args = build_metadata_args(metadata or {})
        if metadata_args:
            cmd += metadata_args
    else:
        cmd += ["-f", "best"]
        metadata_args = build_metadata_args(metadata or {})
        if metadata_args:
            cmd += metadata_args

    cmd.append(url)
    return cmd


def set_job(job_id, **updates):
    with DOWNLOAD_JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id, {})
        job.update(updates)
        job["updatedAt"] = time.time()
        DOWNLOAD_JOBS[job_id] = job
        return dict(job)


def get_job(job_id):
    with DOWNLOAD_JOBS_LOCK:
        job = DOWNLOAD_JOBS.get(job_id)
        return dict(job) if job else None


def cleanup_job(job_id):
    with DOWNLOAD_JOBS_LOCK:
        job = DOWNLOAD_JOBS.pop(job_id, None)
    if not job:
        return
    temp_dir = job.get("tempDir")
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)


def cleanup_old_jobs():
    now = time.time()
    stale_ids = []
    with DOWNLOAD_JOBS_LOCK:
        for job_id, job in DOWNLOAD_JOBS.items():
            if now - job.get("updatedAt", now) > JOB_TTL_SECONDS:
                stale_ids.append(job_id)
    for job_id in stale_ids:
        cleanup_job(job_id)


def find_downloaded_file(output_dir):
    files = [
        p for p in Path(output_dir).glob("*")
        if p.is_file() and not p.name.endswith((".part", ".ytdl", ".temp", ".tmp"))
    ]
    if not files:
        return None
    return max(files, key=lambda p: (p.stat().st_mtime, p.stat().st_size))


def build_metadata_args(metadata):
    """編集されたメタデータをyt-dlpの埋め込み設定に変換。
    --postprocessor-args でffmpegに -metadata を直接渡すのが最も確実。
    """
    field_map = [
        ("title",   "title"),
        ("artist",  "artist"),
        ("album",   "album"),
        ("genre",   "genre"),
        ("date",    "date"),
        ("comment", "comment"),
    ]

    ffmpeg_args = []
    has_custom_metadata = False

    for request_key, ffmpeg_tag in field_map:
        value = normalize_metadata_value(metadata.get(request_key, ""))
        if not value:
            continue
        has_custom_metadata = True
        ffmpeg_args += ["-metadata", f"{ffmpeg_tag}={value}"]

    if not has_custom_metadata:
        return []

    # --postprocessor-args はスペース区切りで引数を渡す
    # 値にスペースが含まれる場合があるため、各トークンをシェルエスケープする
    import shlex
    ppa_tokens = " ".join(shlex.quote(a) for a in ffmpeg_args)

    return [
        "--embed-metadata",
        "--no-embed-info-json",
        "--postprocessor-args", f"FFmpegMetadata:{ppa_tokens}",
    ]


def normalize_metadata_value(value):
    if not isinstance(value, str):
        return ""
    value = " ".join(value.replace("\0", "").splitlines()).strip()[:500]
    if value.lower() in {"na", "n/a", "none", "unknown", "null", "-"}:
        return ""
    return value


def escape_metadata_template(value):
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("%", "%%")

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

    def send_file(self, file_path, filename):
        safe_filename = filename.replace("\r", "").replace("\n", "")
        encoded_filename = quote(safe_filename)
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.send_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
        self.end_headers()
        with open(file_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

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
                "ffmpeg": check_ffmpeg(),
                "deno": check_deno(),
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
                    "artist": info.get("artist", ""),
                    "artists": info.get("artists", []),
                    "creator": info.get("creator", ""),
                    "creators": info.get("creators", []),
                    "uploader": info.get("uploader", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "formats": summarize_formats(info.get("formats", [])),
                    "view_count": info.get("view_count", 0),
                    "description": info.get("description", ""),
                    "upload_date": info.get("upload_date", ""),
                })
            except Exception as e:
                self.send_json(500, {"error": str(e)})
        elif parsed.path == "/job":
            qs = parse_qs(parsed.query)
            job_id = qs.get("id", [None])[0]
            job = get_job(job_id) if job_id else None
            if not job:
                self.send_json(404, {"error": "job not found"})
                return
            self.send_json(200, {
                "status": job.get("status"),
                "filename": job.get("filename"),
                "error": job.get("error"),
                "returnCode": job.get("returnCode"),
            })
        elif parsed.path == "/file":
            qs = parse_qs(parsed.query)
            job_id = qs.get("id", [None])[0]
            job = get_job(job_id) if job_id else None
            if not job:
                self.send_json(404, {"error": "job not found"})
                return
            if job.get("status") != "done" or not job.get("filePath"):
                self.send_json(409, {"error": "file is not ready"})
                return
            file_path = job["filePath"]
            if not os.path.isfile(file_path):
                self.send_json(404, {"error": "file not found"})
                return
            try:
                self.send_file(file_path, job.get("filename") or os.path.basename(file_path))
            finally:
                threading.Timer(30, cleanup_job, args=[job_id]).start()
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path in {"/download", "/prepare-download"}:
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
            metadata = req.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            if not url:
                self.send_json(400, {"error": "url is required"})
                return
            if fmt in {"mp3", "aac", "opus", "flac"} and not check_ffmpeg():
                self.send_json(500, {"error": f"{fmt}への変換にはffmpegが必要です"})
                return

            if parsed.path == "/prepare-download":
                cleanup_old_jobs()
                job_id = uuid.uuid4().hex
                temp_dir = tempfile.mkdtemp(prefix="yt-dlp-suite-")
                set_job(job_id, status="running", tempDir=temp_dir)
                self.send_json(200, {"status": "started", "jobId": job_id})

                def run_for_browser_download():
                    try:
                        cmd = build_yt_dlp_command(url, fmt, quality, temp_dir, metadata)
                        print(f"\n[yt-dlp] Running for browser download: {' '.join(cmd)}\n")
                        proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True
                        )
                        for line in proc.stdout:
                            print(line, end="")
                        proc.wait()
                        if proc.returncode != 0:
                            set_job(job_id, status="error", returnCode=proc.returncode, error=f"yt-dlp failed with code {proc.returncode}")
                            print(f"\n❌ ダウンロード失敗 (code {proc.returncode})")
                            return
                        file_path = find_downloaded_file(temp_dir)
                        if not file_path:
                            set_job(job_id, status="error", error="downloaded file not found")
                            print("\n❌ ダウンロードファイルが見つかりません")
                            return
                        set_job(
                            job_id,
                            status="done",
                            filePath=str(file_path),
                            filename=file_path.name,
                            returnCode=0,
                        )
                        print(f"\n✅ ブラウザ転送準備完了: {file_path.name}")
                    except Exception as e:
                        set_job(job_id, status="error", error=str(e))
                        print(f"\n❌ ダウンロード失敗: {e}")

                t = threading.Thread(target=run_for_browser_download, daemon=True)
                t.start()
                return

            # Run download in background thread
            job_id = str(id(threading.current_thread()))
            self.send_json(200, {"status": "started", "jobId": job_id, "outputDir": output_dir})

            def run():
                cmd = build_yt_dlp_command(url, fmt, quality, output_dir, metadata)
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


def get_lan_ip():
    """Return the best-effort LAN IP used for outbound traffic."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def parse_args():
    parser = argparse.ArgumentParser(description="YT-DLP local/LAN server")
    parser.add_argument(
        "--host",
        default=os.environ.get("YT_DLP_HOST", HOST),
        help="待受ホスト。LAN内PCから接続する場合は 0.0.0.0（既定値）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("YT_DLP_PORT", PORT)),
        help=f"待受ポート（既定値: {PORT}）",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", DEFAULT_COOKIES_FROM_BROWSER),
        help="YouTubeのBot判定対策に使うブラウザCookie。例: chrome, firefox, edge, safari",
    )
    parser.add_argument(
        "--no-cookies-from-browser",
        action="store_true",
        help="ブラウザCookieを使わずに起動",
    )
    parser.add_argument(
        "--cookies",
        default=os.environ.get("YT_DLP_COOKIES", ""),
        help="yt-dlpに渡すcookies.txtのパス",
    )
    parser.add_argument(
        "--js-runtimes",
        default=os.environ.get("YT_DLP_JS_RUNTIMES", DEFAULT_JS_RUNTIMES),
        help="yt-dlpに渡すJavaScriptランタイム。例: deno, node",
    )
    parser.add_argument(
        "--remote-components",
        default=os.environ.get("YT_DLP_REMOTE_COMPONENTS", DEFAULT_REMOTE_COMPONENTS),
        help="yt-dlpに渡すリモートコンポーネント。例: ejs:npm, ejs:github",
    )
    return parser.parse_args()


def build_ytdlp_extra_args(args):
    extra = []
    if args.cookies_from_browser and not args.no_cookies_from_browser:
        extra += ["--cookies-from-browser", args.cookies_from_browser]
    if args.cookies:
        extra += ["--cookies", args.cookies]
    if args.js_runtimes:
        extra += ["--js-runtimes", args.js_runtimes]
    if args.remote_components:
        extra += ["--remote-components", args.remote_components]
    return extra


def main():
    global YTDLP_EXTRA_ARGS
    args = parse_args()

    if not check_ytdlp():
        print("❌ yt-dlpが見つかりません。インストールしてください:")
        print("   pip install yt-dlp")
        print("   または: brew install yt-dlp  (macOS)")
        sys.exit(1)

    lan_ip = get_lan_ip()
    YTDLP_EXTRA_ARGS = build_ytdlp_extra_args(args)

    print(f"✅ yt-dlp version: {get_ytdlp_version()}")
    print(f"📁 サーバー直接保存先: {DEFAULT_DOWNLOAD_DIR}")
    if args.cookies_from_browser and not args.no_cookies_from_browser:
        print(f"🍪 Cookie: {args.cookies_from_browser} から読み込み")
    if args.cookies:
        print(f"🍪 Cookie file: {args.cookies}")
    if args.js_runtimes:
        print(f"🧩 JS runtime: {args.js_runtimes}")
    if args.remote_components:
        print(f"🧩 Remote components: {args.remote_components}")
    print(f"🚀 サーバー起動中: http://localhost:{args.port}")
    if args.host in {"0.0.0.0", ""} and lan_ip:
        print(f"🌐 同じWi-Fiの別PCから: http://{lan_ip}:{args.port}")
    print("   Chrome拡張機能から接続できます。Ctrl+Cで停止。")
    print("   ※ LAN公開中は同じネットワーク上の端末からアクセスできます。\n")

    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 サーバーを停止しました")


if __name__ == "__main__":
    main()
