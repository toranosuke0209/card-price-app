import re
import time
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base import SeleniumScraper, Product


class BatosukiScraper(SeleniumScraper):
    """バトスキ用スクレイパー（Selenium使用、フォーム送信）"""

    site_name = "バトスキ"
    base_url = "https://batosuki.shop"

    def build_search_url(self, keyword: str) -> str:
        # トップページを返す（検索はJSで実行）
        return self.base_url

    def _search_sync(self, keyword: str) -> list[Product]:
        """フォーム送信による検索"""
        driver = self._get_driver()

        # トップページにアクセス
        driver.get(self.base_url)
        time.sleep(5)

        # JavaScriptで検索フォームに値を設定して送信
        script = f"""
        var forms = document.querySelectorAll('form');
        for (var i = 0; i < forms.length; i++) {{
            var form = forms[i];
            var keywordInput = form.querySelector('input[name="keyword"]');
            if (keywordInput) {{
                keywordInput.value = '{keyword}';
                form.submit();
                break;
            }}
        }}
        """
        driver.execute_script(script)
        time.sleep(10)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        products = self.parse_products(soup)

        # キーワードでフィルタリング
        return self._filter_by_keyword(products, keyword)

    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        products = []
        seen_pids = set()  # 重複排除用

        # 商品リストを取得
        # 構造: <li class="kr-productlist_list">内に商品情報
        items = soup.select("li.kr-productlist_list")

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.price > 0:
                    # URLから重複チェック
                    if product.url not in seen_pids:
                        seen_pids.add(product.url)
                        products.append(product)
            except Exception as e:
                print(f"[バトスキ] パースエラー: {e}")
                continue

        return products

    def _parse_item(self, item) -> Product | None:
        # 商品リンクを取得（テキストがあるリンクを優先）
        links = item.select("a[href*='pid=']")
        if not links:
            return None

        # テキストがあるリンクを探す
        link = None
        name = ""
        for a in links:
            text = a.get_text(strip=True)
            if text:
                link = a
                name = text
                break

        if not link or not name:
            return None

        # URLを取得
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

        # 価格を取得: 「480円(内税)」または「180円(税抜)」形式
        price = 0
        price_text = ""

        # li要素のテキスト全体から価格を探す
        item_text = item.get_text()
        # 内税、税抜、税込みに対応
        price_match = re.search(r"([\d,]+)円\s*[(（](内税|税抜|税込)[)）]?", item_text)
        if price_match:
            price_text = price_match.group(0)
            price = int(price_match.group(1).replace(",", ""))
        else:
            # フォールバック: 単純な「円」パターン
            price_match = re.search(r"([\d,]+)円", item_text)
            if price_match:
                price_text = price_match.group(0)
                price = int(price_match.group(1).replace(",", ""))

        # 在庫チェック
        stock = 0
        stock_display = "不明"

        if "SOLD OUT" in item_text or "soldout" in item_text.lower():
            stock = 0
            stock_display = "売切れ"
        elif price > 0:
            # 価格があれば在庫ありとみなす
            stock = 1
            stock_display = "在庫あり"

        return Product(
            site=self.site_name,
            name=name,
            price=price,
            price_text=price_text or f"{price:,}円(税抜)",
            stock=stock,
            stock_text=stock_display,
            url=url,
            image_url=image_url
        )
