"""
人気キーワードの価格更新スクリプト

1日2回cronで実行、または管理者が手動で実行
各ショップの検索機能を使ってキーワードの価格を取得する
"""
import time
import re
import sys
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from database import (
    get_featured_keywords,
    get_or_create_card,
    get_shop_by_name,
    save_price_if_changed,
    get_connection,
)


# 設定
REQUEST_TIMEOUT = 30.0
INTERVAL_BETWEEN_SHOPS = 2  # ショップ間の待機秒数
INTERVAL_BETWEEN_KEYWORDS = 1  # キーワード間の待機秒数

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def log(message: str):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def search_cardrush(client: httpx.Client, keyword: str) -> list[dict]:
    """カードラッシュで検索"""
    results = []
    try:
        url = f"https://www.cardrush-bs.jp/?mode=srh&keyword={keyword}"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select(".indexItemBox")

        for item in items[:20]:  # 最大20件
            try:
                name_elem = item.select_one(".itemName a")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)
                detail_url = name_elem.get("href", "")

                price_elem = item.select_one(".itemPrice")
                price = 0
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                stock_elem = item.select_one(".itemStock")
                stock_text = stock_elem.get_text(strip=True) if stock_elem else ""
                stock = 0 if "売切" in stock_text or "品切" in stock_text else 1

                img_elem = item.select_one("img")
                image_url = img_elem.get("src", "") if img_elem else ""

                results.append({
                    "name": name,
                    "price": price,
                    "stock": stock,
                    "stock_text": stock_text or ("在庫あり" if stock > 0 else "売切"),
                    "url": detail_url,
                    "image_url": image_url,
                })
            except Exception:
                continue

    except Exception as e:
        log(f"  カードラッシュ検索エラー: {e}")

    return results


def search_fullahead(client: httpx.Client, keyword: str) -> list[dict]:
    """フルアヘッドで検索"""
    results = []
    try:
        url = f"https://fullahead-tcg.com/shop/shopbrand.html?search={keyword}"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select("a[href*='/shop/shopdetail.html']")

        seen_urls = set()
        for link in items[:20]:
            try:
                detail_url = link.get("href", "")
                if not detail_url or detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                if not detail_url.startswith("http"):
                    detail_url = "https://fullahead-tcg.com" + detail_url

                # リンク内からデータ取得
                name_elem = link.select_one("span.itemName")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                # 価格
                price = 0
                price_elem = link.select_one("span.itemPrice strong")
                if not price_elem:
                    price_elem = link.parent.select_one("span.itemPrice strong") if link.parent else None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                # 在庫
                stock = 1
                stock_text = "在庫あり"
                stock_elem = link.select_one("span.firing")
                if not stock_elem:
                    stock_elem = link.parent.select_one("span.firing") if link.parent else None
                if stock_elem:
                    stock_text = stock_elem.get_text(strip=True)
                    if "売切" in stock_text or "×" in stock_text:
                        stock = 0
                        stock_text = "売切"

                # 画像
                image_url = ""
                img_elem = link.select_one("img")
                if not img_elem and link.parent:
                    img_elem = link.parent.select_one("img")
                if img_elem:
                    image_url = img_elem.get("src", "")

                results.append({
                    "name": name,
                    "price": price,
                    "stock": stock,
                    "stock_text": stock_text,
                    "url": detail_url,
                    "image_url": image_url,
                })
            except Exception:
                continue

    except Exception as e:
        log(f"  フルアヘッド検索エラー: {e}")

    return results


def search_yuyutei(client: httpx.Client, keyword: str) -> list[dict]:
    """遊々亭で検索"""
    results = []
    try:
        url = f"https://yuyu-tei.jp/sell/bs/s/search?search_word={keyword}"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select(".card-product")

        for item in items[:20]:
            try:
                is_sold_out = "sold-out" in item.get("class", [])

                link = item.select_one("a[href*='/sell/bs/card/']")
                if not link:
                    continue
                detail_url = link.get("href", "")
                if not detail_url.startswith("http"):
                    detail_url = "https://yuyu-tei.jp" + detail_url

                name_elem = item.select_one("h4.text-primary")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                price = 0
                price_elem = item.select_one("strong.d-block")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                stock = 0 if is_sold_out else 1
                stock_text = "売切" if is_sold_out else "在庫あり"

                img_elem = item.select_one("img.card")
                image_url = img_elem.get("src", "") if img_elem else ""

                results.append({
                    "name": name,
                    "price": price,
                    "stock": stock,
                    "stock_text": stock_text,
                    "url": detail_url,
                    "image_url": image_url,
                })
            except Exception:
                continue

    except Exception as e:
        log(f"  遊々亭検索エラー: {e}")

    return results


