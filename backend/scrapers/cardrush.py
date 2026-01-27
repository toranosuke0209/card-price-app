import re
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import SeleniumScraper, Product


class CardrushScraper(SeleniumScraper):
    """カードラッシュ用スクレイパー（Selenium使用）"""

    site_name = "カードラッシュ"
    base_url = "https://www.cardrush-bs.jp"

    def build_search_url(self, keyword: str) -> str:
        encoded = quote(keyword, safe="")
        return f"{self.base_url}/product-list?keyword={encoded}"

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []

        # 商品リストアイテムを取得
        # 構造: <li class="list_item_cell"> > <div class="item_data">
        items = soup.select("li.list_item_cell div.item_data")

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                print(f"[カードラッシュ] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, item) -> Product | None:
        # 商品リンクを取得
        link = item.select_one("a.item_data_link")
        if not link:
            return None

        url = link.get("href", "")
        if not url:
            return None
        if not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # 商品名を取得: <span class="goods_name">
        name_elem = item.select_one("span.goods_name")
        if not name_elem:
            return None
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

        # 価格を取得: <span class="figure">8,980円</span>
        price = 0
        price_text = ""
        price_elem = item.select_one("span.figure")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"([\d,]+)円", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫を取得: <p class="stock">在庫数 3枚</p>
        stock = 0
        stock_display = "不明"
        stock_elem = item.select_one("p.stock")
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True)
            stock_match = re.search(r"(\d+)", stock_text)
            if stock_match:
                stock = int(stock_match.group(1))
                stock_display = "在庫あり" if stock > 0 else "売切れ"
            elif "売切" in stock_text:
                stock = 0
                stock_display = "売切れ"

        return Product(
            site=self.site_name,
            name=name,
            price=price,
            price_text=price_text + "(税込)" if price_text else f"{price:,}円(税込)",
            stock=stock,
            stock_text=stock_display,
            url=url,
            image_url=image_url
        )
