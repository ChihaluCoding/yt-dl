#!/usr/bin/env python3
"""YT-DLP Suiteの対話式セットアップツール。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT_DIR / "server" / "server.py"
EXTENSION_DIR = ROOT_DIR / "extension"
MANIFEST_PATH = EXTENSION_DIR / "manifest.json"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "yt-dl"


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str
    hint: str = ""


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT_DIR, capture_output=True, text=True)


def get_command_output(command: Sequence[str], runner: Runner = run_command) -> tuple[bool, str]:
    try:
        result = runner(command)
    except OSError as exc:
        return False, str(exc)

    output = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, output


def build_install_ytdlp_command() -> list[str]:
    return [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"]


def build_server_command() -> list[str]:
    return [sys.executable, str(SERVER_PATH)]


def collect_environment_checks(
    which: Callable[[str], str | None] = shutil.which,
    runner: Runner = run_command,
) -> list[CheckItem]:
    python_ok = sys.version_info >= (3, 10)
    checks = [
        CheckItem(
            "Python",
            python_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "Python 3.10以上を推奨します。",
        ),
        CheckItem(
            "ffmpeg",
            which("ffmpeg") is not None,
            which("ffmpeg") or "未検出",
            "動画結合と音声変換に必要です。",
        ),
        CheckItem(
            "Deno",
            which("deno") is not None,
            which("deno") or "未検出",
            "YouTubeのJSチャレンジ対策で使えます。",
        ),
        CheckItem(
            "Node.js",
            which("node") is not None,
            which("node") or "未検出",
            "Denoが無い場合のJSランタイム候補です。",
        ),
        CheckItem(
            "server/server.py",
            SERVER_PATH.is_file(),
            str(SERVER_PATH),
            "ローカルサーバー本体です。",
        ),
        CheckItem(
            "extension/manifest.json",
            MANIFEST_PATH.is_file(),
            str(MANIFEST_PATH),
            "Chrome拡張の読み込みに必要です。",
        ),
    ]

    ok, version = get_command_output(["yt-dlp", "--version"], runner)
    checks.insert(
        1,
        CheckItem(
            "yt-dlp",
            ok,
            version or "未検出",
            "メニューから yt-dlp[default] を更新できます。",
        ),
    )
    return checks


def print_header() -> None:
    print("\nYT-DLP Suite セットアップ")
    print("=" * 32)


def print_environment_checks(checks: list[CheckItem]) -> None:
    print("\n環境チェック")
    for item in checks:
        mark = "OK" if item.ok else "NG"
        print(f"[{mark}] {item.name}: {item.detail}")
        if not item.ok and item.hint:
            print(f"      {item.hint}")


def install_or_update_ytdlp(runner: Runner = run_command) -> bool:
    command = build_install_ytdlp_command()
    print("\nyt-dlp[default] をインストール/更新します。")
    print("実行:", " ".join(command))
    ok, output = get_command_output(command, runner)
    if output:
        print(output)
    if ok:
        print("yt-dlp の準備が完了しました。")
        return True
    print("yt-dlp のインストール/更新に失敗しました。")
    return False


def ensure_download_dir(path: Path = DEFAULT_DOWNLOAD_DIR) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def print_extension_steps() -> None:
    print("\nChrome拡張の読み込み手順")
    print("1. Chromeで chrome://extensions/ を開く")
    print("2. 右上の デベロッパーモード をONにする")
    print("3. パッケージ化されていない拡張機能を読み込む を押す")
    print(f"4. 次のフォルダを選ぶ: {EXTENSION_DIR}")


def start_server() -> int:
    command = build_server_command()
    print("\nローカルサーバーを起動します。停止するには Ctrl+C を押してください。")
    print("実行:", " ".join(command))
    return subprocess.call(command, cwd=ROOT_DIR)


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "はい", "1"}


def run_quick_setup() -> None:
    print_environment_checks(collect_environment_checks())
    if ask_yes_no("yt-dlp[default] をインストール/更新しますか"):
        install_or_update_ytdlp()
    path = ensure_download_dir()
    print(f"保存先フォルダを確認しました: {path}")
    print_extension_steps()
    if ask_yes_no("このままサーバーを起動しますか", default=False):
        start_server()


def print_menu() -> None:
    print("\nメニュー")
    print("1. 環境チェック")
    print("2. yt-dlp[default] をインストール/更新")
    print("3. 保存先フォルダを作成")
    print("4. Chrome拡張の読み込み手順を表示")
    print("5. ローカルサーバーを起動")
    print("6. まとめてセットアップ")
    print("0. 終了")


def handle_choice(choice: str) -> bool:
    if choice == "1":
        print_environment_checks(collect_environment_checks())
    elif choice == "2":
        install_or_update_ytdlp()
    elif choice == "3":
        path = ensure_download_dir()
        print(f"保存先フォルダを確認しました: {path}")
    elif choice == "4":
        print_extension_steps()
    elif choice == "5":
        start_server()
    elif choice == "6":
        run_quick_setup()
    elif choice == "0":
        print("終了します。")
        return False
    else:
        print("番号を選んでください。")
    return True


def main() -> int:
    print_header()
    while True:
        print_menu()
        try:
            choice = input("選択: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            return 0
        if not handle_choice(choice):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
