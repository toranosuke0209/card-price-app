# Yuyutei Local Crawler

遊々亭はEC2からのアクセスがブロックされるため、ローカルPCからクロールしてEC2にアップロードする。

## セットアップ

### 1. 必要なもの
- Python 3.10+
- pip packages: `httpx`, `beautifulsoup4`, `lxml`

```bash
pip install httpx beautifulsoup4 lxml
```

### 2. 設定ファイルの作成
`config.txt.example` をコピーして `config.txt` を作成：

```
PEM_PATH=C:\path\to\your-key.pem
EC2_HOST=ubuntu@your-ec2-ip
```

### 3. outputフォルダの作成
```bash
mkdir output
```

## 使い方

### バッチファイルで実行（推奨）
`crawl_and_upload.bat` をダブルクリック

### 手動実行
```bash
# 全セットをクロール
python crawl_yuyutei.py

# 特定セットのみ
python crawl_yuyutei.py --sets bs74 bs73

# セット一覧を表示
python crawl_yuyutei.py --list-sets
```

## ファイル構成

```
local/
├── crawl_yuyutei.py      # クローラー
├── import_yuyutei.py     # EC2用インポートスクリプト
├── crawl_and_upload.bat  # 自動化バッチ
├── config.txt            # 設定ファイル（gitignore）
├── config.txt.example    # 設定ファイルのテンプレート
└── output/               # 出力JSON（gitignore）
```

## タスクスケジューラで自動化

1. タスクスケジューラを開く
2. 「基本タスクの作成」
3. トリガー: 毎日 22:00
4. 操作: `crawl_and_upload.bat` を実行
5. 開始: このフォルダのパス
