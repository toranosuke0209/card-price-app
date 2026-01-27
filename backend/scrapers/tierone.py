import re
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import BaseScraper, Product


class TieroneScraper(BaseScraper):
    """Tier One用スクレイパー"""

    site_name = "Tier One"
    base_url = "https://tier-one.jp"

    def build_search_url(self, keyword: str) -> str:
        encoded = quote(keyword, safe="")
        return f"{self.base_url}/view/search?search_keyword={encoded}"

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []

        # 商品リスト内のアイテムを取得
        # 構造: <ul class="item-list"> の中の <li>
        item_list = soup.select_one("ul.item-list")
        if not item_list:
            return products

        items = item_list.find_all("li", recursive=False)

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                print(f"[Tier One] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, item) -> Product | None:
        # 商品名を取得: <p class="item-name"><a href="...">商品名</a></p>
        name_elem = item.select_one("p.item-name a")
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name:
            return None

        # URLを取得
        url = name_elem.get("href", "")
        if url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        # 画像URL取得
        image_url = ""
        img_elem = item.select_one("img")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        # 価格を取得: <p class="price">￥1,280<span>（税込）</span></p>
        price = 0
        price_text = ""

        price_elem = item.select_one("p.price")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            # ￥1,280 の形式から数値を抽出
            price_match = re.search(r"[￥¥]([\d,]+)", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫を取得
        stock = 0
        stock_display = "不明"

        # 売り切れチェック: class="item-soldout" や SOLD OUT
        soldout_elem = item.select_one(".item-soldout, .item-list-sold")
        if soldout_elem or "SOLD OUT" in item.get_text():
            stock = 0
            stock_display = "売切れ"
        else:
            # 在庫数を取得: <p class="tac">在庫数:3</p>
            stock_text = item.get_text()
            stock_match = re.search(r"在庫数[：:]?\s*(\d+)", stock_text)
            if stock_match:
                stock = int(stock_match.group(1))
                stock_display = "在庫あり" if stock > 0 else "売切れ"
            else:
                # カートボタンがあれば在庫あり
                cart_btn = item.select_one(".add-list-cart, .cart-order-btn")
                if cart_btn:
                    stock = 1
                    stock_display = "在庫あり"

        return Product(
            site=self.site_name,
            name=name,
            price=price,
            price_text=price_text or f"￥{price:,}(税込)",
            stock=stock,
            stock_text=stock_display,
            url=url,
            image_url=image_url
        )
