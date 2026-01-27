"""
カード価格比較API

変更履歴:
- 2026/01/27: 検索キーワード自動追加機能
- 2026/01/27: リダイレクトAPI追加（クリック計測）
- 2026/01/27: DB参照方式に変更（スクレイピング廃止）
- 旧実装は main_old.py に保存
"""
from pathlib import Path
from urllib.parse import unquote
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

# キーワードファイルのパス
KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"


def add_keyword_if_new(keyword: str) -> bool:
    """
    キーワードがkeywords.txtになければ追加する

    Returns:
        True: 追加した, False: 既に存在
    """
    keyword = keyword.strip()
    if not keyword or len(keyword) < 2:
        return False

    # 既存キーワードを読み込み
    existing = set()
    if KEYWORDS_FILE.exists():
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line.lower())

    # 既に存在する場合は追加しない
    if keyword.lower() in existing:
        return False

    # 新しいキーワードを追加
    with open(KEYWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{keyword}")

    return True

from database import (
    init_database,
    init_shops,
    get_all_shops,
    get_shop_by_name,
    get_latest_prices_by_keyword,
    get_recently_updated,
    get_price_increased_cards,
    get_price_decreased_cards,
    get_hot_cards,
    get_database_stats,
    search_cards,
    record_search,
    record_click,
)

app = FastAPI(title="カード価格比較API")

# フロントエンドの静的ファイルを配信
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.on_event("startup")
async def startup():
    """アプリ起動時にDB初期化"""
    init_database()
    init_shops()


@app.get("/")
async def root():
    """フロントエンドのindex.htmlを返す"""
    return FileResponse(frontend_path / "index.html")


@app.get("/api/search")
async def search(keyword: str = Query(..., min_length=1, description="検索キーワード")):
    """
    キーワードで商品を検索（DB参照）

    - keyword: 検索キーワード（必須）

    レスポンス形式は旧API互換を維持
    """
    # DBから最新価格を取得
    prices = get_latest_prices_by_keyword(keyword, limit=200)

    # 検索ログを記録
    record_search(keyword, len(prices))

    # 結果が少なければキーワードを自動追加（次回バッチで取得される）
    if len(prices) < 5:
        add_keyword_if_new(keyword)

    # サイト別にグループ化（旧API互換形式）
    site_items = {}
    for price in prices:
        site_name = price.shop_name
        if site_name not in site_items:
            site_items[site_name] = []
        site_items[site_name].append(price.to_dict())

    # 全ショップのリストを取得（データがないショップも含める）
    all_shops = get_all_shops()
    site_results = []

    for shop in all_shops:
        items = site_items.get(shop.name, [])
        site_results.append({
            "site": shop.name,
            "items": items
        })

    return {
        "keyword": keyword,
        "results": site_results,
        "total_count": len(prices)
    }


@app.get("/api/sites")
async def get_sites():
    """対応サイト一覧を返す（DB参照）"""
    shops = get_all_shops()
    return {
        "sites": [
            {"name": shop.name, "url": shop.url}
            for shop in shops
        ]
    }


@app.get("/api/home")
async def get_home_data():
    """
    ホーム画面用データを取得

    - recently_updated: 最近価格更新されたカード
    - price_up: 値上がりしたカード
    - price_down: 値下がりしたカード
    - hot_cards: よくクリックされているカード
    - stats: DB統計情報
    """
    # 最近更新されたカード
    recently_updated = get_recently_updated(limit=10)
    recently_updated_list = [p.to_dict() for p in recently_updated]

    # 値上がりカード
    price_up = get_price_increased_cards(limit=10)

    # 値下がりカード
    price_down = get_price_decreased_cards(limit=10)

    # ホットカード（クリック数）
    hot_cards = get_hot_cards(days=7, limit=10)

    # DB統計
    stats = get_database_stats()

    return {
        "recently_updated": recently_updated_list,
        "price_up": price_up,
        "price_down": price_down,
        "hot_cards": hot_cards,
        "stats": {
            "total_cards": stats["cards"],
            "total_prices": stats["prices"],
            "last_updated": stats["newest_price"],
        }
    }


@app.get("/api/redirect")
async def redirect_to_shop(
    url: str = Query(..., description="リダイレクト先URL"),
    site: str = Query(None, description="ショップ名"),
    card: str = Query(None, description="カード名"),
):
    """
    外部ショップへリダイレクト（クリック計測用）

    - url: リダイレクト先の商品ページURL（必須）
    - site: ショップ名（オプション、計測用）
    - card: カード名（オプション、計測用）

    将来的にアフィリエイトURLへの変換もここで行う
    """
    # クリック記録
    card_id = None
    shop_id = None

    if site:
        shop = get_shop_by_name(site)
        if shop:
            shop_id = shop.id

    if card:
        cards = search_cards(card)
        if cards:
            # 完全一致を優先、なければ最初の結果
            for c in cards:
                if c.name == card:
                    card_id = c.id
                    break
            if card_id is None and cards:
                card_id = cards[0].id

    # クリックをDBに記録
    if shop_id or card_id:
        record_click(card_id=card_id, shop_id=shop_id)

    # URLをデコードしてリダイレクト
    decoded_url = unquote(url)

    # 将来のアフィリエイト対応用フック
    # affiliate_url = convert_to_affiliate(decoded_url, site)

    return RedirectResponse(url=decoded_url, status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
