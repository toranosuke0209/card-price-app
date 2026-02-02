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
SELENIUM_TIMEOUT = 60
INTERVAL_BETWEEN_SHOPS = 2  # ショップ間の待機秒数
INTERVAL_BETWEEN_KEYWORDS = 1  # キーワード間の待機秒数

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Seleniumドライバー（遅延初期化）
_selenium_driver = None


def log(message: str):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_selenium_driver():
    """Seleniumドライバーを取得（シングルトン）"""
    global _selenium_driver
    if _selenium_driver is None:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        options.page_load_strategy = "eager"

        _selenium_driver = webdriver.Chrome(options=options)
        _selenium_driver.set_page_load_timeout(SELENIUM_TIMEOUT)

    return _selenium_driver


def close_selenium_driver():
    """Seleniumドライバーを閉じる"""
    global _selenium_driver
    if _selenium_driver:
        try:
            _selenium_driver.quit()
        except:
            pass
        _selenium_driver = None


# =============================================================================
# httpx ベースの検索（軽量サイト用）
# =============================================================================

def search_fullahead(client: httpx.Client, keyword: str) -> list[dict]:
    """フルアヘッドで検索（httpx）"""
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

                name_elem = link.select_one("span.itemName")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                price = 0
                price_elem = link.select_one("span.itemPrice strong")
                if not price_elem:
                    price_elem = link.parent.select_one("span.itemPrice strong") if link.parent else None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

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


def search_batosuki(client: httpx.Client, keyword: str) -> list[dict]:
    """バトスキで検索（httpx）"""
    results = []
    try:
        url = f"https://batosuki.shop/?mode=srh&keyword={keyword}"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        # EUC-JP エンコーディングでデコード
        try:
            html = response.content.decode("euc-jp", errors="replace")
        except:
            html = response.text

        soup = BeautifulSoup(html, "lxml")

        # 商品アイテムを取得
        items = soup.select("li[class*='item_list'], li[class*='footer_list']")

        for item in items[:20]:
            try:
                # 商品名
                name_elem = item.select_one("span.item_name")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                # URL
                url_elem = item.select_one("a[href*='pid=']")
                detail_url = ""
                if url_elem:
                    href = url_elem.get("href", "")
                    if href.startswith("?"):
                        detail_url = f"https://batosuki.shop/{href}"
                    elif not href.startswith("http"):
                        detail_url = f"https://batosuki.shop{href}"
                    else:
                        detail_url = href

                # 価格
                price = 0
                price_elem = item.select_one("span.item_price")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"([\d,]+)円", price_text)
                    if match:
                        price = int(match.group(1).replace(",", ""))

                # 在庫（SOLD OUTの場合は価格が表示されない）
                stock = 1
                stock_text = "在庫あり"
                if price == 0 or "SOLD" in str(item).upper() or "売切" in str(item):
                    stock = 0
                    stock_text = "売切"

                # 画像
                img_elem = item.select_one("img")
                image_url = img_elem.get("src", "") if img_elem else ""

                if price > 0:  # 価格がある商品のみ追加
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
        log(f"  バトスキ検索エラー: {e}")

    return results


def search_tierone(client: httpx.Client, keyword: str) -> list[dict]:
    """Tier Oneで検索（httpx）"""
    results = []
    try:
        url = f"https://tier-one.jp/view/search?search_keyword={keyword}"
        response = client.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            return results

        soup = BeautifulSoup(response.text, "lxml")

        # 商品リストを取得（ul.item-list > li）
        item_list = soup.select_one("ul.item-list")
        if item_list:
            items = item_list.find_all("li", recursive=False)
        else:
            items = []

        for item in items[:20]:
            try:
                # 商品リンク
                link = item.select_one("a[href*='/view/item/']")
                if not link:
                    continue
                detail_url = link.get("href", "")
                if not detail_url.startswith("http"):
                    detail_url = "https://tier-one.jp" + detail_url

                # 商品名（p.item-name a）
                name_elem = item.select_one("p.item-name a")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                # 価格（p.price）
                price = 0
                price_elem = item.select_one("p.price")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                # 在庫（在庫数:Nから取得）
                stock = 1
                stock_text = "在庫あり"
                stock_elem = item.select_one(".M_lumpinput p.tac")
                if stock_elem:
                    stock_match = re.search(r"在庫数:(\d+)", stock_elem.get_text())
                    if stock_match:
                        stock_num = int(stock_match.group(1))
                        if stock_num == 0:
                            stock = 0
                            stock_text = "売切"
                        else:
                            stock_text = f"在庫:{stock_num}"

                # 画像
                img_elem = item.select_one(".item-list-image img")
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
        log(f"  Tier One検索エラー: {e}")

    return results


