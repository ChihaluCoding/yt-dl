# YT-DL

YouTubeの動画をyt-dlpでダウンロードするChrome拡張機能です。

## 構成

```
yt-dlp-suite/
├── server/
│   └── server.py        ← Pythonローカルサーバー（localhost:9876）
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
📁 デフォルト保存先: ~/Downloads/yt-dl ※変えたい場合は拡張機能のpopupから変更できます※
🚀 サーバー起動中: http://localhost:9876
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
4. フォーマット・画質を選択してダウンロード

---

## 注意事項

- サーバーはlocalhost専用のため、外部からはアクセスできません

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
