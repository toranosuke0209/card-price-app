# プロジェクトコンテキスト (CONTEXT.md)

## プロジェクト概要

複数のトレーディングカード販売サイトから価格を同時検索できるWebアプリ。
バトルスピリッツのカードを主な対象とする。
商品の画像・価格・在庫状況を一覧表示。

## 現在の状態（2026/01/25 完成）

### AWS EC2デプロイ状況

**EC2インスタンス情報:**
- IP: `13.115.248.117`
- インスタンスタイプ: t3.medium（2vCPU, 4GB RAM）
- OS: Ubuntu 24.04 LTS (Noble)
- Chrome: 144.0.7559.96
- ChromeDriver: 144.0.7559.96

**アクセスURL:**
```
http://13.115.248.117:8000
```

**サイト動作状況:**

| サイト | 状態 | 取得方法 | 備考 |
|--------|------|----------|------|
| カードラッシュ | ✅ 動作 | Selenium | page_load_strategy="eager"で解決 |
| Tier One | ✅ 動作 | httpx | 静的HTML |
| バトスキ | ✅ 動作 | Selenium | page_load_strategy="eager"で解決 |
| フルアヘッド | ✅ 動作 | httpx | 静的HTML |
| ホビーステーション | ✅ 動作 | Selenium | 画像は403（ホットリンク防止） |
| 遊々亭 | ❌ 403エラー | httpx | EC2のIPがブロックされている |

**5/6サイト動作中**（遊々亭はIPブロックのため動作不可）

---

## 技術的な修正履歴

### 2026/01/25 - Seleniumタイムアウト問題の解決

**問題:** カードラッシュとバトスキでSeleniumが60秒タイムアウト

**原因:** サイトに多数の追跡スクリプト（Google Analytics、Facebook Pixel、LINE Tag等）があり、Seleniumがすべてのリソース読み込み完了を待っていた

**解決策:** `base.py`に以下を追加
```python
options.page_load_strategy = "eager"
```
これによりDOMContentLoaded時点で読み込み完了とみなし、追跡スクリプトの完全読み込みを待たなくなった

### 2026/01/25 - ホビーステーション画像問題

**問題:** ホビステの商品画像が表示されない

**原因:** ホビステがホットリンク防止（403 Forbidden）を設定

**対応:** 画像読み込み失敗時に「No Image」プレースホルダーを表示するようフロントエンドを修正

### 2026/01/25 - インスタンスタイプ変更

**問題:** t3.microでSelenium + Chromeがメモリ不足

**解決:** t3.mediumにアップグレード（4GB RAM）

---

## サーバー操作コマンド

### SSH接続（ローカルPowerShellで実行）
```powershell
cd C:\Users\toraa\Downloads
ssh -i card-price-app-key.pem ubuntu@13.115.248.117
```

### サーバー起動（EC2で実行）
```bash
cd ~/project/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### バックグラウンド起動
```bash
cd ~/project/backend
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/server.log 2>&1 &
```

### プロセス確認・停止
```bash
ps aux | grep uvicorn
pkill -f uvicorn
pkill -f chrome
```

### ログ確認
```bash
tail -f /tmp/server.log
```

---

## 対応サイト詳細

### カードラッシュ (cardrush-bs.jp)
- 検索URL: `https://www.cardrush-bs.jp/product-list?keyword={keyword}`
- 価格形式: `1,780円(税込)` → 正規表現: `([\d,]+)円`
- 在庫形式: `在庫数 3枚` → 正規表現: `在庫数\s*(\d+)`
- **取得方法**: Selenium（JavaScript動的読み込みのため）

### Tier One (tier-one.jp)
- 検索URL: `https://tier-one.jp/view/search?search_keyword={keyword}`
- 価格形式: `￥1,280（税込）` → 正規表現: `￥([\d,]+)`
- 在庫形式: `在庫数:3` → 正規表現: `在庫数[：:](\d+)`
- **取得方法**: httpx（静的HTML）

### バトスキ (batosuki.shop)
- 検索方法: Seleniumでトップページにアクセス後、JavaScriptでフォーム送信
- 価格形式: `480円(内税)` → 正規表現: `([\d,]+)円\s*[(（](内税|税抜|税込)[)）]?`
- 在庫形式: SOLD OUTテキストで判定
- **取得方法**: Selenium（URLパラメータ検索が機能しないため）
- **プラットフォーム**: Shop-Pro

### フルアヘッド (fullahead-tcg.com)
- 検索URL: `https://fullahead-tcg.com/shop/shopbrand.html?search={keyword}`
- 価格形式: `880円` → `span.itemPrice` 内の `strong` 要素
- 在庫形式: カートボタンの有無で判定
- **取得方法**: httpx（静的HTML）
- **プラットフォーム**: MakeShop

### 遊々亭 (yuyu-tei.jp) ※現在動作不可
- 検索URL: `https://yuyu-tei.jp/sell/bs/s/search?search_word={keyword}`
- **状態**: EC2のIPがブロックされており403エラー

