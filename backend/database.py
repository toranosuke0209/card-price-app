"""
データベース操作モジュール
SQLite使用、WALモード有効
"""
import sqlite3
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from models import Shop, Card, Price, Click, SearchLog, BatchProgress, FetchQueue, User, Favorite, AdminInvite, FeaturedKeyword

# DBファイルパス
DB_PATH = Path(__file__).parent / "card_price.db"


def normalize_card_name(name: str) -> str:
    """カード名を検索用に正規化"""
    # NFKC正規化（全角→半角、カタカナ→ひらがな等）
    normalized = unicodedata.normalize("NFKC", name)
    # 小文字化
    normalized = normalized.lower()
    # 空白除去
    normalized = normalized.replace(" ", "").replace("　", "")
    return normalized


@contextmanager
def get_connection():
    """DBコネクション取得（コンテキストマネージャ）"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # WALモード有効化（同時読み書き性能向上）
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """データベース初期化（テーブル作成）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # ショップマスタ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shops (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # カードマスタ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                name_normalized TEXT NOT NULL,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        """)

        # 価格データ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY,
                card_id INTEGER NOT NULL,
                shop_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                stock INTEGER DEFAULT 0,
                stock_text TEXT,
                url TEXT NOT NULL,
                image_url TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES cards(id),
                FOREIGN KEY (shop_id) REFERENCES shops(id)
            )
        """)

        # クリック記録
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY,
                card_id INTEGER,
                shop_id INTEGER,
                price_id INTEGER,
                clicked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES cards(id),
                FOREIGN KEY (shop_id) REFERENCES shops(id)
            )
        """)

        # 検索ログ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id INTEGER PRIMARY KEY,
                keyword TEXT NOT NULL,
                result_count INTEGER DEFAULT 0,
                searched_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_name_normalized ON cards(name_normalized)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_card_shop ON prices(card_id, shop_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_fetched_at ON prices(fetched_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_clicked_at ON clicks(clicked_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_searched_at ON search_logs(searched_at)")

        conn.commit()
        print(f"Database initialized: {DB_PATH}")


def migrate_v2():
    """v2スキーマへのマイグレーション（差分実装用）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # cardsテーブルへのカラム追加
        migrations = [
            "ALTER TABLE cards ADD COLUMN card_no TEXT",
            "ALTER TABLE cards ADD COLUMN source_shop_id INTEGER",
            "ALTER TABLE cards ADD COLUMN detail_url TEXT",
            "ALTER TABLE cards ADD COLUMN is_popular INTEGER DEFAULT 0",
            "ALTER TABLE cards ADD COLUMN last_price_fetch_at TEXT",
        ]

        for sql in migrations:
            try:
                cursor.execute(sql)
                print(f"Migration applied: {sql[:50]}...")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    pass  # カラム既存時はスキップ
                else:
                    print(f"Migration skipped: {e}")

        # バッチ進捗管理テーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_progress (
                id INTEGER PRIMARY KEY,
                shop_id INTEGER NOT NULL,
                kana_type TEXT NOT NULL,
                kana TEXT NOT NULL,
                current_page INTEGER DEFAULT 1,
                total_pages INTEGER,
                status TEXT DEFAULT 'pending',
                last_fetched_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shop_id, kana_type, kana)
            )
        """)

        # 取得キューテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetch_queue (
                id INTEGER PRIMARY KEY,
                card_name TEXT NOT NULL,
                source TEXT DEFAULT 'search',
                priority INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT
            )
        """)

        # 追加インデックス
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_popular ON cards(is_popular)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_last_fetch ON cards(last_price_fetch_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fetch_queue_status ON fetch_queue(status, priority DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_progress_status ON batch_progress(status)")

        # バッチ実行ログテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_logs (
                id INTEGER PRIMARY KEY,
                batch_type TEXT NOT NULL,
                shop_name TEXT,
                status TEXT NOT NULL,
                pages_processed INTEGER DEFAULT 0,
                cards_total INTEGER DEFAULT 0,
                cards_new INTEGER DEFAULT 0,
                message TEXT,
                started_at TEXT,
                finished_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_logs_finished ON batch_logs(finished_at DESC)")

        conn.commit()
        print("Migration v2 completed")


def migrate_v3_auth():
    """v3スキーマへのマイグレーション（認証機能追加）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # ユーザーテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # お気に入りテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (card_id) REFERENCES cards(id),
                UNIQUE(user_id, card_id)
            )
        """)

        # 管理者招待コードテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_invites (
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER,
                used_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                used_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (used_by) REFERENCES users(id)
            )
        """)

        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorites_card ON favorites(card_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_invites_code ON admin_invites(code)")

        conn.commit()
        print("Migration v3 (auth) completed")


def migrate_v4_featured_keywords():
    """v4スキーマへのマイグレーション（人気キーワード機能追加）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 人気キーワードテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS featured_keywords (
                id INTEGER PRIMARY KEY,
                keyword TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_featured_keywords_order ON featured_keywords(display_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_featured_keywords_active ON featured_keywords(is_active)")

        conn.commit()
        print("Migration v4 (featured_keywords) completed")


def migrate_v5_amazon_products():
    """v5スキーマへのマイグレーション（Amazon商品機能追加）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Amazon商品テーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS amazon_products (
                id INTEGER PRIMARY KEY,
                asin TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_amazon_products_order ON amazon_products(display_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_amazon_products_active ON amazon_products(is_active)")

        conn.commit()
        print("Migration v5 (amazon_products) completed")


def migrate_v6_rakuten_products():
    """v6スキーマへのマイグレーション（楽天商品機能追加）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 楽天商品テーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rakuten_products (
                id INTEGER PRIMARY KEY,
                item_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # インデックス作成
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rakuten_products_order ON rakuten_products(display_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rakuten_products_active ON rakuten_products(is_active)")

        conn.commit()
        print("Migration v6 (rakuten_products) completed")


def init_shops():
    """ショップマスタ初期データ投入"""
    shops = [
        ("カードラッシュ", "https://www.cardrush-bs.jp/"),
        ("Tier One", "https://tier-one.jp/"),
        ("バトスキ", "https://batosuki.shop/"),
        ("フルアヘッド", "https://fullahead-tcg.com/"),
        ("遊々亭", "https://yuyu-tei.jp/"),
        ("ホビーステーション", "https://hobbystation-single.jp/"),
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        for name, url in shops:
            cursor.execute(
                "INSERT OR IGNORE INTO shops (name, url) VALUES (?, ?)",
                (name, url)
            )
        conn.commit()
        print(f"Shops initialized: {len(shops)} shops")


# =============================================================================
# ショップ操作
# =============================================================================

def get_all_shops(active_only: bool = True) -> list[Shop]:
    """全ショップ取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM shops WHERE is_active = 1")
        else:
            cursor.execute("SELECT * FROM shops")
        rows = cursor.fetchall()
        return [Shop(**dict(row)) for row in rows]


def get_shop_by_name(name: str) -> Optional[Shop]:
    """ショップ名で取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shops WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Shop(**dict(row)) if row else None


# =============================================================================
# カード操作
# =============================================================================

def get_or_create_card(name: str) -> Card:
    """カードを取得または作成"""
    name_normalized = normalize_card_name(name)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 既存カード検索
        cursor.execute("SELECT * FROM cards WHERE name = ?", (name,))
        row = cursor.fetchone()

        if row:
            return Card(**dict(row))

        # 新規作成
        cursor.execute(
            "INSERT INTO cards (name, name_normalized) VALUES (?, ?)",
            (name, name_normalized)
        )
        conn.commit()

        cursor.execute("SELECT * FROM cards WHERE id = ?", (cursor.lastrowid,))
        row = cursor.fetchone()
        return Card(**dict(row))


def search_cards(keyword: str) -> list[Card]:
    """カード名で検索"""
    keyword_normalized = normalize_card_name(keyword)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM cards WHERE name_normalized LIKE ?",
            (f"%{keyword_normalized}%",)
        )
        rows = cursor.fetchall()
        return [Card(**dict(row)) for row in rows]


# =============================================================================
# 価格操作
# =============================================================================

def save_price(card_id: int, shop_id: int, price: int, stock: int,
               stock_text: str, url: str, image_url: str = "") -> int:
    """価格データを保存（常に新規レコード追加）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prices (card_id, shop_id, price, stock, stock_text, url, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (card_id, shop_id, price, stock, stock_text, url, image_url))
        conn.commit()
        return cursor.lastrowid


def save_price_if_changed(card_id: int, shop_id: int, price: int, stock: int,
                          stock_text: str, url: str, image_url: str = "") -> Optional[int]:
    """価格に変更がある場合のみ保存"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 最新価格を取得
        cursor.execute("""
            SELECT price, stock FROM prices
            WHERE card_id = ? AND shop_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
        """, (card_id, shop_id))
        row = cursor.fetchone()

        # 変更がない場合はスキップ
        if row and row["price"] == price and row["stock"] == stock:
            return None

        # 新規保存
        cursor.execute("""
            INSERT INTO prices (card_id, shop_id, price, stock, stock_text, url, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (card_id, shop_id, price, stock, stock_text, url, image_url))
        conn.commit()
        return cursor.lastrowid


def get_latest_prices_by_keyword(keyword: str, limit: int = 100) -> list[Price]:
    """キーワードで最新価格を検索（検索API用）"""
    keyword_normalized = normalize_card_name(keyword)

    with get_connection() as conn:
        cursor = conn.cursor()
        # 各カード×ショップの最新価格のみ取得
        cursor.execute("""
            SELECT p.*, c.name as card_name, s.name as shop_name
            FROM prices p
            JOIN cards c ON p.card_id = c.id
            JOIN shops s ON p.shop_id = s.id
            WHERE c.name_normalized LIKE ?
            AND p.id IN (
                SELECT MAX(id) FROM prices
                GROUP BY card_id, shop_id
            )
            ORDER BY p.price ASC
            LIMIT ?
        """, (f"%{keyword_normalized}%", limit))

        rows = cursor.fetchall()
        return [Price(**dict(row)) for row in rows]


def get_latest_price(card_id: int, shop_id: int) -> Optional[Price]:
    """特定カード×ショップの最新価格を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.name as card_name, s.name as shop_name
            FROM prices p
            JOIN cards c ON p.card_id = c.id
            JOIN shops s ON p.shop_id = s.id
            WHERE p.card_id = ? AND p.shop_id = ?
            ORDER BY p.fetched_at DESC
            LIMIT 1
        """, (card_id, shop_id))
        row = cursor.fetchone()
        return Price(**dict(row)) if row else None


# =============================================================================
# ホーム画面用クエリ
# =============================================================================

def get_recently_updated(limit: int = 20) -> list[Price]:
    """最近価格更新されたカード"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p.*, c.name as card_name, s.name as shop_name
            FROM prices p
            JOIN cards c ON p.card_id = c.id
            JOIN shops s ON p.shop_id = s.id
            WHERE p.fetched_at > datetime('now', '-1 hour')
            ORDER BY p.fetched_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [Price(**dict(row)) for row in rows]


def get_price_increased_cards(limit: int = 20) -> list[dict]:
    """値上がりしたカード"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            WITH ranked AS (
                SELECT
                    p.card_id,
                    p.shop_id,
                    p.price,
                    p.fetched_at,
                    ROW_NUMBER() OVER (PARTITION BY p.card_id, p.shop_id ORDER BY p.fetched_at DESC) as rn
                FROM prices p
            )
            SELECT
                c.name as card_name,
                s.name as shop_name,
                curr.price as current_price,
                prev.price as previous_price,
                (curr.price - prev.price) as diff
            FROM ranked curr
            JOIN ranked prev ON curr.card_id = prev.card_id AND curr.shop_id = prev.shop_id
            JOIN cards c ON curr.card_id = c.id
            JOIN shops s ON curr.shop_id = s.id
            WHERE curr.rn = 1 AND prev.rn = 2 AND curr.price > prev.price
            ORDER BY diff DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_price_decreased_cards(limit: int = 20) -> list[dict]:
    """値下がりしたカード"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            WITH ranked AS (
                SELECT
                    p.card_id,
                    p.shop_id,
                    p.price,
                    p.fetched_at,
                    ROW_NUMBER() OVER (PARTITION BY p.card_id, p.shop_id ORDER BY p.fetched_at DESC) as rn
                FROM prices p
            )
            SELECT
                c.name as card_name,
                s.name as shop_name,
                curr.price as current_price,
                prev.price as previous_price,
                (prev.price - curr.price) as diff
            FROM ranked curr
            JOIN ranked prev ON curr.card_id = prev.card_id AND curr.shop_id = prev.shop_id
            JOIN cards c ON curr.card_id = c.id
            JOIN shops s ON curr.shop_id = s.id
            WHERE curr.rn = 1 AND prev.rn = 2 AND curr.price < prev.price
            ORDER BY diff DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_hot_cards(days: int = 7, limit: int = 20) -> list[dict]:
    """ホットカード（検索・クリック数）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.id,
                c.name as card_name,
                COUNT(DISTINCT cl.id) as click_count
            FROM cards c
            LEFT JOIN clicks cl ON cl.card_id = c.id
                AND cl.clicked_at > datetime('now', ? || ' days')
            GROUP BY c.id
            HAVING click_count > 0
            ORDER BY click_count DESC
            LIMIT ?
        """, (f"-{days}", limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# クリック・検索ログ
# =============================================================================

def record_click(card_id: int, shop_id: int, price_id: Optional[int] = None) -> int:
    """クリック記録"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO clicks (card_id, shop_id, price_id) VALUES (?, ?, ?)",
            (card_id, shop_id, price_id)
        )
        conn.commit()
        return cursor.lastrowid


