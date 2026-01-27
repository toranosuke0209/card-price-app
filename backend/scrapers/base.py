from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
import httpx
from bs4 import BeautifulSoup
import platform
import os

# ChromeDriverのパスを自動検出
def get_chromedriver_path():
    """環境に応じてChromeDriverのパスを返す"""
    system = platform.system()

    if system == "Windows":
        # Windowsローカル環境
        return r"C:\Users\toraa\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"
    elif system == "Linux":
        # Linux/EC2環境
        # システムパスにある場合
        if os.path.exists("/usr/local/bin/chromedriver"):
            return "/usr/local/bin/chromedriver"
        elif os.path.exists("/usr/bin/chromedriver"):
            return "/usr/bin/chromedriver"
        else:
            # システムパスにない場合はNoneを返し、Seleniumに自動検出させる
            return None
    else:
        # macOSやその他のOS
        return None

CHROMEDRIVER_PATH = get_chromedriver_path()


@dataclass
class Product:
    """商品情報を表すデータクラス"""
    site: str
    name: str
    price: int
    price_text: str
    stock: int
    stock_text: str
    url: str
    image_url: str = ""  # 商品画像URL

    def to_dict(self) -> dict:
        return asdict(self)


class BaseScraper(ABC):
    """スクレイパーの基底クラス（httpx使用）"""

    site_name: str = ""
    base_url: str = ""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            follow_redirects=True
        )

    async def close(self):
        await self.client.aclose()

    @abstractmethod
    def build_search_url(self, keyword: str) -> str:
        """検索URLを構築（サブクラスで実装）"""
        pass

    async def search(self, keyword: str) -> list[Product]:
        """キーワードで商品を検索"""
        try:
            url = self.build_search_url(keyword)
            response = await self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            products = self.parse_products(soup)

            # キーワードでフィルタリング
            return self._filter_by_keyword(products, keyword)
        except Exception as e:
            print(f"[{self.site_name}] 検索エラー: {e}")
            return []

    def _filter_by_keyword(self, products: list[Product], keyword: str) -> list[Product]:
        """検索キーワードに基づいて商品をフィルタリング"""
        if not keyword:
            return products

        keyword_lower = keyword.lower().strip()
        filtered = []
        for product in products:
            name_lower = product.name.lower()
            if keyword_lower in name_lower:
                filtered.append(product)
        return filtered

    @abstractmethod
    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        """検索結果ページから商品リストを抽出（サブクラスで実装）"""
        pass


class SeleniumScraper(ABC):
    """Seleniumを使用するスクレイパーの基底クラス"""

    site_name: str = ""
    base_url: str = ""
    _driver = None

    def _get_driver(self):
        """WebDriverを取得（遅延初期化）"""
        if self._driver is None:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            # EC2/Linux環境用の設定
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")
            # ページ読み込み戦略を"eager"に設定（DOMContentLoadedで読み込み完了とみなす）
            # これにより追跡スクリプト等の完全読み込みを待たずに処理を続行できる
            options.page_load_strategy = "eager"

            try:
                # ChromeDriverのパスが指定されている場合はServiceを使用
                if CHROMEDRIVER_PATH:
                    service = Service(executable_path=CHROMEDRIVER_PATH)
                    self._driver = webdriver.Chrome(service=service, options=options)
                else:
                    # パスが指定されていない場合は自動検出
                    self._driver = webdriver.Chrome(options=options)

                # ページ読み込みタイムアウトを設定（60秒に延長）
                self._driver.set_page_load_timeout(60)
                self._driver.implicitly_wait(15)
            except Exception as e:
                print(f"[{self.site_name}] Chrome起動エラー: {e}")
                raise

        return self._driver

    async def close(self):
        """リソースをクリーンアップ"""
        if self._driver:
            self._driver.quit()
            self._driver = None

    @abstractmethod
    def build_search_url(self, keyword: str) -> str:
        """検索URLを構築（サブクラスで実装）"""
        pass

    async def search(self, keyword: str) -> list[Product]:
        """キーワードで商品を検索"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._search_sync, keyword)
        except Exception as e:
            print(f"[{self.site_name}] 検索エラー: {e}")
            return []

    def _search_sync(self, keyword: str) -> list[Product]:
        """同期的な検索処理"""
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = self._get_driver()
        url = self.build_search_url(keyword)

        driver.get(url)
        time.sleep(5)

        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/'], li.list_item_cell, .item_data"))
            )
        except:
            pass

        time.sleep(3)

        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        products = self.parse_products(soup)

        # キーワードでフィルタリング
        return self._filter_by_keyword(products, keyword)

    def _filter_by_keyword(self, products: list[Product], keyword: str) -> list[Product]:
        """検索キーワードに基づいて商品をフィルタリング"""
        if not keyword:
            return products

        # キーワードを正規化（小文字、空白除去）
        keyword_lower = keyword.lower().strip()

        filtered = []
        for product in products:
            # 商品名を正規化
            name_lower = product.name.lower()

            # キーワードが商品名に含まれているかチェック
            if keyword_lower in name_lower:
                filtered.append(product)

        return filtered

    @abstractmethod
    def parse_products(self, soup: BeautifulSoup) -> list[Product]:
        """検索結果ページから商品リストを抽出（サブクラスで実装）"""
        pass