# =============================================================================
# Selenium ベースの検索（JavaScript必須サイト用）
# =============================================================================

def search_cardrush_selenium(keyword: str) -> list[dict]:
    """カードラッシュで検索（Selenium）"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    results = []
    try:
        driver = get_selenium_driver()
        url = f"https://www.cardrush-bs.jp/product-list?keyword={keyword}"
        driver.get(url)
        time.sleep(3)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.list_item_cell"))
            )
        except:
            pass

        soup = BeautifulSoup(driver.page_source, "lxml")
        items = soup.select("li.list_item_cell")

        for item in items[:20]:
            try:
                link = item.select_one("a[href*='/product/']")
                if not link:
                    continue
                detail_url = link.get("href", "")
                if not detail_url.startswith("http"):
                    detail_url = "https://www.cardrush-bs.jp" + detail_url

                name_elem = item.select_one(".item_name, .name a")
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)

                price = 0
                price_elem = item.select_one(".item_price, .price")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"[\d,]+", price_text)
                    if match:
                        price = int(match.group().replace(",", ""))

                # 在庫を取得（p.stock から「在庫数 N枚」を抽出）
                stock = 0
                stock_text = "売切"
                stock_elem = item.select_one("p.stock")
                if stock_elem:
                    stock_text = stock_elem.get_text(strip=True)
                    stock_match = re.search(r"(\d+)", stock_text)
                    if stock_match:
                        stock = int(stock_match.group(1))
                        if stock > 0:
                            stock_text = f"在庫:{stock}"
                        else:
                            stock_text = "売切"
                # ×や売切表示があれば在庫なし
                if "×" in str(item) or "売切" in str(item) or "品切" in str(item):
                    stock = 0
                    stock_text = "売切"

                img_elem = item.select_one("img")
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
        log(f"  カードラッシュ検索エラー: {e}")

    return results


def search_hobbystation_selenium(keyword: str) -> list[dict]:
    """ホビーステーションで検索（Selenium）"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    results = []
    try:
        driver = get_selenium_driver()
        # 正しいURL: /bs/product/list?search_word=キーワード
        url = f"https://www.hobbystation-single.jp/bs/product/list?search_word={keyword}"
        driver.get(url)
        time.sleep(3)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.searchRsultList li"))
            )
        except:
            pass

        soup = BeautifulSoup(driver.page_source, "lxml")

        # 商品リストを取得（ul.searchRsultList li）
        items = soup.select("ul.searchRsultList li")

        for item in items[:20]:
            try:
                # 商品名とURL（div.list_product_Name_pc a）
                name_elem = item.select_one("div.list_product_Name_pc a")
                if not name_elem:
                    name_elem = item.select_one("div.list_product_Name_sp a")
                if not name_elem:
                    continue

                name = name_elem.get_text(strip=True)
                detail_url = name_elem.get("href", "")

                if not name or len(name) < 3:
                    continue

                # 価格（div.packageDetail から取得）
                price = 0
                price_elem = item.select_one("div.packageDetail")
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    match = re.search(r"([\d,]+)円", price_text)
                    if match:
                        price = int(match.group(1).replace(",", ""))

                # 在庫（SOLD OUTアイコンの有無で判定）
                stock = 1
                stock_text = "在庫あり"
                soldout_img = item.select_one("img[alt*='SOLD']")
                if soldout_img or "SOLD" in str(item).upper():
                    stock = 0
                    stock_text = "売切"

                # 画像
                img_elem = item.select_one("figure img")
                image_url = ""
                if img_elem:
                    image_url = img_elem.get("src", "")
                    if image_url and not image_url.startswith("http"):
                        image_url = "https://www.hobbystation-single.jp" + image_url

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
        log(f"  ホビステ検索エラー: {e}")

    return results