def search_hobbystation(client: httpx.Client, keyword: str) -> list[dict]:
    """ホビーステーションで検索"""
    results = []
    try:
        url = f"https://hobbystation-single.jp/product-list?keyword={keyword}&c=10"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select(".product-list-item")

        for item in items[:20]:
            try:
                link = item.select_one("a.product-list-item__link")
                if not link:
                    continue
                detail_url = link.get("href", "")
                if not detail_url.startswith("http"):
                    detail_url = "https://hobbystation-single.jp" + detail_url

                name_elem = item.select_one(".product-list-item__name")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                price = 0
                price_elem = item.select_one(".product-list-item__price")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                stock_elem = item.select_one(".product-list-item__stock")
                stock_text = stock_elem.get_text(strip=True) if stock_elem else ""
                stock = 0 if "売切" in stock_text or "在庫切れ" in stock_text else 1

                img_elem = item.select_one("img")
                image_url = img_elem.get("src", "") if img_elem else ""

                results.append({
                    "name": name,
                    "price": price,
                    "stock": stock,
                    "stock_text": stock_text or ("在庫あり" if stock > 0 else "売切"),
                    "url": detail_url,
                    "image_url": image_url,
                })
            except Exception:
                continue

    except Exception as e:
        log(f"  ホビステ検索エラー: {e}")

    return results


# ショップ別検索関数マッピング
SHOP_SEARCHERS = {
    "カードラッシュ": search_cardrush,
    "フルアヘッド": search_fullahead,
    "遊々亭": search_yuyutei,
    "ホビーステーション": search_hobbystation,
}


def update_keyword_prices(keyword: str, client: httpx.Client) -> dict:
    """1つのキーワードの価格を全ショップから取得・更新"""
    stats = {"keyword": keyword, "total": 0, "new": 0, "shops": {}}

    for shop_name, search_func in SHOP_SEARCHERS.items():
        shop = get_shop_by_name(shop_name)
        if not shop:
            continue

        log(f"  {shop_name} を検索中...")
        results = search_func(client, keyword)
        shop_stats = {"found": len(results), "saved": 0}

        for item in results:
            if item["price"] <= 0:
                continue

            # カードを取得または作成
            card = get_or_create_card(item["name"])

            # 価格を保存（変更がある場合のみ）
            saved = save_price_if_changed(
                card_id=card.id,
                shop_id=shop.id,
                price=item["price"],
                stock=item["stock"],
                stock_text=item["stock_text"],
                url=item["url"],
                image_url=item.get("image_url", ""),
            )

            if saved:
                shop_stats["saved"] += 1
                stats["new"] += 1

            stats["total"] += 1

        stats["shops"][shop_name] = shop_stats
        time.sleep(INTERVAL_BETWEEN_SHOPS)

    return stats


def update_all_featured_keywords():
    """全ての人気キーワードの価格を更新"""
    log("=== 人気キーワード価格更新 開始 ===")

    keywords = get_featured_keywords(active_only=True)
    if not keywords:
        log("人気キーワードが登録されていません")
        return

    log(f"対象キーワード数: {len(keywords)}")

    client = httpx.Client(headers=HEADERS, follow_redirects=True)
    total_stats = {"keywords": 0, "total": 0, "new": 0}

    try:
        for kw in keywords:
            log(f"\n【{kw.keyword}】")
            stats = update_keyword_prices(kw.keyword, client)

            total_stats["keywords"] += 1
            total_stats["total"] += stats["total"]
            total_stats["new"] += stats["new"]

            for shop_name, shop_stat in stats["shops"].items():
                log(f"    {shop_name}: {shop_stat['found']}件取得, {shop_stat['saved']}件更新")

            time.sleep(INTERVAL_BETWEEN_KEYWORDS)

    finally:
        client.close()

    log(f"\n=== 完了 ===")
    log(f"キーワード数: {total_stats['keywords']}")
    log(f"取得商品数: {total_stats['total']}")
    log(f"価格更新数: {total_stats['new']}")

    return total_stats


def update_single_keyword(keyword: str) -> dict:
    """単一キーワードの価格を更新（管理者の即座更新用）"""
    log(f"=== キーワード「{keyword}」の価格更新 ===")

    client = httpx.Client(headers=HEADERS, follow_redirects=True)
    try:
        stats = update_keyword_prices(keyword, client)
        log(f"完了: {stats['total']}件取得, {stats['new']}件更新")
        return stats
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 引数があれば単一キーワード更新
        keyword = " ".join(sys.argv[1:])
        update_single_keyword(keyword)
    else:
        # 引数なしなら全キーワード更新
        update_all_featured_keywords()
