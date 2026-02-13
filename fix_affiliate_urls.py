#!/usr/bin/env python3
"""Amazon商品のaffiliate_urlを正しいASINで再生成"""
from database import get_connection

AMAZON_TAG = "bsprice-22"

print("=== affiliate_urlを修正 ===")

with get_connection() as conn:
    cursor = conn.cursor()

    # 全商品のASINを取得して、affiliate_urlを再生成
    cursor.execute("SELECT id, asin, name FROM amazon_products")
    products = cursor.fetchall()

    for product in products:
        product_id, asin, name = product
        correct_url = f"https://www.amazon.co.jp/dp/{asin}?tag={AMAZON_TAG}"

        cursor.execute(
            "UPDATE amazon_products SET affiliate_url = ? WHERE id = ?",
            (correct_url, product_id)
        )
        print(f"  ✓ {name}")
        print(f"    -> {correct_url}")

    conn.commit()

print("\n修正完了!")