def record_search(keyword: str, result_count: int) -> int:
    """検索ログ記録"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_logs (keyword, result_count) VALUES (?, ?)",
            (keyword, result_count)
        )
        conn.commit()
        return cursor.lastrowid


# =============================================================================
# メンテナンス
# =============================================================================

def cleanup_old_prices(days: int = 90):
    """古い価格データを削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM prices
            WHERE fetched_at < datetime('now', ? || ' days')
        """, (f"-{days}",))
        deleted = cursor.rowcount
        conn.commit()
        print(f"Deleted {deleted} old price records")
        return deleted


def get_inactive_keywords(days: int = 30) -> list[str]:
    """指定日数以上検索されていないキーワードを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # 各キーワードの最終検索日を取得し、30日以上前のものを抽出
        cursor.execute("""
            SELECT keyword, MAX(searched_at) as last_searched
            FROM search_logs
            GROUP BY keyword
            HAVING MAX(searched_at) < datetime('now', ? || ' days')
        """, (f"-{days}",))
        rows = cursor.fetchall()
        return [row["keyword"] for row in rows]


def get_database_stats() -> dict:
    """DB統計情報"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM shops")
        shop_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM cards")
        card_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM prices")
        price_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM clicks")
        click_count = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(fetched_at), MAX(fetched_at) FROM prices")
        row = cursor.fetchone()
        oldest_price = row[0]
        newest_price = row[1]

        return {
            "shops": shop_count,
            "cards": card_count,
            "prices": price_count,
            "clicks": click_count,
            "oldest_price": oldest_price,
            "newest_price": newest_price,
        }


# =============================================================================
# バッチ進捗管理
# =============================================================================

HIRAGANA = list('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん')
KATAKANA = list('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン')


def init_batch_progress(shop_id: int):
    """指定ショップのバッチ進捗を初期化"""
    with get_connection() as conn:
        cursor = conn.cursor()

        for kana in HIRAGANA:
            cursor.execute("""
                INSERT OR IGNORE INTO batch_progress (shop_id, kana_type, kana)
                VALUES (?, 'hiragana', ?)
            """, (shop_id, kana))

        for kana in KATAKANA:
            cursor.execute("""
                INSERT OR IGNORE INTO batch_progress (shop_id, kana_type, kana)
                VALUES (?, 'katakana', ?)
            """, (shop_id, kana))

        conn.commit()


def get_next_batch_target(shop_id: int) -> Optional[BatchProgress]:
    """次に処理すべきバッチ対象を取得（ひらがな→カタカナ順）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 処理中のものがあれば優先
        cursor.execute("""
            SELECT * FROM batch_progress
            WHERE shop_id = ? AND status = 'in_progress'
            LIMIT 1
        """, (shop_id,))
        row = cursor.fetchone()
        if row:
            return BatchProgress(**dict(row))

        # ひらがな→カタカナの順で未完了を取得
        cursor.execute("""
            SELECT * FROM batch_progress
            WHERE shop_id = ? AND status = 'pending'
            ORDER BY
                CASE kana_type WHEN 'hiragana' THEN 0 ELSE 1 END,
                id
            LIMIT 1
        """, (shop_id,))
        row = cursor.fetchone()
        return BatchProgress(**dict(row)) if row else None


