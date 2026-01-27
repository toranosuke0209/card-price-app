import re
import time
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import SeleniumScraper, Product


class HobbystationScraper(SeleniumScraper):
    """ホビーステーション用スクレイパー（Selenium使用）"""

    site_name = "ホビーステーション"
    base_url = "https://www.hobbystation-single.jp"

    def build_search_url(self, keyword: str) -> str:
        # トップページを返す（検索はJSで実行）
        return f"{self.base_url}/bs/product/list"

    def _search_sync(self, keyword: str) -> list[Product]:
        """Enterキーによる検索"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        driver = self._get_driver()

        # 商品一覧ページにアクセス
        driver.get(self.build_search_url(keyword))
        time.sleep(3)

        # 検索入力欄に直接入力してEnterキーで検索
        search_input = driver.find_element(By.CSS_SELECTOR, 'input[name="search_word"][type="search"]')
        search_input.clear()
        search_input.send_keys(keyword)
        search_input.send_keys(Keys.RETURN)

        # 検索結果の読み込みを待つ
        time.sleep(8)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        products = self.parse_products(soup)

        # ホビーステーションはサイト側で検索済みなのでフィルタリング不要
        return products

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []

        # 商品リストを取得
        # 構造: ul.searchRsultList > li
        result_list = soup.select_one("ul.searchRsultList")
        if not result_list:
            return products

        items = result_list.select("li")

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                print(f"[ホビーステーション] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, item) -> Product | None:
        # 商品リンクを取得
        link = item.select_one("a[href*='/bs/product/detail/']")
        if not link:
            return None

        href = link.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else urljoin(self.base_url, href)

        # 商品名: div.list_product_Name_pc a または div.list_product_Name_sp a
        name = ""
        name_elem = item.select_one("div.list_product_Name_pc a")
        if name_elem:
            name = name_elem.get_text(strip=True)
        if not name:
            name_elem = item.select_one("div.list_product_Name_sp a")
            if name_elem:
                name = name_elem.get_text(strip=True)
        if not name:
            return None

        # 画像URL取得
        image_url = ""
        img_elem = item.select_one("img")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        # 価格: div.packageDetail 内のテキスト
        price = 0
        price_text = ""
        price_elem = item.select_one("div.packageDetail")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"([\d,]+)円", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫チェック: SOLD OUT画像の有無
        stock = 0
        stock_display = "不明"

        soldout_img = item.select_one("img[alt='SOLD OUT'], img[src*='soldout']")
        if soldout_img:
            stock = 0
            stock_display = "売切れ"
        elif price > 0:
            # カートボタンが有効かどうか
            cart_btn = item.select_one("button.shopCart:not([disabled])")
            if cart_btn:
                stock = 1
                stock_display = "在庫あり"
            else:
                stock = 0
                stock_display = "売切れ"

        return Product(
            site=self.site_name,
            name=name,
            price=price,
            price_text=price_text.split("円")[0] + "円" if "円" in price_text else f"{price:,}円",
            stock=stock,
            stock_text=stock_display,
            url=url,
            image_url=image_url
        )
