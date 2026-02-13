#!/usr/bin/env python3
"""Amazon商品のaffiliate_urlを確認"""
from database import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT asin, name, affiliate_url FROM amazon_products")
    for row in cursor.fetchall():
        print(f"ASIN: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"URL: {row[2]}")
        print("-" * 50)