def update_batch_progress(progress_id: int, current_page: int,
                          total_pages: Optional[int] = None,
                          status: str = 'in_progress'):
    """バッチ進捗を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE batch_progress
            SET current_page = ?, total_pages = ?, status = ?,
                last_fetched_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (current_page, total_pages, status, progress_id))
        conn.commit()


def reset_batch_progress(shop_id: int):
    """バッチ進捗をリセット（再巡回用）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE batch_progress
            SET current_page = 1, status = 'pending', last_fetched_at = NULL
            WHERE shop_id = ?
        """, (shop_id,))
        conn.commit()


def get_batch_stats(shop_id: int) -> dict:
    """バッチ進捗統計"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                status,
                COUNT(*) as count
            FROM batch_progress
            WHERE shop_id = ?
            GROUP BY status
        """, (shop_id,))
        rows = cursor.fetchall()
        stats = {row["status"]: row["count"] for row in rows}
        return {
            "pending": stats.get("pending", 0),
            "in_progress": stats.get("in_progress", 0),
            "completed": stats.get("completed", 0),
        }


# =============================================================================
# 取得キュー操作
# =============================================================================

def add_to_fetch_queue(card_name: str, source: str = 'search', priority: int = 0) -> Optional[int]:
    """取得キューに追加（重複チェック付き）"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 同じカード名でpending/processingがあればスキップ
        cursor.execute("""
            SELECT id FROM fetch_queue
            WHERE card_name = ? AND status IN ('pending', 'processing')
        """, (card_name,))
        if cursor.fetchone():
            return None

        cursor.execute("""
            INSERT INTO fetch_queue (card_name, source, priority)
            VALUES (?, ?, ?)
        """, (card_name, source, priority))
        conn.commit()
        return cursor.lastrowid


