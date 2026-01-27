# アーキテクチャ設計書 (ARCHITECTURE.md)

## システム構成図

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│   外部サイト     │
│  (HTML/JS/CSS)  │◀────│   (FastAPI)     │◀────│ (スクレイピング) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## バックエンド設計

### ディレクトリ構成

```
backend/
├── main.py           # FastAPIアプリケーション、ルーティング
├── requirements.txt  # 依存パッケージ
└── scrapers/
    ├── __init__.py   # スクレイパーのエクスポート
    ├── base.py       # 基底クラス (BaseScraper)
    ├── cardrush.py   # カードラッシュ用スクレイパー
    └── tierone.py    # Tier One用スクレイパー
```

### クラス設計

#### BaseScraper (抽象基底クラス)
```python
class BaseScraper(ABC):
    site_name: str      # サイト表示名
    base_url: str       # ベースURL

    async def search(keyword: str) -> list[Product]
    # サブクラスで実装

    @abstractmethod
    def parse_product(element) -> Product
    # 各サイト固有のパース処理
```

#### Product (データクラス)
```python
@dataclass
class Product:
    site: str           # サイト名
    name: str           # 商品名
    price: int          # 価格（数値）
    price_text: str     # 価格（表示用）
    stock: int          # 在庫数
    stock_text: str     # 在庫状況（表示用）
    url: str            # 商品URL
```

#### CardrushScraper / TieroneScraper
- BaseScraperを継承
- 各サイト固有のHTML解析ロジックを実装

### 処理フロー

1. `/api/search?keyword=xxx` リクエスト受信
2. 全スクレイパーに対して `asyncio.gather()` で並行実行
3. 各スクレイパーがHTTPリクエスト → HTML解析 → Product生成
4. 結果を統合してJSONレスポンス返却

## フロントエンド設計

### ファイル構成

```
frontend/
├── index.html    # メインHTML
├── style.css     # スタイルシート
└── app.js        # 検索・表示ロジック
```

### UI構成

```
┌────────────────────────────────────────┐
│  カード価格比較                         │
├────────────────────────────────────────┤
│  [検索キーワード入力    ] [検索ボタン]  │
├────────────────────────────────────────┤
│  ソート: [価格順 ▼]                     │
├────────────────────────────────────────┤
│  ┌──────────────────────────────────┐  │
│  │ カードラッシュ | 商品名 | ¥1,780 │  │
│  │ Tier One      | 商品名 | ¥1,280 │  │
│  │ ...                              │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

## 拡張性

### 新規サイト追加時
1. `scrapers/` に新しいスクレイパークラスを追加
2. `BaseScraper` を継承し、`parse_product()` を実装
3. `scrapers/__init__.py` でエクスポート
4. `main.py` の `SCRAPERS` リストに追加

これにより、既存コードを変更せずに対応サイトを増やせる。
