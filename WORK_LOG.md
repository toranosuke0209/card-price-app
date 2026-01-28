# カード価格比較アプリ 作業ログ

## プロジェクト情報

- **ローカルパス**: `C:/Users/ykh2435064/Desktop/project`
- **GitHub**: https://github.com/toranosuke0209/card-price-app
- **EC2 IP (Elastic IP)**: `54.64.210.46`
- **SSHキー**: `C:/Users/ykh2435064/Desktop/card-price-app-key.pem`
- **サイトURL**: https://54.64.210.46:8000/ （自己署名証明書）

---

## 2026-01-28: ログイン機能実装

### 実装内容

JWT認証ベースのログイン機能を実装し、デプロイ完了。

#### 新規作成ファイル
| ファイル | 説明 |
|---------|------|
| `backend/auth.py` | JWT認証モジュール（トークン生成/検証、パスワードハッシュ） |
| `frontend/auth.js` | フロントエンド認証処理（ログイン状態管理、API呼び出し） |
| `frontend/login.html` | ログイン/新規登録/管理者登録ページ |
| `frontend/admin.html` | 管理者ダッシュボード |

#### 変更ファイル
| ファイル | 変更内容 |
|---------|---------|
| `backend/requirements.txt` | python-jose, passlib, python-multipart追加 |
| `backend/database.py` | users, favorites, admin_invitesテーブル追加、CRUD関数追加 |
| `backend/models.py` | User, Favorite, AdminInviteモデル追加 |
| `backend/main.py` | 認証API、お気に入りAPI、管理者API追加 |
| `frontend/index.html` | ヘッダーにユーザーメニュー追加 |
| `frontend/app.js` | お気に入りボタン機能追加 |
| `frontend/style.css` | 認証UI、管理画面スタイル追加 |

### APIエンドポイント

#### 認証API
| エンドポイント | メソッド | 認証 | 説明 |
|---------------|---------|------|------|
| `/api/auth/register` | POST | 不要 | ユーザー登録 |
| `/api/auth/login` | POST | 不要 | ログイン→JWT発行 |
| `/api/auth/me` | GET | 必要 | 現在のユーザー情報 |
| `/api/auth/admin-register` | POST | 招待コード | 管理者登録 |

#### お気に入りAPI
| エンドポイント | メソッド | 認証 | 説明 |
|---------------|---------|------|------|
| `/api/favorites` | GET | 必要 | お気に入り一覧 |
| `/api/favorites` | POST | 必要 | お気に入り追加 |
| `/api/favorites/{id}` | DELETE | 必要 | お気に入り削除 |
| `/api/favorites/ids` | GET | 必要 | お気に入りIDリスト（軽量） |

#### 管理者API
| エンドポイント | メソッド | 認証 | 説明 |
|---------------|---------|------|------|
| `/api/admin/stats` | GET | 管理者 | 統計情報 |
| `/api/admin/cards` | POST | 管理者 | カード登録 |
| `/api/admin/invites` | GET/POST | 管理者 | 招待コード管理 |
| `/api/admin/update-popular` | POST | 管理者 | 人気カード更新 |

### 管理者アカウント
- **ID**: 1
- **ユーザー名**: admin
- **パスワード**: berogon0209
- **メール**: admin@example.com
- **ロール**: admin

### ログイン手順
1. http://54.64.210.46:8000/login にアクセス
2. 「ログイン」タブでユーザー名とパスワードを入力
3. ログイン後、ヘッダー右上のユーザーメニューから「管理画面」をクリック
4. または直接 http://54.64.210.46:8000/admin にアクセス

※管理者も一般ユーザーも同じログインページを使用。ログイン後にロールで機能が分かれる。

### 新しい管理者の追加方法
1. 管理画面（/admin）にログイン
2. 「新しい招待コードを生成」をクリック
3. 生成されたコードを新管理者に共有
4. 新管理者は /login の「管理者登録」タブで登録

### 既知の問題
- bcryptとpasslibのバージョン互換性で警告が出るが動作に影響なし
- EC2ではbcrypt 4.1.3にダウングレード済み

---

## EC2デプロイ手順

```bash
# SSH接続
ssh -i "C:/Users/ykh2435064/Desktop/card-price-app-key.pem" ubuntu@54.64.210.46

# プロジェクトディレクトリ
cd /home/ubuntu/project

# コード更新
git pull origin master

# パッケージインストール（venv使用）
cd backend
./venv/bin/pip install -r requirements.txt

# マイグレーション実行
./venv/bin/python -c "from database import migrate_v3_auth; migrate_v3_auth()"

# サーバー再起動（HTTPS）
kill $(pidof python) 2>/dev/null
nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile=/home/ubuntu/project/certs/key.pem --ssl-certfile=/home/ubuntu/project/certs/cert.pem > /home/ubuntu/project/server.log 2>&1 &
```

---

## データベーススキーマ（v3）