def get_pending_queue_items(limit: int = 10) -> list[FetchQueue]:
    """処理待ちキューを取得（優先度順）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM fetch_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [FetchQueue(**dict(row)) for row in rows]


def update_queue_status(queue_id: int, status: str):
    """キューステータスを更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if status == 'done':
            cursor.execute("""
                UPDATE fetch_queue
                SET status = ?, processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, queue_id))
        else:
            cursor.execute("""
                UPDATE fetch_queue
                SET status = ?
                WHERE id = ?
            """, (status, queue_id))
        conn.commit()


def cleanup_old_queue(days: int = 7):
    """古いキューを削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM fetch_queue
            WHERE status = 'done' AND processed_at < datetime('now', ? || ' days')
        """, (f"-{days}",))
        deleted = cursor.rowcount
        conn.commit()
        return deleted


# =============================================================================
# 人気カード操作
# =============================================================================

def update_popular_cards(search_threshold: int = 5, click_threshold: int = 3,
                         days: int = 7, max_popular: int = 100):
    """人気カードフラグを更新"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 一旦全てリセット
        cursor.execute("UPDATE cards SET is_popular = 0")

        # 検索・クリック数が閾値以上のカードを人気に設定
        cursor.execute("""
            UPDATE cards SET is_popular = 1
            WHERE id IN (
                SELECT c.id
                FROM cards c
                LEFT JOIN search_logs sl ON sl.keyword = c.name
                    AND sl.searched_at > datetime('now', ? || ' days')
                LEFT JOIN clicks cl ON cl.card_id = c.id
                    AND cl.clicked_at > datetime('now', ? || ' days')
                GROUP BY c.id
                HAVING COUNT(DISTINCT sl.id) >= ? OR COUNT(DISTINCT cl.id) >= ?
                ORDER BY COUNT(DISTINCT sl.id) + COUNT(DISTINCT cl.id) DESC
                LIMIT ?
            )
        """, (f"-{days}", f"-{days}", search_threshold, click_threshold, max_popular))

        updated = cursor.rowcount
        conn.commit()
        print(f"Updated {updated} popular cards")
        return updated


def get_popular_cards() -> list[Card]:
    """人気カード一覧を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cards WHERE is_popular = 1
        """)
        rows = cursor.fetchall()
        return [Card(**dict(row)) for row in rows]