### ホビーステーション (hobbystation-single.jp)
- 検索方法: Seleniumで検索入力欄に入力後、Enterキーで検索実行
- 商品構造: `ul.searchRsultList > li`
- 価格形式: `div.packageDetail` 内のテキスト
- 在庫形式: SOLD OUT画像の有無で判定
- **取得方法**: Selenium（Enterキー送信）
- **注意**: 画像はホットリンク防止で表示不可（データは取得可能）

---

## ファイル構成

```
project/
├── CONTEXT.md               ← このファイル（プロジェクト状態管理）
├── DEPLOYMENT.md            # AWS EC2デプロイ手順書
├── README.md                # プロジェクト概要
├── setup_ec2.sh             # EC2自動セットアップスクリプト
├── card-price-app.service   # systemdサービス定義ファイル
├── backend/
│   ├── main.py              # FastAPI サーバー
│   ├── requirements.txt     # 依存関係
│   └── scrapers/
│       ├── __init__.py      # エクスポート定義
│       ├── base.py          # 基底クラス（ChromeDriverパス自動検出、フィルタリング機能）
│       ├── cardrush.py      # カードラッシュ用（SeleniumScraper継承）
│       ├── tierone.py       # Tier One用（BaseScraper継承）
│       ├── batosuki.py      # バトスキ用（SeleniumScraper継承、フォーム送信）
│       ├── fullahead.py     # フルアヘッド用（BaseScraper継承）
│       ├── yuyutei.py       # 遊々亭用（BaseScraper継承）
│       └── hobbystation.py  # ホビーステーション用（SeleniumScraper継承）
└── frontend/
    ├── index.html           # メインHTML
    ├── style.css            # スタイル（サイト別バッジ色定義）
    └── app.js               # 検索・表示ロジック
```

---

## 技術スタック

| 項目 | 技術 | 理由 |
|------|------|------|
| バックエンド | Python + FastAPI | スクレイピングとの相性、async対応 |
| HTTPクライアント | httpx | async対応、モダンなAPI |
| HTMLパーサー | BeautifulSoup4 | 柔軟なセレクタ、日本語対応 |
| フロントエンド | Vanilla JS | シンプルさ優先、依存なし |
| 動的サイト対応 | Selenium + ChromeDriver | JavaScript実行が必要なサイト用 |
| インフラ | AWS EC2 (t3.medium) | Selenium実行に十分なメモリ |

---

## 依存関係 (requirements.txt)

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
beautifulsoup4==4.12.3
lxml==5.1.0
selenium==4.17.0
```

---

## 実装済み機能

- [x] 5サイトからの価格取得（遊々亭を除く）
- [x] キーワードフィルタリング（関係ない商品を除外）
- [x] 価格順ソート（安い順/高い順）
- [x] サイト別ソート
- [x] 在庫状態表示
- [x] サイト別色分けバッジ
- [x] 商品画像表示（ホビステ以外）
- [x] 画像読み込みエラー時のプレースホルダー表示
- [x] AWS EC2デプロイ対応（ChromeDriverパス自動検出）
- [x] Seleniumタイムアウト問題解決（page_load_strategy="eager"）

---

## 未実装・今後の課題

- [ ] ページネーション対応（現在は1ページ目のみ）
- [ ] 検索結果のキャッシュ機能
- [ ] レート制限の実装
- [ ] Docker化（ECS/Fargate対応）
- [ ] 遊々亭対応（プロキシ経由での回避）
- [ ] ホビステ画像のプロキシ配信

---

## トラブルシューティング

### Seleniumタイムアウトの場合
1. `base.py`で`page_load_strategy = "eager"`が設定されているか確認
2. Chromeプロセスが残っていないか確認: `pkill -f chrome`
3. サーバーを再起動

### メモリ不足の場合
1. t3.medium以上のインスタンスを使用
2. 不要なChromeプロセスを終了: `pkill -f chrome`

### 画像が表示されない場合
- ホビステ: ホットリンク防止のため表示不可（仕様）
- その他: ブラウザキャッシュをクリア（Ctrl+Shift+R）

### SSH接続できない場合
1. EC2コンソールでインスタンス状態を確認
2. IPアドレスが変わっていないか確認（Elastic IP未設定の場合）
3. セキュリティグループでポート22が開放されているか確認

---

## サイト別CSSクラス（style.css）

- `.cardrush` → 赤 (#e74c3c)
- `.tierone` → 紫 (#9b59b6)
- `.batosuki` → 緑 (#27ae60)
- `.fullahead` → 青 (#3498db)
- `.yuyutei` → オレンジ (#f39c12)
- `.hobbystation` → ターコイズ (#1abc9c)

---

## 開発履歴

- **2026/01/25**: システム完成
  - 5サイト動作確認
  - Seleniumタイムアウト問題解決
  - t3.mediumへアップグレード
  - 画像エラーハンドリング追加
