# BSPrice プロジェクト

## AI向け指示

このプロジェクトの専属エンジニアとして振る舞ってください。

### 行動ルール
1. 実装・修正・提案の前に、このドキュメントを前提として理解すること
2. 不明点・曖昧な点がある場合、自己判断せず必ず質問すること
3. 既存の設計思想・命名規則・構造を尊重すること

### 許可事項（確認不要）
- 既存ファイルの編集・上書き
- 新規ファイルの作成
- 仕様に基づくリファクタリング
- 複数ファイルにまたがる修正

### 要確認事項
- ファイルや機能の削除
- データ破壊・後方互換性のない変更
- 仕様そのものを変更する提案

---

## プロジェクト概要

複数のトレーディングカード販売サイトから価格を同時検索できるWebアプリ。
バトルスピリッツのカードを主な対象とする。

**サイトURL**: https://bsprice.net

### 対応ショップ

| ショップ | 方式 | 実行場所 | ステータス |
|---------|------|---------|-----------|
| カードラッシュ | Selenium | EC2 | 自動（Cron） |
| Tier One | httpx | EC2 | 自動（Cron） |
| ホビーステーション | httpx | EC2 | 自動（Cron） |
| バトスキ | httpx | EC2 | 自動（Cron） |
| フルアヘッド | Selenium | EC2 | 自動（Cron） |
| 遊々亭 | httpx | ローカルPC | 手動/タスクスケジューラ |

---

## サーバー情報

| 項目 | 値 |
|------|-----|
| IP | 54.64.210.46 |
| ドメイン | bsprice.net |
| ユーザー | ubuntu |
| SSHキー | C:\Users\ykh2435064\Desktop\card-price-app-key.pem |
| インスタンス | t3.medium (2vCPU, 4GB RAM) |
| OS | Ubuntu 24.04 LTS |
| SSL | Let's Encrypt |

### 管理者アカウント
- ユーザー名: admin
- パスワード: berogon0209
- メール: admin@example.com

---

## デプロイコマンド

### ファイルアップロード
```bash
# バックエンド
scp -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" backend/ファイル名 ubuntu@54.64.210.46:/home/ubuntu/project/backend/

# フロントエンド
scp -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" frontend/*.html ubuntu@54.64.210.46:/home/ubuntu/project/frontend/
```

### サーバー再起動
```bash
ssh -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" ubuntu@54.64.210.46 "sudo pkill -f uvicorn; sleep 2; cd /home/ubuntu/project/backend && sudo nohup /home/ubuntu/project/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile /etc/letsencrypt/live/bsprice.net/privkey.pem --ssl-certfile /etc/letsencrypt/live/bsprice.net/fullchain.pem > /tmp/uvicorn.log 2>&1 &"
```

### ログ確認
```bash
ssh -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" ubuntu@54.64.210.46 "tail -50 /tmp/uvicorn.log"
```

### 巡回バッチ手動実行
```bash
ssh -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" ubuntu@54.64.210.46 "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python batch_crawl.py --shop all --pages 50"
```

---

## アーキテクチャ

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│   外部サイト     │
│  (HTML/JS/CSS)  │◀────│   (FastAPI)     │◀────│ (スクレイピング) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 技術スタック
- バックエンド: Python + FastAPI + SQLite (WALモード)
- フロントエンド: Vanilla JS + HTML5 + CSS3
- スクレイピング: BeautifulSoup4, Selenium, httpx
- 認証: JWT + bcrypt

### データベース
- **現在のバージョン**: v10
- **マイグレーション**: main.py起動時に自動実行
- v8: 通知システム（price_changes, notifications, notification_settings）
- v9: X投稿キュー（x_post_queue）
- v10: 価格履歴（price_history）

