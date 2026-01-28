#!/usr/bin/env python3
"""
キュー処理バッチ
fetch_queueに溜まったカード名を処理して価格を取得する

使用方法:
    python batch_queue.py              # キュー処理実行
    python batch_queue.py --limit 5    # 処理件数を指定
    python batch_queue.py --status     # キュー状況確認

cron設定例（毎時30分）:
    30 * * * * cd /home/ubuntu/project/backend && python batch_queue.py >> /var/log/card-queue-batch.log 2>&1
"""
import sys
import os
import time
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# fcntlはLinux専用
if sys.platform != "win32":
    import fcntl

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_database,
    init_shops,
    get_connection,
    get_shop_by_name,
    get_or_create_card,
    save_price_if_changed,
    get_pending_queue_items,
    update_queue_status,
    cleanup_old_queue,
)
from scrapers import (
    CardrushScraper,
    TieroneScraper,
    BatosukiScraper,
    FullaheadScraper,
    HobbystationScraper,
)
from scrapers.base import Product

# ロックファイルパス
LOCK_FILE = Path(__file__).parent / ".batch_queue.lock"

# スクレイパー定義
SCRAPER_CLASSES = [
    ("Tier One", TieroneScraper),
    ("フルアヘッド", FullaheadScraper),
    ("カードラッシュ", CardrushScraper),
    ("バトスキ", BatosukiScraper),
    ("ホビーステーション", HobbystationScraper),
]

# 設定
DEFAULT_LIMIT = 10  # 1回あたりの処理件数
ITEM_INTERVAL = 3   # アイテム間のインターバル（秒）


def log(message: str):
    """タイムスタンプ付きログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def acquire_lock() -> bool:
    """ファイルロック取得"""
    if sys.platform == "win32":
        return True

    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        acquire_lock._fd = lock_fd
        return True
    except (IOError, OSError):
        return False


def release_lock():
    """ファイルロック解放"""
    if sys.platform == "win32":
        return

    try:
        if hasattr(acquire_lock, "_fd"):
            fcntl.flock(acquire_lock._fd, fcntl.LOCK_UN)
            acquire_lock._fd.close()
            LOCK_FILE.unlink(missing_ok=True)
    except Exception as e:
        log(f"Unlock error: {e}")


async def fetch_and_save(keyword: str) -> dict:
    """
    キーワードで検索して価格を保存

    Returns:
        {"products": N, "saved": N}
    """
    total_products = 0
    total_saved = 0

    for shop_name, scraper_class in SCRAPER_CLASSES:
        scraper = scraper_class()
        try:
            products = await scraper.search(keyword)

            # キーワードでフィルタ
            filtered = [p for p in products if keyword.lower() in p.name.lower()]

            # DB保存
            shop = get_shop_by_name(shop_name)
            if shop and filtered:
                for product in filtered:
                    card = get_or_create_card(product.name)
                    price_id = save_price_if_changed(
                        card_id=card.id,
                        shop_id=shop.id,
                        price=product.price,
                        stock=product.stock,
                        stock_text=product.stock_text,
                        url=product.url,
                        image_url=product.image_url,
                    )
                    total_products += 1
                    if price_id:
                        total_saved += 1

                log(f"  [{shop_name}] {len(filtered)} items")

        except Exception as e:
            log(f"  [{shop_name}] ERROR: {e}")
        finally:
            await scraper.close()

        # Selenium系の後は待機
        if scraper_class in [CardrushScraper, BatosukiScraper, HobbystationScraper]:
            await asyncio.sleep(1)

    return {"products": total_products, "saved": total_saved}


async def process_queue(limit: int = DEFAULT_LIMIT):
    """キュー処理メイン"""
    log("=" * 60)
    log("Queue processing started")
    log("=" * 60)

    # DB初期化
    init_database()
    init_shops()

    # 古いキューを削除
    deleted = cleanup_old_queue(days=7)
    if deleted:
        log(f"Cleaned up {deleted} old queue items")

    # 処理待ちキューを取得
    queue_items = get_pending_queue_items(limit=limit)

    if not queue_items:
        log("No pending queue items")
        return

    log(f"Found {len(queue_items)} items to process")

    total_start = time.time()
    total_products = 0
    total_saved = 0

    for i, item in enumerate(queue_items, 1):
        log(f"\n[{i}/{len(queue_items)}] Processing: {item.card_name}")

        # ステータスを処理中に更新
        update_queue_status(item.id, 'processing')

        try:
            # 検索・保存実行
            result = await fetch_and_save(item.card_name)
            total_products += result["products"]
            total_saved += result["saved"]

            # ステータスを完了に更新
            update_queue_status(item.id, 'done')
            log(f"  Completed: {result['products']} products, {result['saved']} saved")

        except Exception as e:
            log(f"  ERROR: {e}")
            # エラー時はpendingに戻す
            update_queue_status(item.id, 'pending')

        # インターバル
        if i < len(queue_items):
            await asyncio.sleep(ITEM_INTERVAL)

    # 完了
    elapsed = time.time() - total_start
    log("\n" + "=" * 60)
    log("Queue processing completed")
    log(f"  Items processed: {len(queue_items)}")
    log(f"  Total products: {total_products}")
    log(f"  Total saved: {total_saved}")
    log(f"  Elapsed: {elapsed:.1f}s")
    log("=" * 60)


def show_status():
    """キュー状況表示"""
    init_database()

    with get_connection() as conn:
        cursor = conn.cursor()

        # ステータス別集計
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM fetch_queue
            GROUP BY status
        """)
        stats = {row["status"]: row["count"] for row in cursor.fetchall()}

        # 最新の待機アイテム
        cursor.execute("""
            SELECT card_name, source, created_at
            FROM fetch_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT 10
        """)
        pending = cursor.fetchall()

    print("\n=== Queue Status ===")
    print(f"  Pending: {stats.get('pending', 0)}")
    print(f"  Processing: {stats.get('processing', 0)}")
    print(f"  Done: {stats.get('done', 0)}")

    if pending:
        print("\n=== Pending Items (top 10) ===")
        for item in pending:
            print(f"  - {item['card_name']} ({item['source']}, {item['created_at']})")


def main():
    parser = argparse.ArgumentParser(description="Queue processor for card price fetching")
    parser.add_argument("--limit", "-l", type=int, default=DEFAULT_LIMIT,
                        help=f"Number of items to process (default: {DEFAULT_LIMIT})")
    parser.add_argument("--status", "-s", action="store_true", help="Show queue status")
    parser.add_argument("--no-lock", action="store_true", help="Skip lock check")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # ロック取得
    if not args.no_lock and not acquire_lock():
        log("Another batch process is running. Exiting.")
        sys.exit(1)

    try:
        asyncio.run(process_queue(limit=args.limit))
    finally:
        release_lock()


if __name__ == "__main__":
    main()
