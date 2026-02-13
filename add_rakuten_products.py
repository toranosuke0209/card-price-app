#!/usr/bin/env python3
"""楽天商品を追加するスクリプト"""
from database import add_rakuten_product

AFFILIATE_ID = "507d6316.932e0e43.507d6317.e71fdd26"

products = [
    {
        "item_code": "bs75_booster",
        "name": "バトルスピリッツ 契約編:環 第4章 英雄傑集 ブースターパック",
        "price": 5040,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/amiami/cabinet/images/2024/n25454.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{AFFILIATE_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2590%25E3%2583%2588%25E3%2583%25AB%25E3%2582%25B9%25E3%2583%2594%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2584%2BBS75%2F"
    },
    {
        "item_code": "bs_sleeve",
        "name": "バトルスピリッツ カードスリーブ",
        "price": 880,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/surugaya-a-too/cabinet/5765/607743177m.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{AFFILIATE_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2590%25E3%2583%2588%25E3%2583%25AB%25E3%2582%25B9%25E3%2583%2594%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2584%2B%25E3%2582%25B9%25E3%2583%25AA%25E3%2583%25BC%25E3%2583%2596%2F"
    },
    {
        "item_code": "bs_deckcase",
        "name": "トレカ デッキケース",
        "price": 1500,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/torekagu/cabinet/09444648/imgrc0083516253.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{AFFILIATE_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2588%25E3%2583%25AC%25E3%2582%25AB%2B%25E3%2583%2587%25E3%2583%2583%25E3%2582%25AD%25E3%2582%25B1%25E3%2583%25BC%25E3%2582%25B9%2F"
    },
    {
        "item_code": "bs_playmat",
        "name": "バトルスピリッツ プレイマット",
        "price": 2500,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/surugaya-a-too/cabinet/5389/607525627m.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{AFFILIATE_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2590%25E3%2583%2588%25E3%2583%25AB%25E3%2582%25B9%25E3%2583%2594%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2584%2B%25E3%2583%2597%25E3%2583%25AC%25E3%2582%25A4%25E3%2583%259E%25E3%2583%2583%25E3%2583%2588%2F"
    },
]

for p in products:
    try:
        product = add_rakuten_product(
            item_code=p["item_code"],
            name=p["name"],
            price=p["price"],
            image_url=p["image_url"],
            affiliate_url=p["affiliate_url"]
        )
        print(f"Added: {product.name}")
    except Exception as e:
        print(f"Error adding {p['name']}: {e}")

print("Done!")