def search_dorasuta_selenium(keyword: str) -> list[dict]:
    """ドラスタで検索（Selenium）"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from urllib.parse import quote

    results = []
    try:
        driver = get_selenium_driver()
        encoded_kw = quote(keyword, encoding='utf-8')
        url = f"https://dorasuta.jp/battlespirits/product-list?kw={encoded_kw}"
        driver.get(url)
        time.sleep(3)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.element"))
            )
        except:
            pass

        soup = BeautifulSoup(driver.page_source, "lxml")

        # 商品リストを取得
        items = soup.select("div.element:has(div.description)")

        for item in items[:20]:
            try:
                # 商品名とURL
                name_elem = item.select_one("div.description li.change_hight a")
                if not name_elem:
                    continue

                name = name_elem.get_text(strip=True)
                detail_url = name_elem.get("href", "")

                if not name or len(name) < 3:
                    continue

                if detail_url and not detail_url.startswith("http"):
                    detail_url = "https://dorasuta.jp" + detail_url

                # 価格
                price = 0
                price_elems = item.select("div.description ul li")
                for li in price_elems:
                    if "円" in li.get_text():
                        match = re.search(r"([\d,]+)円", li.get_text())
                        if match:
                            price = int(match.group(1).replace(",", ""))
                        break

                # 在庫
                stock = 1
                stock_text = "在庫あり"
                soldout = item.select_one("a.condition.soldout, .soldout")
                if soldout:
                    stock = 0
                    stock_text = "SOLDOUT"
                else:
                    stock_elem = item.select_one("div.selectbox[data-value]")
                    if stock_elem:
                        stock_val = stock_elem.get("data-value", "0")
                        if stock_val.isdigit():
                            stock = int(stock_val)
                            stock_text = f"在庫: {stock}"

                # 画像
                img_elem = item.select_one("div.content img[data-src]")
                image_url = ""
                if img_elem:
                    image_url = img_elem.get("data-src", "")
                    if image_url and not image_url.startswith("http"):
                        image_url = "https://dorasuta.jp" + image_url

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
        log(f"  ドラスタ検索エラー: {e}")

    return results


# =============================================================================
# メイン処理
# =============================================================================

# ショップ別検索関数マッピング
HTTPX_SHOPS = {
    "フルアヘッド": search_fullahead,
    "Tier One": search_tierone,
    "バトスキ": search_batosuki,
}

SELENIUM_SHOPS = {
    "カードラッシュ": search_cardrush_selenium,
    "ホビーステーション": search_hobbystation_selenium,
    "ドラスタ": search_dorasuta_selenium,
}


def update_keyword_prices(keyword: str, client: httpx.Client) -> dict:
    """1つのキーワードの価格を全ショップから取得・更新"""
    stats = {"keyword": keyword, "total": 0, "new": 0, "shops": {}}

    # httpxベースのショップ
    for shop_name, search_func in HTTPX_SHOPS.items():
        shop = get_shop_by_name(shop_name)
        if not shop:
            continue

        log(f"  {shop_name} を検索中...")
        results = search_func(client, keyword)
        shop_stats = {"found": len(results), "saved": 0}

        for item in results:
            if item["price"] <= 0:
                continue

            card = get_or_create_card(item["name"])
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
        log(f"    -> {shop_stats['found']}件取得, {shop_stats['saved']}件更新")
        time.sleep(INTERVAL_BETWEEN_SHOPS)

    # Seleniumベースのショップ
    for shop_name, search_func in SELENIUM_SHOPS.items():
        shop = get_shop_by_name(shop_name)
        if not shop:
            continue

        log(f"  {shop_name} を検索中（Selenium）...")
        results = search_func(keyword)
        shop_stats = {"found": len(results), "saved": 0}

        for item in results:
            if item["price"] <= 0:
                continue

            card = get_or_create_card(item["name"])
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
        log(f"    -> {shop_stats['found']}件取得, {shop_stats['saved']}件更新")
        time.sleep(INTERVAL_BETWEEN_SHOPS)

    return stats


def update_all_featured_keywords():
    """全ての人気キーワードの価格を更新"""
    log("=== 人気キーワード価格更新 開始 ===")

    keywords = get_featured_keywords(active_only=True)
    if not keywords:
        log("人気キーワードが登録されていません")
        return {"keywords": 0, "total": 0, "new": 0}

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

            time.sleep(INTERVAL_BETWEEN_KEYWORDS)

    finally:
        client.close()
        close_selenium_driver()

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
        close_selenium_driver()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        keyword = " ".join(sys.argv[1:])
        update_single_keyword(keyword)
    else:
        update_all_featured_keywords()