def get_cards_needing_price_update(hours: int = 24, limit: int = 50) -> list[Card]:
    """価格更新が必要なカードを取得（人気カード優先）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cards
            WHERE is_popular = 1
            AND (last_price_fetch_at IS NULL
                 OR last_price_fetch_at < datetime('now', ? || ' hours'))
            ORDER BY last_price_fetch_at ASC NULLS FIRST
            LIMIT ?
        """, (f"-{hours}", limit))
        rows = cursor.fetchall()
        return [Card(**dict(row)) for row in rows]


def update_card_price_fetch_time(card_id: int):
    """カードの価格取得時刻を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cards SET last_price_fetch_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (card_id,))
        conn.commit()


# =============================================================================
# バッチログ操作
# =============================================================================

def save_batch_log(batch_type: str, shop_name: str, status: str,
                   pages_processed: int = 0, cards_total: int = 0,
                   cards_new: int = 0, message: str = None,
                   started_at: str = None) -> int:
    """バッチ実行ログを保存"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO batch_logs
            (batch_type, shop_name, status, pages_processed, cards_total, cards_new, message, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (batch_type, shop_name, status, pages_processed, cards_total, cards_new, message, started_at))
        conn.commit()
        return cursor.lastrowid


def get_recent_batch_logs(limit: int = 10, per_shop: bool = False) -> list[dict]:
    """最近のバッチ実行ログを取得

    Args:
        limit: 取得件数（per_shop=Falseの場合に使用）
        per_shop: Trueの場合、各ショップの最新1件のみを取得
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if per_shop:
            # 各ショップの最新ログを取得
            cursor.execute("""
                SELECT * FROM batch_logs b1
                WHERE finished_at = (
                    SELECT MAX(finished_at) FROM batch_logs b2
                    WHERE b2.shop_name = b1.shop_name
                )
                ORDER BY finished_at DESC
            """)
        else:
            cursor.execute("""
                SELECT * FROM batch_logs
                ORDER BY finished_at DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_latest_crawl_result() -> dict | None:
    """最新の巡回バッチ結果を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM batch_logs
            WHERE batch_type = 'crawl' AND status = 'success'
            ORDER BY finished_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# カード登録（拡張版）
# =============================================================================

# =============================================================================
# ユーザー操作
# =============================================================================

def create_user(username: str, email: str, password_hash: str, role: str = 'user') -> User:
    """ユーザーを作成"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (username, email, password_hash, role))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        row = cursor.fetchone()
        return User(**dict(row))


