import asyncio
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from scrapers import CardrushScraper, TieroneScraper, BatosukiScraper, FullaheadScraper, YuyuteiScraper, HobbystationScraper

app = FastAPI(title="カード価格比較API")

# スクレイパーのリスト（拡張時はここに追加）
SCRAPERS = [
    CardrushScraper,
    TieroneScraper,
    BatosukiScraper,
    FullaheadScraper,
    YuyuteiScraper,
    HobbystationScraper,
]

# フロントエンドの静的ファイルを配信
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def root():
    """フロントエンドのindex.htmlを返す"""
    return FileResponse(frontend_path / "index.html")


@app.get("/api/search")
async def search(keyword: str = Query(..., min_length=1, description="検索キーワード")):
    """
    複数サイトから商品を検索

    - keyword: 検索キーワード（必須）
    """
    scrapers = [cls() for cls in SCRAPERS]

    try:
        # 全スクレイパーで並行検索
        tasks = [scraper.search(keyword) for scraper in scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果を整形
        site_results = []
        total_count = 0

        for scraper, result in zip(scrapers, results):
            if isinstance(result, Exception):
                items = []
            else:
                items = [p.to_dict() for p in result]
                total_count += len(items)

            site_results.append({
                "site": scraper.site_name,
                "items": items
            })

        return {
            "keyword": keyword,
            "results": site_results,
            "total_count": total_count
        }
    finally:
        # クライアントをクローズ
        for scraper in scrapers:
            await scraper.close()


@app.get("/api/sites")
async def get_sites():
    """対応サイト一覧を返す"""
    return {
        "sites": [
            {"name": cls.site_name, "url": cls.base_url}
            for cls in SCRAPERS
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
