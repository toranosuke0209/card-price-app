#!/usr/bin/env python3
"""Amazon商品の画像URLを修正（Amazon.jp画像形式）"""
from database import get_connection

print("=== 画像URLをAmazon.jp形式に修正 ===")

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT id, asin, name FROM amazon_products")
    products = cursor.fetchall()

    for product in products:
        product_id, asin, name = product
        # Amazon.jp 画像URL形式
        image_url = f"https://images-na.ssl-images-amazon.com/images/P/{asin}.09.LZZZZZZZ.jpg"

        cursor.execute(
            "UPDATE amazon_products SET image_url = ? WHERE id = ?",
            (image_url, product_id)
        )
        print(f"  {name}: {asin}")

    conn.commit()

print("\n完了!")