def get_user_by_username(username: str) -> Optional[User]:
    """ユーザー名でユーザーを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return User(**dict(row)) if row else None


def get_user_by_email(email: str) -> Optional[User]:
    """メールアドレスでユーザーを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return User(**dict(row)) if row else None


def get_user_by_id(user_id: int) -> Optional[User]:
    """IDでユーザーを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return User(**dict(row)) if row else None


def get_all_users() -> list[User]:
    """全ユーザーを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [User(**dict(row)) for row in rows]


# =============================================================================
# お気に入り操作
# =============================================================================

def add_favorite(user_id: int, card_id: int) -> Optional[Favorite]:
    """お気に入りを追加"""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO favorites (user_id, card_id)
                VALUES (?, ?)
            """, (user_id, card_id))
            conn.commit()
            cursor.execute("SELECT * FROM favorites WHERE id = ?", (cursor.lastrowid,))
            row = cursor.fetchone()
            return Favorite(**dict(row))
        except sqlite3.IntegrityError:
            return None


def remove_favorite(user_id: int, card_id: int) -> bool:
    """お気に入りを削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM favorites WHERE user_id = ? AND card_id = ?
        """, (user_id, card_id))
        conn.commit()
        return cursor.rowcount > 0


def get_user_favorites(user_id: int) -> list[dict]:
    """ユーザーのお気に入りカード一覧を取得（価格情報付き）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id as favorite_id, f.created_at as favorited_at,
                   c.id as card_id, c.name as card_name
            FROM favorites f
            JOIN cards c ON f.card_id = c.id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_user_favorite_ids(user_id: int) -> list[int]:
    """ユーザーのお気に入りカードIDリストを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT card_id FROM favorites WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return [row['card_id'] for row in rows]


def is_favorite(user_id: int, card_id: int) -> bool:
    """お気に入り登録済みかチェック"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM favorites WHERE user_id = ? AND card_id = ?
        """, (user_id, card_id))
        return cursor.fetchone() is not None


# =============================================================================
# 管理者招待コード操作
# =============================================================================

def create_admin_invite(code: str, created_by: int) -> AdminInvite:
    """管理者招待コードを作成"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_invites (code, created_by)
            VALUES (?, ?)
        """, (code, created_by))
        conn.commit()
        cursor.execute("SELECT * FROM admin_invites WHERE id = ?", (cursor.lastrowid,))
        row = cursor.fetchone()
        return AdminInvite(**dict(row))


def get_admin_invite(code: str) -> Optional[AdminInvite]:
    """招待コードを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_invites WHERE code = ?", (code,))
        row = cursor.fetchone()
        return AdminInvite(**dict(row)) if row else None


def use_admin_invite(code: str, user_id: int) -> bool:
    """招待コードを使用済みにする"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE admin_invites
            SET used_by = ?, used_at = CURRENT_TIMESTAMP
            WHERE code = ? AND used_by IS NULL
        """, (user_id, code))
        conn.commit()
        return cursor.rowcount > 0


def get_all_admin_invites(created_by: Optional[int] = None) -> list[AdminInvite]:
    """招待コード一覧を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if created_by:
            cursor.execute("""
                SELECT * FROM admin_invites
                WHERE created_by = ?
                ORDER BY created_at DESC
            """, (created_by,))
        else:
            cursor.execute("SELECT * FROM admin_invites ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [AdminInvite(**dict(row)) for row in rows]


# =============================================================================
# 人気キーワード操作
# =============================================================================

def get_featured_keywords(active_only: bool = True) -> list[FeaturedKeyword]:
    """人気キーワード一覧を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("""
                SELECT * FROM featured_keywords
                WHERE is_active = 1
                ORDER BY display_order ASC, id ASC
            """)
        else:
            cursor.execute("""
                SELECT * FROM featured_keywords
                ORDER BY display_order ASC, id ASC
            """)
        rows = cursor.fetchall()
        return [FeaturedKeyword(**dict(row)) for row in rows]


