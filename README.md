# YT-DL

YouTubeの動画をyt-dlpでダウンロードするChrome拡張機能です。

## 構成

```
yt-dlp-suite/
├── server/
│   └── server.py        ← Pythonローカル/LANサーバー（localhost:9876）
└── extension/
    ├── manifest.json
    ├── popup.html
    ├── popup.js
    ├── content.js
    └── icons/
```

---

## セットアップ手順

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

## 使い方

1. **サーバーを起動**した状態でChromeを開く
2. YouTubeの動画ページに移動
3. 拡張機能アイコンをクリック → 自動で動画情報を取得
4. 必要に応じてメタデータを編集
5. フォーマット・画質を選択してダウンロード

---

## 設定

拡張機能のポップアップ右上にある設定ボタン、またはChrome拡張機能の詳細画面から設定を開けます。

設定画面では以下を変更できます。

- ローカルサーバーURL
- 既定フォーマット
- 既定画質
- YouTubeページでの自動情報取得
- ポップアップの文字サイズ

ポップアップの「メタデータ編集」では、ダウンロードするファイルに埋め込むタイトル、アーティスト、アルバム、ジャンル、日付、コメントを編集できます。

### 同じWi-Fiの別PCから使う

1. ダウンロードを実行するPCで `python3 server/server.py` を起動します
2. 起動ログの `🌐 同じWi-Fiの別PCから: http://192.168.x.x:9876` を確認します
3. 別PCのChromeにも `extension/` を読み込みます
4. 拡張機能の設定画面で「ローカルサーバーURL」に手順2のURLを入力して保存します

ファイルは操作しているChromeの通常のダウンロード先に保存されます。サーバー側には変換用の一時ファイルだけを作り、ブラウザへ転送後に削除します。macOS/WindowsのファイアウォールでPythonの受信接続を許可する必要がある場合があります。

---

## 注意事項

- サーバーは既定で同じLAN内に公開されます。信頼できるWi-Fi内だけで使ってください
- localhost専用に戻したい場合は `python3 server/server.py --host 127.0.0.1` で起動してください

---

## トラブルシューティング

**サーバーに接続できない場合**
- `python3 server/server.py` が起動しているか確認
- ポート9876が他のプロセスに使われていないか確認: `lsof -i :9876`

**yt-dlpが見つからない場合**
- `yt-dlp --version` でインストールを確認
- パスが通っているか確認: `which yt-dlp`

**ダウンロードが失敗する場合**
- yt-dlpを最新版に更新: `yt-dlp -U`
