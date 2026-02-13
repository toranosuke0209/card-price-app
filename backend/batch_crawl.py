"""
カード登録バッチ（全商品ページ巡回）
複数ショップの全商品一覧を巡回してカードを登録する

使用方法:
  python batch_crawl.py                        # カードラッシュを巡回（デフォルト）
  python batch_crawl.py --shop tierone         # Tier Oneを巡回
  python batch_crawl.py --shop all             # 全ショップを巡回
  python batch_crawl.py --pages 10             # ページ数指定
  python batch_crawl.py --new-arrivals --shop all  # 全ショップの新商品取得（ページ1から3ページ）
  python batch_crawl.py --new-arrivals --pages 5   # 新商品取得（ページ数指定）
  python batch_crawl.py --status               # 全ショップの進捗確認
  python batch_crawl.py --status --shop tierone # 特定ショップの進捗確認
  python batch_crawl.py --reset --shop tierone  # 進捗リセット
"""

import argparse
import time
import re
import sys
import httpx
from pathlib import Path
from abc import ABC, abstractmethod

if sys.platform != 'win32':
    import fcntl

from datetime import datetime
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

from database import (
    get_connection,
    get_or_create_card_v2,
    get_shop_by_name,
    save_batch_log,
    save_price_if_changed,
)
from scrapers.base import SeleniumScraper

# ロックファイル
LOCK_FILE = Path(__file__).parent / ".batch_crawl.lock"

# 設定
MAX_PAGES_PER_DAY = 50
NEW_ARRIVALS_PAGES = 3  # 新商品取得時のデフォルトページ数
PAGE_INTERVAL = 5

# 対応ショップ
SUPPORTED_SHOPS = {
    "cardrush": "カードラッシュ",
    "tierone": "Tier One",
    "hobbystation": "ホビーステーション",
    "batosuki": "バトスキ",
    "fullahead": "フルアヘッド",
    "dorasuta": "ドラスタ",
}