### usersテーブル
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- 'user' or 'admin'
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### favoritesテーブル
```sql
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (card_id) REFERENCES cards(id),
    UNIQUE(user_id, card_id)
);
```

### admin_invitesテーブル
```sql
CREATE TABLE admin_invites (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    created_by INTEGER,
    used_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    used_at TEXT,
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (used_by) REFERENCES users(id)
);
```

---

## 2026-01-28: フルアヘッド画像バグ修正

### 問題
検索結果でフルアヘッドの商品が誤った画像を表示していた。
例: 「ノヴァ」で検索すると、異なるカードに同じ画像が表示される

### 原因
`batch_crawl.py`の`FullaheadCrawler._parse_card_from_link`メソッドで、
画像取得時に親要素を3レベル上まで遡っていたため、複数商品を含む共通コンテナに到達し、
常に最初の画像が返されていた。

### 修正内容
- `backend/batch_crawl.py` 868-877行目
- 画像をリンク内または直接の親要素から取得するように変更
- 554件の誤った画像URLをDBからクリア

### 今後の対応
次回フルアヘッドのバッチクロール実行時に正しい画像が取得される。

---

## 2026-01-29: HTTPS化・画像問題修正

### 実施内容

#### 1. HTTPS化（自己署名証明書）
家のWi-Fiでページ表示が崩れる問題があり、HTTPS化で解決。
- `/home/ubuntu/project/certs/` に証明書を配置
- uvicornのSSLオプションで起動

```bash
# HTTPS起動コマンド
kill $(pidof python) 2>/dev/null
cd /home/ubuntu/project/backend && nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile=/home/ubuntu/project/certs/key.pem --ssl-certfile=/home/ubuntu/project/certs/cert.pem > /home/ubuntu/project/server.log 2>&1 &
```

#### 2. ホビステ画像プロキシ追加
ホビステが外部からの画像直接アクセスをブロック（403）していたため、プロキシAPIを追加。
- `backend/main.py` に `/api/image-proxy` エンドポイント追加
- `frontend/app.js` でホビステ画像をプロキシ経由に変更

#### 3. フルアヘッド画像修正完了
- 空画像エントリ554件を削除
- 再クロールして正しい画像を取得済み

#### 4. 遊々亭クローラー全セット対応
`local/crawl_yuyutei.py` の `BS_SETS` リストを拡張：
- BS01〜BS74（全メインセット）
- BSC01〜BSC50（コラボ/構築済み）
- SD01〜SD67（スターターデッキ）
- PB01〜PB46（プロモ）
- CB01〜CB30（コラボブースター）

遊々亭クロール実行：`local/crawl_and_upload.bat` をダブルクリック

---

## 🚨 未解決: フルアヘッド価格表示問題

### 症状
フルアヘッドの価格表示がおかしい（詳細未確認）

### 調査ポイント
1. `batch_crawl.py` の `FullaheadCrawler._parse_card_from_link` メソッド（価格取得部分）
2. DBに保存されている価格データを確認
3. 検索結果で返される価格を確認

### 確認コマンド
```bash
# フルアヘッドの価格データ確認
ssh -i "C:/Users/ykh2435064/Desktop/card-price-app-key.pem" ubuntu@54.64.210.46 "cd /home/ubuntu/project/backend && ./venv/bin/python << 'PYEOF'
import sqlite3
conn = sqlite3.connect('card_price.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT c.name, p.price, p.stock_text
    FROM prices p
    JOIN cards c ON p.card_id = c.id
    JOIN shops s ON p.shop_id = s.id
    WHERE s.name LIKE '%フルアヘッド%'
    ORDER BY p.fetched_at DESC
    LIMIT 10
''')
for r in cursor.fetchall():
    print(f'{r[0][:30]}... -> {r[1]}円 ({r[2]})')
PYEOF"
```

---

## 次回作業候補

1. **フルアヘッド価格問題修正**（優先）

2. **セキュリティ強化**
   - JWT_SECRET_KEYを環境変数に設定
   - CORS設定を本番用に制限
   - HTTPS対応

2. **機能追加**
   - お気に入りカードの価格一覧ページ
   - 価格変動通知機能
   - ユーザープロフィール編集

3. **運用改善**
   - systemdサービス化
   - ログローテーション設定
   - バックアップ自動化

---

## よく使うコマンド

```bash
# ローカル開発サーバー起動
cd C:/Users/ykh2435064/Desktop/project/backend
python -m uvicorn main:app --reload --port 8000

# EC2接続
ssh -i "C:/Users/ykh2435064/Desktop/card-price-app-key.pem" ubuntu@54.64.210.46

# EC2サーバーログ確認
ssh -i "C:/Users/ykh2435064/Desktop/card-price-app-key.pem" ubuntu@54.64.210.46 "tail -50 /home/ubuntu/project/server.log"

# EC2プロセス確認
ssh -i "C:/Users/ykh2435064/Desktop/card-price-app-key.pem" ubuntu@54.64.210.46 "ps aux | grep uvicorn"
```
