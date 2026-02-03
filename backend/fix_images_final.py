#!/usr/bin/env python3
"""Amazon商品の画像URLをメーカー公式サイトの画像に修正"""
from database import get_connection

# ASINごとの正しい画像URL（メーカー公式サイトから取得）
image_urls = {
    # 既存商品（元々動いていたもの - そのまま維持、もしくは更新）
    "B0FM7DTP22": "https://bandai-a.akamaihd.net/bc/img/model/b/1000215481_1.jpg",  # 契約編:環 第3章
    "B0DXDVB16M": "https://bandai-a.akamaihd.net/bc/img/model/b/1000212633_1.jpg",  # 契約編:環 第1章
    "B0G31XRJR9": "https://bandai-a.akamaihd.net/bc/img/model/b/1000219232_1.jpg",  # ウエハース 蛇皇襲来

    # 新規追加商品（メーカー公式サイトから取得）
    "B003CP0AQO": "https://www.yanoman.co.jp/html/upload/save_image/items/95-080.jpg",  # やのまん インナーガードJr
    "B07JQC7BHM": "https://broccolionline.jp/img/goods/S/4510417593393.jpg",  # ブロッコリー BSP-13
    "B00UWNNBCE": "https://aclass.co.jp/wp-content/uploads/2022/11/370437_front_1000.png",  # Aclass ジャストサイドイン
    "B00TZMJ93S": "https://www.a-answer.co.jp/data/2021/12/ans-tc036_10.jpg",  # アンサー デッキケース
    "B09C8HXKBP": "https://ultimateguard.com/media/9e/96/04/1736778125/UGD011202.webp",  # Ultimate Guard
    "B0DGPZVBRZ": "https://bandai-a.akamaihd.net/bc/img/model/b/1000220358_1.jpg",  # CB32 ウルトラマン
}

print("=== 画像URLをメーカー公式画像に修正 ===")

with get_connection() as conn:
    cursor = conn.cursor()

    for asin, image_url in image_urls.items():
        cursor.execute(
            "UPDATE amazon_products SET image_url = ? WHERE asin = ?",
            (image_url, asin)
        )
        if cursor.rowcount > 0:
            cursor.execute("SELECT name FROM amazon_products WHERE asin = ?", (asin,))
            row = cursor.fetchone()
            print(f"  ✓ {row[0]}")

    conn.commit()

print("\n修正完了!")
