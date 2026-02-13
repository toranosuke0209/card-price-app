"""
sitemap.xml 自動生成スクリプト
カード詳細ページを含むsitemapを生成する
"""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "card_price.db"
OUTPUT_DIR = Path(__file__).parent.parent / "frontend"
BASE_URL = "https://bsprice.net"

def get_published_article_slugs():
    """公開済み記事のslugリストを取得"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT slug FROM articles WHERE is_published = 1 ORDER BY published_at DESC")
        return [row[0] for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def generate_sitemap():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 価格データがあるカードのみ取得（実際に販売されているカード）
    cur.execute('''
        SELECT DISTINCT c.id
        FROM cards c
        JOIN prices p ON c.id = p.card_id
        ORDER BY c.id
    ''')
    card_ids = [row[0] for row in cur.fetchall()]
    conn.close()

    # 公開済みブログ記事
    article_slugs = get_published_article_slugs()
    print(f"価格データがあるカード数: {len(card_ids)}")
    print(f"公開済みブログ記事数: {len(article_slugs)}")

    # sitemapは50,000件が上限なので、分割が必要な場合は対応
    if len(card_ids) > 50000:
        print("カード数が50,000件を超えるため、sitemap indexを生成します")
        generate_sitemap_index(card_ids, article_slugs)
    else:
        generate_single_sitemap(card_ids, article_slugs)

def generate_single_sitemap(card_ids, article_slugs=None):
    today = datetime.now().strftime("%Y-%m-%d")
    article_slugs = article_slugs or []

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # 静的ページ
    static_pages = [
        ("/", "daily", "1.0"),
        ("/ranking", "daily", "0.8"),
        ("/shops", "weekly", "0.7"),
        ("/blog", "weekly", "0.7"),
        ("/about", "monthly", "0.5"),
        ("/privacy", "monthly", "0.3"),
    ]

    for path, freq, priority in static_pages:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{BASE_URL}{path}</loc>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append(f"  </url>")

    # ブログ記事ページ
    for slug in article_slugs:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{BASE_URL}/blog/{slug}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>weekly</changefreq>")
        lines.append(f"    <priority>0.7</priority>")
        lines.append(f"  </url>")

    # カード詳細ページ
    for card_id in card_ids:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{BASE_URL}/card?id={card_id}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>daily</changefreq>")
        lines.append(f"    <priority>0.6</priority>")
        lines.append(f"  </url>")

    lines.append('</urlset>')

    output_path = OUTPUT_DIR / "sitemap.xml"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    total = len(static_pages) + len(article_slugs) + len(card_ids)
    print(f"sitemap.xml を生成しました: {output_path}")
    print(f"総URL数: {total}")

def generate_sitemap_index(card_ids, article_slugs=None):
    today = datetime.now().strftime("%Y-%m-%d")
    chunk_size = 45000  # 余裕を持って45000件ずつ
    article_slugs = article_slugs or []

    sitemap_files = []

    # カードページを分割
    for i in range(0, len(card_ids), chunk_size):
        chunk = card_ids[i:i+chunk_size]
        sitemap_num = (i // chunk_size) + 1
        filename = f"sitemap-cards-{sitemap_num}.xml"

        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

        for card_id in chunk:
            lines.append(f"  <url>")
            lines.append(f"    <loc>{BASE_URL}/card?id={card_id}</loc>")
            lines.append(f"    <lastmod>{today}</lastmod>")
            lines.append(f"    <changefreq>daily</changefreq>")
            lines.append(f"    <priority>0.6</priority>")
            lines.append(f"  </url>")

        lines.append('</urlset>')

        output_path = OUTPUT_DIR / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        sitemap_files.append(filename)
        print(f"{filename} を生成しました ({len(chunk)}件)")

    # 静的ページ + ブログ記事用sitemap
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    static_pages = [
        ("/", "daily", "1.0"),
        ("/ranking", "daily", "0.8"),
        ("/shops", "weekly", "0.7"),
        ("/blog", "weekly", "0.7"),
        ("/about", "monthly", "0.5"),
        ("/privacy", "monthly", "0.3"),
    ]

    for path, freq, priority in static_pages:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{BASE_URL}{path}</loc>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append(f"  </url>")

    # ブログ記事ページ
    for slug in article_slugs:
        lines.append(f"  <url>")
        lines.append(f"    <loc>{BASE_URL}/blog/{slug}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>weekly</changefreq>")
        lines.append(f"    <priority>0.7</priority>")
        lines.append(f"  </url>")

    lines.append('</urlset>')

    output_path = OUTPUT_DIR / "sitemap-static.xml"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    sitemap_files.insert(0, "sitemap-static.xml")
    print(f"sitemap-static.xml を生成しました")
    
    # sitemap index
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for filename in sitemap_files:
        lines.append(f"  <sitemap>")
        lines.append(f"    <loc>{BASE_URL}/static/{filename}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"  </sitemap>")
    
    lines.append('</sitemapindex>')
    
    output_path = OUTPUT_DIR / "sitemap.xml"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"sitemap.xml (index) を生成しました")
    print(f"総カード数: {len(card_ids)}")

if __name__ == "__main__":
    generate_sitemap()
