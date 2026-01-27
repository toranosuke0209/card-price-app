import re
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import BaseScraper, Product


class YuyuteiScraper(BaseScraper):
    """遊々亭用スクレイパー"""

    site_name = "遊々亭"
    base_url = "https://yuyu-tei.jp"

    def build_search_url(self, keyword: str) -> str:
        encoded = quote(keyword, safe="")
        return f"{self.base_url}/sell/bs/s/search?search_word={encoded}"

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []

        # 商品リストを取得
        # 構造: div.card-product
        cards = soup.select("div.card-product")

        for card in cards:
            try:
                product = self._parse_item(card)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                print(f"[遊々亭] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, card) -> Product | None:
        # 商品リンクを取得
        link = card.select_one("a[href*='/sell/bs/card/']")
        if not link:
            return None

        href = link.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else urljoin(self.base_url, href)

        # カード番号: <span class="d-block border...">BS65-XV01</span>
        card_num = ""
        num_elem = card.select_one("span.border")
        if num_elem:
            card_num = num_elem.get_text(strip=True)

        # 商品名: <h4 class="text-primary fw-bold">
        name = ""
        name_elem = card.select_one("h4.text-primary")
        if name_elem:
            name = name_elem.get_text(strip=True)

        # カード番号と名前を結合
        if card_num and name:
            full_name = f"{card_num} {name}"
        elif name:
            full_name = name
        else:
            return None

        # 画像URL: <img class="card img-fluid" src="...">
        image_url = ""
        img_elem = card.select_one("img.card")
        if img_elem:
            image_url = img_elem.get("src", "")
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(self.base_url, image_url)

        # 価格: <strong class="d-block text-end">4,980 円</strong>
        price = 0
        price_text = ""
        price_elem = card.select_one("strong.text-end")
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"([\d,]+)\s*円", price_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

        # 在庫チェック: sold-outクラスがあれば売切れ
        stock = 0
        stock_display = "不明"

        if "sold-out" in card.get("class", []):
            stock = 0
            stock_display = "売切れ"
        else:
            # 在庫テキストを確認: <label class="cart_sell_zaiko">在庫 : ○</label>
            stock_elem = card.select_one("label.cart_sell_zaiko")
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True)
                if "×" in stock_text:
                    stock = 0
                    stock_display = "売切れ"
                elif "○" in stock_text or "◯" in stock_text:
                    stock = 1
                    stock_display = "在庫あり"
                else:
                    # 数字を探す
                    stock_match = re.search(r"(\d+)", stock_text)
                    if stock_match:
                        stock = int(stock_match.group(1))
                        stock_display = f"在庫{stock}点"
                    elif price > 0:
                        stock = 1
                        stock_display = "在庫あり"

        return Product(
            site=self.site_name,
            name=full_name,
            price=price,
            price_text=price_text or f"{price:,}円",
            stock=stock,
            stock_text=stock_display,
            url=url,
            image_url=image_url
        )
