#!/usr/bin/env python3
"""
バッチ処理: 価格データ定期取得

使用方法:
    python batch.py                    # 全キーワードを取得
    python batch.py --keyword "カード名"  # 特定キーワードのみ
    python batch.py --stats            # 統計情報表示

cron設定例（30分ごと）:
    */30 * * * * cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch.py >> /var/log/card-price-batch.log 2>&1
"""
import sys
import os
import time
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# fcntlはLinux専用（Windowsでは使用不可）
if sys.platform != "win32":
    import fcntl

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_database,
    init_shops,
    get_all_shops,
    get_shop_by_name,
    get_or_create_card,
    save_price_if_changed,
    get_database_stats,
)
from scrapers import (
    CardrushScraper,
    TieroneScraper,
    BatosukiScraper,
    FullaheadScraper,
    YuyuteiScraper,
    HobbystationScraper,
)
from scrapers.base import Product

# ロックファイルパス（二重起動防止）
LOCK_FILE = Path(__file__).parent / ".batch.lock"

# キーワードリストファイル
KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"

# デフォルトキーワード（keywords.txtがない場合に使用）
DEFAULT_KEYWORDS = [
    "ジークフリード",
    "アレックス",
    "光龍騎神",
    "超神星龍",
    "ゴッドゼクス",
    "魔界七将",
    "六絶神",
    "創界神",
    "転醒",
    "契約",
]

# スクレイパー定義
# 順序: httpx系を先に、Selenium系を後に（メモリ効率）
SCRAPER_CLASSES = [
    # httpx系（軽量・並行可能だが順次実行）
    ("Tier One", TieroneScraper),
    ("フルアヘッド", FullaheadScraper),
    ("遊々亭", YuyuteiScraper),  # 現在403エラーで動作不可
    # Selenium系（重い・順次実行必須）
    ("カードラッシュ", CardrushScraper),
    ("バトスキ", BatosukiScraper),
    ("ホビーステーション", HobbystationScraper),
]