### ファイル構成
```
project/
├── backend/
│   ├── main.py              # FastAPI サーバー
│   ├── database.py          # DB操作（v10まで移行済み）
│   ├── models.py            # データモデル
│   ├── auth.py              # JWT認証
│   ├── batch_crawl.py       # バッチクローラー
│   ├── batch_notify.py      # 価格変動検知＆通知バッチ
│   ├── twitter_bot.py       # X API連携（未使用：API有料化のため）
│   └── card_price.db        # SQLiteデータベース
├── frontend/
│   ├── index.html           # メインページ
│   ├── search.html          # 検索結果ページ
│   ├── card.html            # カード詳細ページ
│   ├── ranking.html         # ランキングページ
│   ├── shops.html           # ショップ一覧
│   ├── favorites.html       # お気に入り一覧（価格付き）
│   ├── login.html           # ログインページ
│   ├── admin.html           # 管理画面（X投稿キュー含む）
│   ├── about.html           # サイト概要
│   ├── privacy.html         # プライバシーポリシー
│   ├── style.css            # スタイル
│   ├── app.js               # 検索・表示ロジック
│   └── auth.js              # 認証処理＆通知ベル
└── local/
    ├── crawl_yuyutei.py     # 遊々亭ローカルクローラー
    └── crawl_and_upload.bat # 自動化バッチ
```

---

## API仕様

### 検索API
```
GET /api/search?keyword={検索キーワード}
```

### 認証API
| エンドポイント | メソッド | 認証 | 説明 |
|---------------|---------|------|------|
| /api/auth/register | POST | 不要 | ユーザー登録 |
| /api/auth/login | POST | 不要 | ログイン→JWT発行 |
| /api/auth/me | GET | 必要 | 現在のユーザー情報 |

### 管理者API
| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| /api/admin/stats | GET | 統計情報 |
| /api/admin/featured-keywords | GET/POST | 人気キーワード管理 |
| /api/admin/featured-keywords/update-all-prices | POST | 全キーワード価格更新 |
| /api/admin/x-posts | GET | X投稿キュー一覧 |
| /api/admin/x-posts | POST | カスタムX投稿を作成 |
| /api/admin/x-posts/{id}/posted | POST | 投稿済みにマーク |
| /api/admin/x-posts/{id} | DELETE | 投稿を削除 |
| /api/card/{id}/history | GET | カードの価格履歴を取得 |

### 通知API（要認証）
| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| /api/notifications | GET | 通知一覧 |
| /api/notifications/count | GET | 未読数取得 |
| /api/notifications/{id}/read | POST | 既読にする |
| /api/notifications/read-all | POST | 全て既読 |
| /api/notifications/settings | GET/PUT | 通知設定

---

## 実装済み機能

### 価格変動通知システム（v8移行）
- **テーブル**: `price_changes`, `notifications`, `notification_settings`
- **サイト内通知**: ヘッダーの通知ベル（auth.js）で未読数表示、ドロップダウンで一覧
- **通知設定**: ユーザーごとに値下げ/値上げの閾値設定可能
- **バッチ処理**: `batch_notify.py`で価格変動検出→通知作成

### X投稿キュー（v9移行）
- **テーブル**: `x_post_queue`
- **投稿タイプ**: `price_drop`（値下げ）, `price_rise`（値上げ）, `summary`（まとめ）, `custom`（カスタム）
- **管理画面**: admin.htmlの「X投稿」タブで投稿キュー管理
- **カスタム投稿**: 管理者が任意の内容でX投稿を作成可能（280文字以内）
- **手動投稿**: X Web Intent経由（API有料化のため自動投稿は断念）
- **投稿条件**: 500円以上 or 20%以上の変動で個別投稿、3件以上でまとめ投稿

### 価格履歴（v10移行）
- **テーブル**: `price_history`
- **記録タイミング**: batch_crawl.pyで価格変動検出時に自動記録
- **表示**: カード詳細ページ（card.html）でChart.jsによるグラフ表示
- **API**: `/api/card/{id}/history?days=30` で履歴取得

### お気に入り機能
- **お気に入り登録**: カード詳細ページから星アイコンで追加/削除
- **お気に入り一覧**: `/favorites`で価格情報付きで表示
- **価格通知連携**: お気に入りカードの価格変動を通知

### SEO対応
- **canonicalタグ**: 全ページに設置（card.htmlはJSで動的設定）
- **favicon**: 全ページで`/static/favicon.ico`を参照
- **noindex**: admin.htmlのみ検索エンジン除外

---

## トラブルシューティング

### Seleniumタイムアウト
1. `base.py`で`page_load_strategy = "eager"`が設定されているか確認
2. Chromeプロセスを終了: `pkill -f chrome`
3. サーバー再起動

### メモリ不足
1. t3.medium以上のインスタンスを使用
2. 不要なChromeプロセスを終了

### SSH接続できない
1. EC2コンソールでインスタンス状態を確認
2. IPアドレスが変わっていないか確認
