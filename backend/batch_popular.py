#!/usr/bin/env python3
"""
人気カード価格更新バッチ
is_popular=1のカードを優先的に価格更新する

使用方法:
    python batch_popular.py              # 人気カードの価格を更新
    python batch_popular.py --limit 20   # 更新件数を指定
    python batch_popular.py --stats      # 人気カード統計表示
    python batch_popular.py --refresh    # 人気カード判定を更新

cron設定例（毎日6時）:
    0 6 * * * cd /home/ubuntu/project/backend && python batch_popular.py >> /var/log/card-popular-batch.log 2>&1
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
    get_shop_by_name,
    get_or_create_card,
    save_price_if_changed,
    get_popular_cards,
    get_cards_needing_price_update,
    update_card_price_fetch_time,
    update_popular_cards,
    get_database_stats,
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
LOCK_FILE = Path(__file__).parent / ".batch_popular.lock"

# スクレイパー定義（httpx系を先に、Selenium系を後に）
SCRAPER_CLASSES = [
    ("Tier One", TieroneScraper),
    ("フルアヘッド", FullaheadScraper),
    ("カードラッシュ", CardrushScraper),
    ("バトスキ", BatosukiScraper),
    ("ホビーステーション", HobbystationScraper),
]

# 設定
DEFAULT_LIMIT = 50  # 1回あたりの更新件数
CARD_INTERVAL = 3   # カード間のインターバル（秒）


def log(message: str):
    """タイムスタンプ付きログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def acquire_lock() -> bool:
    """ファイルロック取得"""
    if sys.platform == "win32":
        return True  # Windowsではスキップ

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


async def fetch_card_prices(card_name: str) -> list[tuple[str, list[Product]]]:
    """
    1つのカードの価格を全ショップから取得

    Returns:
        [(shop_name, products), ...]
    """
    results = []

    for shop_name, scraper_class in SCRAPER_CLASSES:
        scraper = scraper_class()
        try:
            products = await scraper.search(card_name)
            # カード名でフィルタ（完全一致に近いもののみ）
            filtered = [p for p in products if card_name.lower() in p.name.lower()]
            results.append((shop_name, filtered))
        except Exception as e:
            log(f"  [{shop_name}] ERROR: {e}")
            results.append((shop_name, []))
        finally:
            await scraper.close()

        # Selenium系の後は待機
        if scraper_class in [CardrushScraper, BatosukiScraper, HobbystationScraper]:
            await asyncio.sleep(1)

    return results


def save_card_prices(card_name: str, shop_results: list[tuple[str, list[Product]]]) -> dict:
    """
    カードの価格をDBに保存

    Returns:
        {shop_name: {"products": N, "saved": N, "skipped": N}, ...}
    """
    stats = {}

    for shop_name, products in shop_results:
        shop = get_shop_by_name(shop_name)
        if not shop:
            continue

        saved = 0
        skipped = 0

        for product in products:
            try:
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

                if price_id:
                    saved += 1
                else:
                    skipped += 1
            except Exception as e:
                log(f"    DB error [{product.name}]: {e}")

        stats[shop_name] = {
            "products": len(products),
            "saved": saved,
            "skipped": skipped,
        }

    return stats


async def update_popular_card_prices(limit: int = DEFAULT_LIMIT):
    """人気カードの価格を更新"""
    log("=" * 60)
    log("Popular cards price update started")
    log("=" * 60)

    # DB初期化
    init_database()
    init_shops()

    # 価格更新が必要な人気カードを取得
    cards = get_cards_needing_price_update(hours=24, limit=limit)

    if not cards:
        log("No popular cards need updating")
        return

    log(f"Found {len(cards)} cards to update")

    total_start = time.time()
    total_saved = 0
    total_products = 0

    for i, card in enumerate(cards, 1):
        log(f"\n[{i}/{len(cards)}] {card.name}")

        # 価格取得
        shop_results = await fetch_card_prices(card.name)

        # DB保存
        stats = save_card_prices(card.name, shop_results)

        # 統計出力
        for shop_name, shop_stat in stats.items():
            if shop_stat["products"] > 0:
                log(f"  [{shop_name}] {shop_stat['products']} items, saved {shop_stat['saved']}")
                total_products += shop_stat["products"]
                total_saved += shop_stat["saved"]

        # 価格取得時刻を更新
        update_card_price_fetch_time(card.id)

        # インターバル
        if i < len(cards):
            await asyncio.sleep(CARD_INTERVAL)

    # 完了
    elapsed = time.time() - total_start
    log("\n" + "=" * 60)
    log("Popular cards update completed")
    log(f"  Cards processed: {len(cards)}")
    log(f"  Total products: {total_products}")
    log(f"  Total saved: {total_saved}")
    log(f"  Elapsed: {elapsed:.1f}s")
    log("=" * 60)


def refresh_popular_cards():
    """人気カード判定を更新"""
    log("Refreshing popular cards...")
    init_database()

    updated = update_popular_cards(
        search_threshold=5,
        click_threshold=3,
        days=7,
        max_popular=100
    )

    log(f"Popular cards updated: {updated} cards")


def show_stats():
    """人気カード統計表示"""
    init_database()

    # 人気カード一覧
    popular = get_popular_cards()
    db_stats = get_database_stats()

    print("\n=== Popular Cards Statistics ===")
    print(f"  Total popular cards: {len(popular)}")
    print(f"  Total cards in DB: {db_stats['cards']}")

    if popular:
        print("\n=== Popular Cards List ===")
        for card in popular[:20]:  # 上位20件のみ表示
            last_fetch = getattr(card, 'last_price_fetch_at', None) or 'Never'
            print(f"  - {card.name} (last update: {last_fetch})")

        if len(popular) > 20:
            print(f"  ... and {len(popular) - 20} more")


def main():
    parser = argparse.ArgumentParser(description="Popular cards price updater")
    parser.add_argument("--limit", "-l", type=int, default=DEFAULT_LIMIT,
                        help=f"Number of cards to update (default: {DEFAULT_LIMIT})")
    parser.add_argument("--stats", "-s", action="store_true", help="Show popular cards statistics")
    parser.add_argument("--refresh", "-r", action="store_true", help="Refresh popular cards list")
    parser.add_argument("--no-lock", action="store_true", help="Skip lock check")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.refresh:
        refresh_popular_cards()
        return

    # ロック取得
    if not args.no_lock and not acquire_lock():
        log("Another batch process is running. Exiting.")
        sys.exit(1)

    try:
        asyncio.run(update_popular_card_prices(limit=args.limit))
    finally:
        release_lock()


if __name__ == "__main__":
    main()