class CrawlProgress:
    """巡回進捗管理"""

    def __init__(self, shop_id: int):
        self.shop_id = shop_id

    def get_current_page(self) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_page FROM batch_progress
                WHERE shop_id = ? AND kana_type = 'page'
                LIMIT 1
            """, (self.shop_id,))
            row = cursor.fetchone()
            return row["current_page"] if row else 1

    def init_progress(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO batch_progress
                (shop_id, kana_type, kana, current_page, status)
                VALUES (?, 'page', 'all', 1, 'pending')
            """, (self.shop_id,))
            conn.commit()

    def update_progress(self, page: int, total_pages: int = None, status: str = 'in_progress'):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_progress
                SET current_page = ?, total_pages = ?, status = ?,
                    last_fetched_at = CURRENT_TIMESTAMP
                WHERE shop_id = ? AND kana_type = 'page'
            """, (page, total_pages, status, self.shop_id))
            conn.commit()

    def reset_progress(self):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batch_progress
                SET current_page = 1, status = 'pending', last_fetched_at = NULL
                WHERE shop_id = ? AND kana_type = 'page'
            """, (self.shop_id,))
            conn.commit()

    def get_stats(self) -> dict:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_page, total_pages, status, last_fetched_at
                FROM batch_progress
                WHERE shop_id = ? AND kana_type = 'page'
            """, (self.shop_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "current_page": row["current_page"],
                    "total_pages": row["total_pages"],
                    "status": row["status"],
                    "last_fetched_at": row["last_fetched_at"],
                }
            return {"current_page": 1, "total_pages": None, "status": "not_started", "last_fetched_at": None}


class BaseCrawler(ABC):
    """クローラー基底クラス"""
    site_name: str = ""
    base_url: str = ""

    @abstractmethod
    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        """ページを取得して (cards, total_pages) を返す"""
        pass

    @abstractmethod
    def close(self):
        """リソースをクリーンアップ"""
        pass


class CardrushCrawler(SeleniumScraper, BaseCrawler):
    """カードラッシュ巡回クローラー（Selenium使用）"""

    site_name = "カードラッシュ"
    base_url = "https://www.cardrush-bs.jp"

    def build_search_url(self, keyword: str) -> str:
        return f"{self.base_url}/product-list"

    def build_list_url(self, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/product-list"
        return f"{self.base_url}/product-list?page={page}"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = self._get_driver()
        url = self.build_list_url(page)

        print(f"[{self.site_name}] ページ {page} を取得中: {url}")

        driver.get(url)
        time.sleep(3)

        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.list_item_cell"))
            )
        except:
            print(f"[{self.site_name}] ページ読み込みタイムアウト")

        time.sleep(2)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            max_page = 1
            page_links = soup.select("a[href*='page=']")
            for link in page_links:
                href = link.get("href", "")
                match = re.search(r'page=(\d+)', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)

            if max_page == 1:
                text = soup.get_text()
                count_match = re.search(r'([\d,]+)件', text)
                if count_match:
                    total_items = int(count_match.group(1).replace(",", ""))
                    max_page = (total_items + 99) // 100

            return max_page
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        cards = []
        items = soup.select("li.list_item_cell div.item_data")

        for item in items:
            try:
                card = self._parse_card_item(item)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_item(self, item) -> dict | None:
        link = item.select_one("a.item_data_link")
        if not link:
            return None

        url = link.get("href", "")
        if not url:
            return None
        if not url.startswith("http"):
            url = urljoin(self.base_url, url)

        name_elem = item.select_one("span.goods_name")
        if not name_elem:
            return None
        name = name_elem.get_text(strip=True)
        if not name:
            return None

        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # 価格を取得
        price = 0
        price_elem = item.select_one("span.figure")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d,]+)', price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫を取得
        stock = 0
        stock_text = ""
        stock_elem = item.select_one("p.stock")
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True)
            stock_match = re.search(r'(\d+)', stock_text)
            if stock_match:
                stock = int(stock_match.group(1))

        # 画像URLを取得
        image_url = ""
        img_elem = item.select_one("div.global_photo img")
        if img_elem:
            image_url = img_elem.get("src", "")

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def parse_products(self, soup: BeautifulSoup):
        return []

    def close(self):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(super().close())


class TieroneCrawler(BaseCrawler):
    """Tier One巡回クローラー（httpx使用、軽量）"""

    site_name = "Tier One"
    base_url = "https://tier-one.jp"

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            follow_redirects=True
        )

    def build_list_url(self, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/view/category/all_items"
        return f"{self.base_url}/view/category/all_items?page={page}"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        url = self.build_list_url(page)
        print(f"[{self.site_name}] ページ {page} を取得中: {url}")

        try:
            response = self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            print(f"[{self.site_name}] 取得エラー: {e}")
            return [], 1

        soup = BeautifulSoup(response.text, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            max_page = 1

            # page=N のリンクから取得
            page_links = soup.select("a[href*='page=']")
            for link in page_links:
                href = link.get("href", "")
                match = re.search(r'page=(\d+)', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)

            # 総件数から計算（バックアップ）
            if max_page == 1:
                text = soup.get_text()
                # "(全9694件)" のような形式
                count_match = re.search(r'全([\d,]+)件', text)
                if count_match:
                    total_items = int(count_match.group(1).replace(",", ""))
                    # 1ページ48件
                    max_page = (total_items + 47) // 48

            return max_page
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        cards = []

        # 商品リスト
        item_list = soup.select_one("ul.item-list")
        if not item_list:
            # 別のセレクタを試す
            items = soup.select("li.item-list-box, div.item-box")
        else:
            items = item_list.find_all("li", recursive=False)

        for item in items:
            try:
                card = self._parse_card_item(item)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_item(self, item) -> dict | None:
        # 商品名とURL
        name_elem = item.select_one("p.item-name a, a.item-name")
        if not name_elem:
            # 別のセレクタ
            name_elem = item.select_one("a[href*='/view/item/']")

        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        url = name_elem.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # カード番号を抽出
        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # 価格を取得
        price = 0
        price_elem = item.select_one("p.price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'[￥¥]([\d,]+)', price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫を取得
        stock = 0
        stock_text = ""
        stock_elem = item.select_one("p.tac, .stock")
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True)
            stock_match = re.search(r'(\d+)', stock_text)
            if stock_match:
                stock = int(stock_match.group(1))

        # 画像URLを取得
        image_url = ""
        img_elem = item.select_one("div.item-list-image img")
        if img_elem:
            image_url = img_elem.get("src", "")

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def close(self):
        self.client.close()


class HobbyStationCrawler(BaseCrawler):
    """ホビーステーション巡回クローラー（httpx使用）"""

    site_name = "ホビーステーション"
    base_url = "https://www.hobbystation-single.jp"

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            follow_redirects=True
        )

    def build_list_url(self, page: int) -> str:
        return f"{self.base_url}/bs/product/list?page=1&pageno={page}"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        url = self.build_list_url(page)
        print(f"[{self.site_name}] ページ {page} を取得中: {url}")

        try:
            response = self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            print(f"[{self.site_name}] 取得エラー: {e}")
            return [], 1

        soup = BeautifulSoup(response.text, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            # 「最後へ」リンクからページ数を取得
            last_link = soup.select_one("a[href*='pageno=']:-soup-contains('最後')")
            if not last_link:
                # 別の方法: 全ページリンクから最大値を取得
                page_links = soup.select("a[href*='pageno=']")
                max_page = 1
                for link in page_links:
                    href = link.get("href", "")
                    match = re.search(r'pageno=(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))
                return max_page

            href = last_link.get("href", "")
            match = re.search(r'pageno=(\d+)', href)
            if match:
                return int(match.group(1))

            # 総件数から計算（バックアップ）
            text = soup.get_text()
            count_match = re.search(r'([\d,]+)件', text)
            if count_match:
                total = int(count_match.group(1).replace(",", ""))
                return (total + 59) // 60

            return 1
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        cards = []
        items = soup.select("li:has(.packageDetail)")

        for item in items:
            try:
                card = self._parse_card_item(item)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_item(self, item) -> dict | None:
        # 商品名
        name_elem = item.select_one("div.list_product_Name_pc a")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        # URL
        url_elem = item.select_one("figure a")
        url = url_elem.get("href", "") if url_elem else ""
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # カード番号を抽出
        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # 価格
        price = 0
        price_elem = item.select_one(".packageDetail")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d,]+)円', price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫
        stock = 0
        stock_text = ""
        soldout = item.select_one("img[alt*='SOLD'], img[src*='soldout']")
        if soldout:
            stock = 0
            stock_text = "SOLD OUT"
        else:
            # 在庫数を取得
            if price_elem:
                stock_match = re.search(r'在庫数[：:]\s*(\d+)', price_elem.get_text())
                if stock_match:
                    stock = int(stock_match.group(1))
                    stock_text = f"在庫数: {stock}"
                else:
                    stock = 1  # SOLD OUTでなければ在庫ありと仮定

        # 画像URL
        image_url = ""
        img_elem = item.select_one("figure img")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def close(self):
        self.client.close()


class BatosukiCrawler(BaseCrawler):
    """バトスキ巡回クローラー（httpx使用）"""

    site_name = "バトスキ"
    base_url = "https://batosuki.shop"

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            follow_redirects=True
        )

    def build_list_url(self, page: int) -> str:
        return f"{self.base_url}/?mode=srh&page={page}"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        url = self.build_list_url(page)
        print(f"[{self.site_name}] ページ {page} を取得中: {url}")

        try:
            response = self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            print(f"[{self.site_name}] 取得エラー: {e}")
            return [], 1

        soup = BeautifulSoup(response.text, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            page_links = soup.select("a[href*='page=']")
            max_page = 1
            for link in page_links:
                href = link.get("href", "")
                match = re.search(r'page=(\d+)', href)
                if match:
                    max_page = max(max_page, int(match.group(1)))
            return max_page
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        cards = []
        items = soup.select("li.kr-productlist_list")

        for item in items:
            try:
                card = self._parse_card_item(item)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_item(self, item) -> dict | None:
        # 商品名
        name_elem = item.select_one("span.item_name")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        # URL
        url_elem = item.select_one("a[href*='pid=']")
        url = ""
        if url_elem:
            href = url_elem.get("href", "")
            if href.startswith("?"):
                url = f"{self.base_url}/{href}"
            elif not href.startswith("http"):
                url = urljoin(self.base_url, href)
            else:
                url = href

        # カード番号を抽出
        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # 価格（SOLD OUTの場合は表示されない）
        price = 0
        price_elem = item.select_one("span.item_price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d,]+)円', price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫
        stock = 0
        stock_text = ""
        soldout = item.select_one("span.item_soldout, .soldout")
        if soldout:
            stock = 0
            stock_text = "SOLD OUT"
        elif price > 0:
            stock = 1  # 価格があれば在庫ありと仮定
            stock_text = "在庫あり"

        # 画像URL
        image_url = ""
        img_elem = item.select_one("img.item_img")
        if img_elem:
            image_url = img_elem.get("src", "")

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def close(self):
        self.client.close()


class FullaheadCrawler(SeleniumScraper, BaseCrawler):
    """フルアヘッド巡回クローラー（Selenium使用）"""

    site_name = "フルアヘッド"
    base_url = "https://fullahead-tcg.com"

    def build_search_url(self, keyword: str) -> str:
        return f"{self.base_url}/shopbrand/all_items/"

    def build_list_url(self, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/shopbrand/all_items/"
        return f"{self.base_url}/shopbrand/all_items/page{page}/order/"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = self._get_driver()
        url = self.build_list_url(page)

        print(f"[{self.site_name}] ページ {page} を取得中: {url}")

        driver.get(url)
        time.sleep(5)

        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/shopdetail/']"))
            )
        except:
            print(f"[{self.site_name}] ページ読み込みタイムアウト")

        time.sleep(2)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        try:
            # 総商品数から計算
            text = soup.get_text()
            count_match = re.search(r'\[(\d+)\]', text)
            if count_match:
                total_items = int(count_match.group(1))
                return (total_items + 49) // 50

            # ページリンクから取得
            page_links = soup.select("ul.M_pager a[href*='/page']")
            max_page = 1
            for link in page_links:
                href = link.get("href", "")
                match = re.search(r'/page(\d+)/', href)
                if match:
                    max_page = max(max_page, int(match.group(1)))

            return max_page
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        cards = []

        # 商品リンクを探して親構造から情報を取得
        product_links = soup.select("a[href*='/shopdetail/']")

        seen_urls = set()
        for link in product_links:
            try:
                href = link.get("href", "")
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                card = self._parse_card_from_link(link)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_from_link(self, link) -> dict | None:
        # 商品名
        name_elem = link.select_one("span.itemName")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        # URL
        url = link.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # カード番号を抽出
        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # リンク内または直接の親から価格・在庫・画像を取得
        # （3レベル上の親だと共通コンテナになり、最初の要素のデータが全カードに適用されてしまう）
        item = link.parent if link.parent else link

        price = 0
        stock = 0
        stock_text = ""
        image_url = ""

        # 価格 - リンク内 → 直接の親
        price_elem = link.select_one("span.itemPrice strong")
        if not price_elem:
            price_elem = item.select_one("span.itemPrice strong")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d,]+)', price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫 - リンク内 → 直接の親
        stock_elem = link.select_one("span.M_item-stock-smallstock, span.M_category-smallstock")
        if not stock_elem:
            stock_elem = item.select_one("span.M_item-stock-smallstock, span.M_category-smallstock")
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True)
            stock_match = re.search(r'(\d+)', stock_text)
            if stock_match:
                stock = int(stock_match.group(1))
        else:
            # テキストから在庫判定
            item_text = item.get_text()
            if "カート" in item_text:
                stock = 1
                stock_text = "在庫あり"
            elif "売切" in item_text or "SOLD" in item_text.upper():
                stock = 0
                stock_text = "売切れ"
            elif price > 0:
                stock = 1
                stock_text = "在庫あり"

        # 画像 - リンク内 → 直接の親
        img_elem = link.select_one("span.itemImg img, img")
        if not img_elem:
            img_elem = item.select_one("img")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def parse_products(self, soup: BeautifulSoup):
        return []

    def close(self):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(super().close())


class DorasutaCrawler(SeleniumScraper, BaseCrawler):
    """ドラスタ巡回クローラー（Selenium使用）"""

    site_name = "ドラスタ"
    base_url = "https://dorasuta.jp"

    def __init__(self):
        self._current_page = 0

    def build_search_url(self, keyword: str) -> str:
        encoded = quote(keyword, encoding='utf-8')
        return f"{self.base_url}/battlespirits/product-list?kw={encoded}"

    def build_list_url(self, page: int) -> str:
        # 初回は商品一覧ページ、以降はJavaScriptでページ遷移
        return f"{self.base_url}/battlespirits/product-list"

    def fetch_page(self, page: int) -> tuple[list[dict], int]:
        """ページを取得"""
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = self._get_driver()

        if page == 1 or self._current_page == 0:
            # 初回: 商品一覧ページを開く
            url = self.build_list_url(page)
            print(f"[{self.site_name}] ページ {page} を取得中: {url}")
            driver.get(url)
            time.sleep(4)
        else:
            # 2ページ目以降: JavaScriptでページ遷移
            print(f"[{self.site_name}] ページ {page} を取得中...")
            try:
                driver.execute_script(f"$.formSubmit('#form110200', 'search', ['pager', '{page}']);")
                time.sleep(4)
            except Exception as e:
                print(f"[{self.site_name}] ページ遷移エラー: {e}")
                return [], page

        self._current_page = page

        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.element"))
            )
        except:
            pass

        time.sleep(2)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")

        total_pages = self._parse_total_pages(soup)
        cards = self._parse_card_list(soup)

        print(f"[{self.site_name}] ページ {page}/{total_pages}: {len(cards)} 件取得")

        return cards, total_pages

    def _parse_total_pages(self, soup: BeautifulSoup) -> int:
        """ページ数を取得"""
        try:
            pager = soup.select("div.pager a.page_num, div.pager div.page_num")
            max_page = 1
            for elem in pager:
                text = elem.get_text(strip=True)
                if text.isdigit():
                    max_page = max(max_page, int(text))
            return max_page
        except Exception as e:
            print(f"[{self.site_name}] ページ数取得エラー: {e}")
            return 1

    def _parse_card_list(self, soup: BeautifulSoup) -> list[dict]:
        """商品リストをパース"""
        cards = []
        elements = soup.select("div.element:has(div.description)")

        for elem in elements:
            try:
                card = self._parse_card_item(elem)
                if card:
                    cards.append(card)
            except Exception as e:
                continue

        return cards

    def _parse_card_item(self, item) -> dict | None:
        # 商品名とURL
        name_elem = item.select_one("div.description li.change_hight a")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        url = name_elem.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # カード番号を抽出
        card_no = None
        card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
        if card_no_match:
            card_no = card_no_match.group(1)

        # 価格を取得
        price = 0
        price_elems = item.select("div.description ul li")
        for li in price_elems:
            if "円" in li.get_text():
                price_text = li.get_text(strip=True)
                price_match = re.search(r'([\d,]+)円', price_text)
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))
                break

        # 在庫を取得
        stock = 0
        stock_text = ""
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
            elif price > 0:
                stock = 1
                stock_text = "在庫あり"

        # 画像URL
        image_url = ""
        img_elem = item.select_one("div.content img[data-src]")
        if img_elem:
            image_url = img_elem.get("data-src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        return {
            "name": name,
            "card_no": card_no,
            "detail_url": url,
            "price": price,
            "stock": stock,
            "stock_text": stock_text,
            "image_url": image_url,
        }

    def parse_products(self, soup: BeautifulSoup):
        return []

    def close(self):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(super().close())


def get_crawler(shop_key: str) -> BaseCrawler:
    """ショップキーに対応するクローラーを返す"""
    if shop_key == "cardrush":
        return CardrushCrawler()
    elif shop_key == "tierone":
        return TieroneCrawler()
    elif shop_key == "hobbystation":
        return HobbyStationCrawler()
    elif shop_key == "batosuki":
        return BatosukiCrawler()
    elif shop_key == "fullahead":
        return FullaheadCrawler()
    elif shop_key == "dorasuta":
        return DorasutaCrawler()
    else:
        raise ValueError(f"Unknown shop: {shop_key}")


def acquire_lock():
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        return None


def release_lock(lock_fd):
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def run_crawl(shop_key: str, max_pages: int = MAX_PAGES_PER_DAY):
    """指定ショップの巡回を実行"""
    shop_name = SUPPORTED_SHOPS.get(shop_key)
    if not shop_name:
        print(f"エラー: 未対応のショップ '{shop_key}'")
        return

    shop = get_shop_by_name(shop_name)
    if not shop:
        print(f"エラー: ショップ '{shop_name}' が見つかりません")
        return

    progress = CrawlProgress(shop.id)
    progress.init_progress()

    current_page = progress.get_current_page()
    print(f"[{shop_name}] 巡回開始: ページ {current_page} から")

    crawler = None
    total_cards = 0
    new_cards = 0
    updated_cards = 0
    pages_processed = 0
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        crawler = get_crawler(shop_key)

        for i in range(max_pages):
            page = current_page + i

            cards, total_pages = crawler.fetch_page(page)
            pages_processed += 1

            print(f"[{shop_name}] ページ {page}/{total_pages}: {len(cards)} 件取得")

            for card_data in cards:
                total_cards += 1
                card = get_or_create_card_v2(
                    name=card_data["name"],
                    card_no=card_data.get("card_no"),
                    source_shop_id=shop.id,
                    detail_url=card_data.get("detail_url"),
                )
                today_str = datetime.now().strftime("%Y-%m-%d")
                if card.first_seen_at and str(card.first_seen_at).startswith(today_str):
                    new_cards += 1

                # 価格を保存
                if card_data.get("price", 0) > 0:
                    price_saved = save_price_if_changed(
                        card_id=card.id,
                        shop_id=shop.id,
                        price=card_data["price"],
                        stock=card_data.get("stock", 0),
                        stock_text=card_data.get("stock_text", ""),
                        url=card_data.get("detail_url", ""),
                        image_url=card_data.get("image_url", ""),
                    )
                    # 既存カードで価格が保存された場合は更新としてカウント
                    is_new = card.first_seen_at and str(card.first_seen_at).startswith(today_str)
                    if price_saved and not is_new:
                        updated_cards += 1

            if page >= total_pages:
                progress.update_progress(1, total_pages, 'pending')
                print(f"[{shop_name}] 全ページ巡回完了。次回は最初から開始します。")
                break
            else:
                progress.update_progress(page + 1, total_pages, 'in_progress')

            if i < max_pages - 1:
                time.sleep(PAGE_INTERVAL)

        print(f"\n[{shop_name}] 巡回完了")
        print(f"  処理ページ数: {pages_processed}")
        print(f"  取得カード数: {total_cards}")
        print(f"  新規登録数: {new_cards}")
        print(f"  価格更新数: {updated_cards}")

        # 成功ログを保存
        save_batch_log(
            batch_type='crawl',
            shop_name=shop_name,
            status='success',
            pages_processed=pages_processed,
            cards_total=total_cards,
            cards_new=new_cards,
            cards_updated=updated_cards,
            message=f"{pages_processed}ページ巡回完了",
            started_at=started_at
        )

    except Exception as e:
        print(f"[{shop_name}] エラー: {e}")
        import traceback
        traceback.print_exc()

        # エラーログを保存
        save_batch_log(
            batch_type='crawl',
            shop_name=shop_name,
            status='error',
            pages_processed=pages_processed,
            cards_total=total_cards,
            cards_new=new_cards,
            cards_updated=updated_cards,
            message=str(e),
            started_at=started_at
        )
    finally:
        if crawler:
            crawler.close()


def run_new_arrivals(shop_key: str, pages: int = NEW_ARRIVALS_PAGES):
    """新商品取得: ページ1から数ページだけ巡回（通常の進捗に影響しない）"""
    shop_name = SUPPORTED_SHOPS.get(shop_key)
    if not shop_name:
        print(f"エラー: 未対応のショップ '{shop_key}'")
        return

    shop = get_shop_by_name(shop_name)
    if not shop:
        print(f"エラー: ショップ '{shop_name}' が見つかりません")
        return

    print(f"[{shop_name}] 新商品取得開始: ページ 1〜{pages}")

    crawler = None
    total_cards = 0
    new_cards = 0
    updated_cards = 0
    pages_processed = 0
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        crawler = get_crawler(shop_key)

        for page in range(1, pages + 1):
            cards, total_pages = crawler.fetch_page(page)
            pages_processed += 1

            print(f"[{shop_name}] ページ {page}/{total_pages}: {len(cards)} 件取得")

            for card_data in cards:
                total_cards += 1
                card = get_or_create_card_v2(
                    name=card_data["name"],
                    card_no=card_data.get("card_no"),
                    source_shop_id=shop.id,
                    detail_url=card_data.get("detail_url"),
                )
                today_str = datetime.now().strftime("%Y-%m-%d")
                if card.first_seen_at and str(card.first_seen_at).startswith(today_str):
                    new_cards += 1

                if card_data.get("price", 0) > 0:
                    price_saved = save_price_if_changed(
                        card_id=card.id,
                        shop_id=shop.id,
                        price=card_data["price"],
                        stock=card_data.get("stock", 0),
                        stock_text=card_data.get("stock_text", ""),
                        url=card_data.get("detail_url", ""),
                        image_url=card_data.get("image_url", ""),
                    )
                    is_new = card.first_seen_at and str(card.first_seen_at).startswith(today_str)
                    if price_saved and not is_new:
                        updated_cards += 1

            if page >= total_pages:
                print(f"[{shop_name}] 全ページ取得済み（{total_pages}ページ）")
                break

            if page < pages:
                time.sleep(PAGE_INTERVAL)

        print(f"\n[{shop_name}] 新商品取得完了")
        print(f"  処理ページ数: {pages_processed}")
        print(f"  取得カード数: {total_cards}")
        print(f"  新規登録数: {new_cards}")
        print(f"  価格更新数: {updated_cards}")

        save_batch_log(
            batch_type='new_arrivals',
            shop_name=shop_name,
            status='success',
            pages_processed=pages_processed,
            cards_total=total_cards,
            cards_new=new_cards,
            cards_updated=updated_cards,
            message=f"新商品取得: {pages_processed}ページ巡回完了",
            started_at=started_at
        )

    except Exception as e:
        print(f"[{shop_name}] エラー: {e}")
        import traceback
        traceback.print_exc()

        save_batch_log(
            batch_type='new_arrivals',
            shop_name=shop_name,
            status='error',
            pages_processed=pages_processed,
            cards_total=total_cards,
            cards_new=new_cards,
            cards_updated=updated_cards,
            message=str(e),
            started_at=started_at
        )
    finally:
        if crawler:
            crawler.close()


def show_status(shop_key: str = None):
    """進捗状況を表示"""
    shops_to_check = [shop_key] if shop_key else list(SUPPORTED_SHOPS.keys())

    for key in shops_to_check:
        shop_name = SUPPORTED_SHOPS.get(key)
        if not shop_name:
            continue

        shop = get_shop_by_name(shop_name)
        if not shop:
            print(f"\n=== {shop_name} ===")
            print("  ショップ未登録")
            continue

        progress = CrawlProgress(shop.id)
        stats = progress.get_stats()

        print(f"\n=== {shop_name} 巡回進捗 ===")
        print(f"  現在ページ: {stats['current_page']}")
        print(f"  総ページ数: {stats['total_pages'] or '未取得'}")
        print(f"  ステータス: {stats['status']}")
        print(f"  最終更新: {stats['last_fetched_at'] or '未実行'}")

        if stats['total_pages']:
            pct = (stats['current_page'] / stats['total_pages']) * 100
            print(f"  進捗: {pct:.1f}%")


def reset_progress(shop_key: str):
    """進捗をリセット"""
    shop_name = SUPPORTED_SHOPS.get(shop_key)
    if not shop_name:
        print(f"エラー: 未対応のショップ '{shop_key}'")
        return

    shop = get_shop_by_name(shop_name)
    if not shop:
        print(f"エラー: ショップ '{shop_name}' が見つかりません")
        return

    progress = CrawlProgress(shop.id)
    progress.reset_progress()
    print(f"[{shop_name}] 進捗をリセットしました")


def main():
    parser = argparse.ArgumentParser(description="カード登録バッチ（全商品ページ巡回）")
    parser.add_argument("--shop", type=str, default="cardrush",
                        choices=list(SUPPORTED_SHOPS.keys()) + ["all"],
                        help="対象ショップ（デフォルト: cardrush）")
    parser.add_argument("--pages", type=int, default=MAX_PAGES_PER_DAY,
                        help=f"処理するページ数（デフォルト: {MAX_PAGES_PER_DAY}）")
    parser.add_argument("--new-arrivals", action="store_true",
                        help="新商品取得モード（ページ1から数ページだけ巡回、進捗に影響なし）")
    parser.add_argument("--status", action="store_true", help="進捗確認")
    parser.add_argument("--reset", action="store_true", help="進捗リセット")

    args = parser.parse_args()

    if args.status:
        shop_key = None if args.shop == "all" else args.shop
        show_status(shop_key)
        return

    if args.reset:
        if args.shop == "all":
            for key in SUPPORTED_SHOPS.keys():
                reset_progress(key)
        else:
            reset_progress(args.shop)
        return

    print(f"[{datetime.now()}] バッチ開始")

    if sys.platform != 'win32':
        lock_fd = acquire_lock()
        if not lock_fd:
            print("別のバッチプロセスが実行中です。終了します。")
            return
    else:
        lock_fd = None

    try:
        if args.new_arrivals:
            # 新商品取得モード: ページ1から数ページだけ巡回
            pages = args.pages if args.pages != MAX_PAGES_PER_DAY else NEW_ARRIVALS_PAGES
            print(f"=== 新商品取得モード（{pages}ページ） ===")
            if args.shop == "all":
                for shop_key in SUPPORTED_SHOPS.keys():
                    run_new_arrivals(shop_key, pages=pages)
                    print()
            else:
                run_new_arrivals(args.shop, pages=pages)
        else:
            if args.shop == "all":
                for shop_key in SUPPORTED_SHOPS.keys():
                    run_crawl(shop_key, max_pages=args.pages)
                    print()
            else:
                run_crawl(args.shop, max_pages=args.pages)
    finally:
        if lock_fd:
            release_lock(lock_fd)

    print(f"[{datetime.now()}] バッチ終了")


if __name__ == "__main__":
    main()
