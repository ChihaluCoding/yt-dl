# YT-DL

YouTube・ニコニコ動画・その他2000+のサイトの動画をyt-dlpでダウンロードするChrome拡張機能です。

## セットアップ手順

### かんたんセットアップ

対話式ツールで環境チェック、yt-dlp更新、保存先作成、拡張機能の読み込み手順表示、サーバー起動をまとめて進められます。

```bash
python tools/setup_wizard.py
```

---

### 1. yt-dlp をインストール

```bash
# pip経由
pip install yt-dlp

# macOS (Homebrew)
brew install yt-dlp

# Windows (winget)
winget install yt-dlp
```

### 2. ローカルサーバーを起動

```bash
python3 server/server.py
```

起動すると以下のように表示されます：
```
✅ yt-dlp version: 2026.xx.xx
📁 サーバー直接保存先: ~/Downloads/yt-dl
🚀 サーバー起動中: http://localhost:9876
🌐 同じWi-Fiの別PCから: http://192.168.x.x:9876
```

### 3. Chrome拡張機能をインストール

1. Chromeで `chrome://extensions/` を開く
2. 右上「**デベロッパーモード**」をONにする
3. 「**パッケージ化されていない拡張機能を読み込む**」をクリック
4. `extension/` フォルダを選択

---

### 同じWi-Fiの別PCから使う

1. ダウンロードを実行するPCで `python3 server/server.py` を起動します
2. 起動ログの `🌐 同じWi-Fiの別PCから: http://192.168.x.x:9876` を確認します
3. 別PCのChromeにも `extension/` を読み込みます
4. 拡張機能の設定画面で「ローカルサーバーURL」に手順2のURLを入力して保存します

ファイルは操作しているChromeの通常のダウンロード先に保存されます。サーバー側には変換用の一時ファイルだけを作り、ブラウザへ転送後に削除します。macOS/WindowsのファイアウォールでPythonの受信接続を許可する必要がある場合があります。

---
