#!/usr/bin/env python3
"""Amazon商品の画像URLを修正（Amazon PA-APIウィジェット形式）"""
from database import get_connection

AMAZON_TAG = "bsprice-22"

print("=== 画像URLをAmazon PA-API形式に修正 ===")

with get_connection() as conn:
    cursor = conn.cursor()

    # 全商品のASINを取得
    cursor.execute("SELECT id, asin, name FROM amazon_products")
    products = cursor.fetchall()

    for product in products:
        product_id, asin, name = product
        # Amazon PA-APIウィジェット画像URL（ASINから動的に生成される）
        image_url = f"https://ws-fe.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_SL250_&ID=AsinImage&MarketPlace=JP&ServiceVersion=20070822&WS=1&tag={AMAZON_TAG}"

        cursor.execute(
            "UPDATE amazon_products SET image_url = ? WHERE id = ?",
            (image_url, product_id)
        )
        print(f"  ✓ {name}")

    conn.commit()

print("\n修正完了!")