def add_featured_keyword(keyword: str, created_by: int) -> FeaturedKeyword:
    """人気キーワードを追加"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 最大のdisplay_orderを取得
        cursor.execute("SELECT MAX(display_order) FROM featured_keywords")
        max_order = cursor.fetchone()[0] or 0

        cursor.execute("""
            INSERT INTO featured_keywords (keyword, display_order, created_by)
            VALUES (?, ?, ?)
        """, (keyword, max_order + 1, created_by))
        conn.commit()

        cursor.execute("SELECT * FROM featured_keywords WHERE id = ?", (cursor.lastrowid,))
        row = cursor.fetchone()
        return FeaturedKeyword(**dict(row))


def update_featured_keyword(keyword_id: int, keyword: str = None,
                            is_active: int = None) -> Optional[FeaturedKeyword]:
    """人気キーワードを更新"""
    with get_connection() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if keyword is not None:
            updates.append("keyword = ?")
            params.append(keyword)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)

        if not updates:
            return None

        params.append(keyword_id)
        cursor.execute(f"""
            UPDATE featured_keywords
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        conn.commit()

        cursor.execute("SELECT * FROM featured_keywords WHERE id = ?", (keyword_id,))
        row = cursor.fetchone()
        return FeaturedKeyword(**dict(row)) if row else None


def delete_featured_keyword(keyword_id: int) -> bool:
    """人気キーワードを削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM featured_keywords WHERE id = ?", (keyword_id,))
        conn.commit()
        return cursor.rowcount > 0


def reorder_featured_keywords(keyword_ids: list[int]) -> bool:
    """人気キーワードの表示順を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for order, keyword_id in enumerate(keyword_ids):
            cursor.execute("""
                UPDATE featured_keywords
                SET display_order = ?
                WHERE id = ?
            """, (order, keyword_id))
        conn.commit()
        return True


# =============================================================================
# カード登録（拡張版）
# =============================================================================

def get_or_create_card_v2(name: str, card_no: str = None,
                          source_shop_id: int = None,
                          detail_url: str = None) -> Card:
    """カードを取得または作成（v2拡張版）"""
    name_normalized = normalize_card_name(name)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 既存カード検索
        cursor.execute("SELECT * FROM cards WHERE name = ?", (name,))
        row = cursor.fetchone()

        if row:
            # 既存カードにdetail_urlがなければ更新
            if detail_url and not row["detail_url"]:
                cursor.execute("""
                    UPDATE cards SET detail_url = ?, card_no = ?
                    WHERE id = ?
                """, (detail_url, card_no, row["id"]))
                conn.commit()
            return Card(**dict(row))

        # 新規作成
        cursor.execute("""
            INSERT INTO cards (name, name_normalized, card_no, source_shop_id, detail_url)
            VALUES (?, ?, ?, ?, ?)
        """, (name, name_normalized, card_no, source_shop_id, detail_url))
        conn.commit()

        cursor.execute("SELECT * FROM cards WHERE id = ?", (cursor.lastrowid,))
        row = cursor.fetchone()
        return Card(**dict(row))


# =============================================================================
# 初期化実行
# =============================================================================

def get_card_by_id(card_id: int) -> Optional[Card]:
    """IDでカードを取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        return Card(**dict(row)) if row else None


def get_admin_stats() -> dict:
    """管理者用統計情報"""
    with get_connection() as conn:
        cursor = conn.cursor()

        stats = get_database_stats()

        # ユーザー数
        cursor.execute("SELECT COUNT(*) FROM users")
        stats["users"] = cursor.fetchone()[0]

        # 管理者数
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        stats["admins"] = cursor.fetchone()[0]

        # お気に入り登録数
        cursor.execute("SELECT COUNT(*) FROM favorites")
        stats["favorites"] = cursor.fetchone()[0]

        # 未使用招待コード数
        cursor.execute("SELECT COUNT(*) FROM admin_invites WHERE used_by IS NULL")
        stats["unused_invites"] = cursor.fetchone()[0]

        return stats


# =============================================================================
# Amazon商品操作
# =============================================================================

from models import AmazonProduct


def get_amazon_products(active_only: bool = True) -> list[AmazonProduct]:
    """Amazon商品一覧を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM amazon_products WHERE is_active = 1 ORDER BY display_order")
        else:
            cursor.execute("SELECT * FROM amazon_products ORDER BY display_order")
        rows = cursor.fetchall()
        return [AmazonProduct(**dict(row)) for row in rows]