def log(message: str):
    """タイムスタンプ付きログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def load_keywords() -> list[str]:
    """キーワードリストを読み込み"""
    if KEYWORDS_FILE.exists():
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if keywords:
            log(f"Loaded {len(keywords)} keywords from {KEYWORDS_FILE}")
            return keywords

    log(f"Using {len(DEFAULT_KEYWORDS)} default keywords")
    return DEFAULT_KEYWORDS


def acquire_lock() -> bool:
    """ファイルロック取得（二重起動防止）"""
    try:
        # ロックファイルを作成/オープン
        lock_fd = open(LOCK_FILE, "w")
        # 非ブロッキングで排他ロック取得を試みる
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # ロック取得成功 - PIDを書き込み
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        # ファイルディスクリプタを保持（閉じるとロック解除される）
        acquire_lock._fd = lock_fd
        return True
    except (IOError, OSError):
        # ロック取得失敗 = 他のプロセスが実行中
        return False
    except Exception as e:
        log(f"Lock error: {e}")
        return False


def release_lock():
    """ファイルロック解放"""
    try:
        if hasattr(acquire_lock, "_fd"):
            fcntl.flock(acquire_lock._fd, fcntl.LOCK_UN)
            acquire_lock._fd.close()
            LOCK_FILE.unlink(missing_ok=True)
    except Exception as e:
        log(f"Unlock error: {e}")


async def fetch_shop_prices(scraper_class, keyword: str) -> tuple[str, list[Product], float]:
    """
    1つのショップから価格を取得

    Returns:
        (shop_name, products, elapsed_seconds)
    """
    scraper = scraper_class()
    shop_name = scraper.site_name
    start_time = time.time()

    try:
        products = await scraper.search(keyword)
        elapsed = time.time() - start_time
        return (shop_name, products, elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        log(f"  [{shop_name}] ERROR: {e}")
        return (shop_name, [], elapsed)
    finally:
        await scraper.close()


def save_products_to_db(products: list[Product], shop_name: str) -> tuple[int, int]:
    """
    商品データをDBに保存

    Returns:
        (saved_count, skipped_count)
    """
    shop = get_shop_by_name(shop_name)
    if not shop:
        log(f"  Shop not found: {shop_name}")
        return (0, 0)

    saved = 0
    skipped = 0

    for product in products:
        try:
            # カードを取得または作成
            card = get_or_create_card(product.name)

            # 価格を保存（変更がある場合のみ）
            price_id = save_price_if_changed(
                card_id=card.id,
                shop_id=shop.id,
                price=product.price,
                stock=product.stock,
                stock_text=product.stock_text,
                url=product.url,
                image_url=product.image_url,
            )

            if price_id:
                saved += 1
            else:
                skipped += 1

        except Exception as e:
            log(f"  DB save error [{product.name}]: {e}")
            continue

    return (saved, skipped)


async def process_keyword(keyword: str) -> dict:
    """
    1つのキーワードを全ショップで検索してDB保存

    Returns:
        結果統計
    """
    log(f"Processing keyword: {keyword}")

    results = {
        "keyword": keyword,
        "shops": {},
        "total_products": 0,
        "total_saved": 0,
        "total_skipped": 0,
        "total_errors": 0,
    }

    # 各ショップを順次処理（Selenium同時起動防止）
    for shop_name, scraper_class in SCRAPER_CLASSES:
        log(f"  [{shop_name}] Fetching...")

        # 価格取得
        _, products, elapsed = await fetch_shop_prices(scraper_class, keyword)

        if products:
            # DB保存
            saved, skipped = save_products_to_db(products, shop_name)
            results["shops"][shop_name] = {
                "products": len(products),
                "saved": saved,
                "skipped": skipped,
                "elapsed": elapsed,
            }
            results["total_products"] += len(products)
            results["total_saved"] += saved
            results["total_skipped"] += skipped
            log(f"  [{shop_name}] Found {len(products)}, saved {saved}, skipped {skipped} ({elapsed:.1f}s)")
        else:
            results["shops"][shop_name] = {
                "products": 0,
                "saved": 0,
                "skipped": 0,
                "elapsed": elapsed,
                "error": True,
            }
            results["total_errors"] += 1
            log(f"  [{shop_name}] No results ({elapsed:.1f}s)")

        # Seleniumスクレイパー後は少し待機（メモリ解放）
        if scraper_class in [CardrushScraper, BatosukiScraper, HobbystationScraper]:
            await asyncio.sleep(2)

    return results


async def run_batch(keywords: list[str] = None):
    """バッチ処理メイン"""
    log("=" * 60)
    log("Batch started")
    log("=" * 60)

    # DB初期化確認
    init_database()
    init_shops()

    # キーワードリスト
    if keywords is None:
        keywords = load_keywords()

    total_start = time.time()
    all_results = []

    for i, keyword in enumerate(keywords, 1):
        log(f"\n[{i}/{len(keywords)}] Keyword: {keyword}")
        result = await process_keyword(keyword)
        all_results.append(result)

        # キーワード間の待機（サーバー負荷軽減）
        if i < len(keywords):
            await asyncio.sleep(5)

    # 集計
    total_elapsed = time.time() - total_start
    total_products = sum(r["total_products"] for r in all_results)
    total_saved = sum(r["total_saved"] for r in all_results)
    total_skipped = sum(r["total_skipped"] for r in all_results)

    log("\n" + "=" * 60)
    log("Batch completed")
    log(f"  Keywords: {len(keywords)}")
    log(f"  Total products: {total_products}")
    log(f"  Saved: {total_saved}")
    log(f"  Skipped (no change): {total_skipped}")
    log(f"  Elapsed: {total_elapsed:.1f}s")
    log("=" * 60)

    return all_results


def show_stats():
    """DB統計表示"""
    init_database()
    stats = get_database_stats()
    print("\n=== Database Statistics ===")
    print(f"  Shops: {stats['shops']}")
    print(f"  Cards: {stats['cards']}")
    print(f"  Prices: {stats['prices']}")
    print(f"  Clicks: {stats['clicks']}")
    print(f"  Oldest price: {stats['oldest_price']}")
    print(f"  Newest price: {stats['newest_price']}")


def main():
    parser = argparse.ArgumentParser(description="Card price batch fetcher")
    parser.add_argument("--keyword", "-k", type=str, help="Fetch specific keyword only")
    parser.add_argument("--stats", "-s", action="store_true", help="Show database statistics")
    parser.add_argument("--no-lock", action="store_true", help="Skip lock check (for testing)")
    args = parser.parse_args()

    # 統計表示モード
    if args.stats:
        show_stats()
        return

    # 二重起動チェック（Windowsではスキップ）
    if sys.platform != "win32" and not args.no_lock:
        if not acquire_lock():
            log("Another batch process is running. Exiting.")
            sys.exit(1)

    try:
        # 特定キーワードモード
        if args.keyword:
            asyncio.run(run_batch([args.keyword]))
        else:
            asyncio.run(run_batch())
    finally:
        if sys.platform != "win32" and not args.no_lock:
            release_lock()


if __name__ == "__main__":
    main()
