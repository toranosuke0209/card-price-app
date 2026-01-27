import re
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import BaseScraper, Product


class FullaheadScraper(BaseScraper):
    """フルアヘッド用スクレイパー"""

    site_name = "フルアヘッド"
    base_url = "https://fullahead-tcg.com"

    def build_search_url(self, keyword: str) -> str:
        encoded = quote(keyword, safe="")
        return f"{self.base_url}/shop/shopbrand.html?search={encoded}"

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []

        # 商品リストを取得
        # 構造: div.indexItemBox > div（各商品）
        item_box = soup.select_one("div.indexItemBox")
        if not item_box:
            return products

        # 各商品div
        items = item_box.find_all("div", recursive=False)

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                print(f"[フルアヘッド] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, item) -> Product | None:
        # 商品リンクを取得
        link = item.select_one("a[href*='shopdetail']")
        if not link:
            return None

        # 商品名: <span class="itemName">内のテキスト
        name_elem = item.select_one("span.itemName")
        name = name_elem.get_text(strip=True) if name_elem else link.get_text(strip=True)
        if not name:
            return None

        # URL
        href = link.get("href", "")
        if not href:
            return None
        url = urljoin(self.base_url, href)

        # 画像URL取得
        image_url = ""
        img_elem = item.select_one("img")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        # 価格を取得: <span class="itemPrice"><strong>880円</strong></span>
        price = 0
        price_text = ""

        price_elem = item.select_one("span.itemPrice")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"([\d,]+)円", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫チェック（カートボタンの有無で判定）
        stock = 0
        stock_display = "不明"

        item_text = item.get_text()
        if "カートに入れる" in item_text or "カート" in item_text:
            stock = 1
            stock_display = "在庫あり"
        elif "売切" in item_text or "SOLD" in item_text.upper():
            stock = 0
            stock_display = "売切れ"
        elif price > 0:
            stock = 1
            stock_display = "在庫あり"

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
