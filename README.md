# カード価格比較アプリ

複数のトレーディングカード販売サイトから価格を同時検索できるWebアプリケーション。
バトルスピリッツのカードを主な対象とし、6つのサイトに対応しています。

## 対応サイト

- カードラッシュ
- Tier One
- バトスキ
- フルアヘッド
- 遊々亭
- ホビーステーション

## 機能

- 複数サイトの同時検索
- 商品画像の表示
- 価格順・サイト別ソート
- 在庫状況の表示
- サイト別色分けバッジ

## 技術スタック

- **バックエンド**: Python 3.11+, FastAPI, httpx, Selenium
- **フロントエンド**: Vanilla JavaScript, HTML5, CSS3
- **スクレイピング**: BeautifulSoup4, Selenium WebDriver

## ローカル開発

### 必要な環境

- Python 3.11以上
- Google Chrome
- ChromeDriver

### インストール

```bash
cd backend
pip install -r requirements.txt
```

### ChromeDriverのセットアップ

1. [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/)から対応バージョンをダウンロード
2. `scrapers/base.py`のパスを環境に合わせて設定（自動検出対応済み）

### サーバー起動

```bash
cd backend
uvicorn main:app --reload
```

ブラウザで http://localhost:8000 にアクセス

## AWS EC2デプロイ

詳細な手順は [DEPLOYMENT.md](./DEPLOYMENT.md) を参照してください。

### クイックスタート

1. EC2インスタンスを作成（Ubuntu 22.04、t2.medium推奨）
2. プロジェクトをアップロード
3. セットアップスクリプトを実行

```bash
cd ~/project
bash setup_ec2.sh
```

4. サーバーを起動

```bash
cd ~/project/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### systemdで常駐化（推奨）

```bash
sudo cp card-price-app.service /etc/systemd/system/
sudo systemctl enable card-price-app
sudo systemctl start card-price-app
```

## プロジェクト構成

```
project/
├── README.md                # このファイル
├── CONTEXT.md               # プロジェクト詳細情報
├── DEPLOYMENT.md            # デプロイ手順書
├── setup_ec2.sh             # EC2自動セットアップ
├── card-price-app.service   # systemdサービス定義
├── backend/
│   ├── main.py              # FastAPI アプリケーション
│   ├── requirements.txt     # Python依存関係
│   └── scrapers/            # スクレイパー実装
└── frontend/
    ├── index.html           # UI
    ├── style.css            # スタイル
    └── app.js               # クライアントロジック
```

## API仕様

### 検索エンドポイント

```
GET /api/search?keyword={検索キーワード}
```

**レスポンス例**:

```json
{
  "keyword": "ジークフリード",
  "total_count": 42,
  "results": [
    {
      "site": "カードラッシュ",
      "count": 15,
      "items": [
        {
          "site": "カードラッシュ",
          "name": "ジークフリード・ヴルム・ノヴァ",
          "price": 1780,
          "price_text": "1,780円(税込)",
          "stock": 3,
          "stock_text": "在庫あり",
          "url": "https://...",
          "image_url": "https://..."
        }
      ]
    }
  ]
}
```

## 注意事項

- このアプリケーションは教育目的で作成されています
- スクレイピング対象サイトの利用規約を遵守してください
- 過度なリクエストは避け、適切な間隔でアクセスしてください

## ライセンス

このプロジェクトは個人利用目的で作成されています。

## トラブルシューティング

### ChromeDriverエラー

ChromeとChromeDriverのバージョンが一致していることを確認してください。

```bash
google-chrome --version
chromedriver --version
```

### メモリ不足

EC2のt2.microではメモリ不足になる可能性があります。t2.medium以上を推奨します。

### ポート8000にアクセスできない

セキュリティグループでポート8000が開放されているか確認してください。

## 開発履歴

- 2026/01/25: 初版リリース
  - 6サイト対応
  - 商品画像表示
  - AWS EC2デプロイ対応

## コンタクト

問題や質問がある場合は、Issueを作成してください。
