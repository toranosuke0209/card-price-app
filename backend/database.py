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

from models import Shop, Card, Price, Click, SearchLog

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
# 初期化実行
# =============================================================================

if __name__ == "__main__":
    # 直接実行時にDB初期化
    init_database()
    init_shops()
    print("\nDatabase stats:")
    print(get_database_stats())