def get_amazon_product_by_id(product_id: int) -> Optional[AmazonProduct]:
    """IDでAmazon商品を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM amazon_products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if row:
            return AmazonProduct(**dict(row))
        return None


def add_amazon_product(asin: str, name: str, price: int, image_url: str, affiliate_tag: str) -> AmazonProduct:
    """Amazon商品を追加"""
    affiliate_url = f"https://www.amazon.co.jp/dp/{asin}?tag={affiliate_tag}"

    with get_connection() as conn:
        cursor = conn.cursor()

        # 現在の最大display_orderを取得
        cursor.execute("SELECT MAX(display_order) FROM amazon_products")
        max_order = cursor.fetchone()[0] or 0

        cursor.execute("""
            INSERT INTO amazon_products (asin, name, price, image_url, affiliate_url, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (asin, name, price, image_url, affiliate_url, max_order + 1))

        conn.commit()
        product_id = cursor.lastrowid

        return get_amazon_product_by_id(product_id)


def update_amazon_product(product_id: int, name: str = None, price: int = None,
                          image_url: str = None, is_active: int = None) -> Optional[AmazonProduct]:
    """Amazon商品を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(product_id)

            cursor.execute(f"""
                UPDATE amazon_products SET {', '.join(updates)} WHERE id = ?
            """, params)
            conn.commit()

    return get_amazon_product_by_id(product_id)


def delete_amazon_product(product_id: int) -> bool:
    """Amazon商品を削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM amazon_products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0


def reorder_amazon_products(product_ids: list[int]):
    """Amazon商品の表示順を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for order, product_id in enumerate(product_ids):
            cursor.execute(
                "UPDATE amazon_products SET display_order = ? WHERE id = ?",
                (order, product_id)
            )
        conn.commit()


# ==================== 楽天商品関連 ====================

from models import RakutenProduct


def get_rakuten_products(active_only: bool = True) -> list[RakutenProduct]:
    """楽天商品一覧を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM rakuten_products WHERE is_active = 1 ORDER BY display_order")
        else:
            cursor.execute("SELECT * FROM rakuten_products ORDER BY display_order")
        rows = cursor.fetchall()
        return [RakutenProduct(**dict(row)) for row in rows]


def get_rakuten_product_by_id(product_id: int) -> Optional[RakutenProduct]:
    """IDで楽天商品を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rakuten_products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if row:
            return RakutenProduct(**dict(row))
        return None


def add_rakuten_product(item_code: str, name: str, price: int, image_url: str, affiliate_url: str) -> RakutenProduct:
    """楽天商品を追加"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 現在の最大display_orderを取得
        cursor.execute("SELECT MAX(display_order) FROM rakuten_products")
        max_order = cursor.fetchone()[0] or 0

        cursor.execute("""
            INSERT INTO rakuten_products (item_code, name, price, image_url, affiliate_url, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item_code, name, price, image_url, affiliate_url, max_order + 1))

        conn.commit()
        product_id = cursor.lastrowid

        return get_rakuten_product_by_id(product_id)


def update_rakuten_product(product_id: int, name: str = None, price: int = None,
                           image_url: str = None, is_active: int = None) -> Optional[RakutenProduct]:
    """楽天商品を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(is_active)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(product_id)

            cursor.execute(f"""
                UPDATE rakuten_products SET {', '.join(updates)} WHERE id = ?
            """, params)
            conn.commit()

    return get_rakuten_product_by_id(product_id)


def delete_rakuten_product(product_id: int) -> bool:
    """楽天商品を削除"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rakuten_products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0


def reorder_rakuten_products(product_ids: list[int]):
    """楽天商品の表示順を更新"""
    with get_connection() as conn:
        cursor = conn.cursor()
        for order, product_id in enumerate(product_ids):
            cursor.execute(
                "UPDATE rakuten_products SET display_order = ? WHERE id = ?",
                (order, product_id)
            )
        conn.commit()


if __name__ == "__main__":
    # 直接実行時にDB初期化
    init_database()
    migrate_v2()  # v2マイグレーション追加
    migrate_v3_auth()  # v3認証マイグレーション追加
    migrate_v4_featured_keywords()  # v4人気キーワードマイグレーション追加
    migrate_v5_amazon_products()  # v5 Amazon商品マイグレーション追加
    init_shops()
    print("\nDatabase stats:")
    print(get_database_stats())
