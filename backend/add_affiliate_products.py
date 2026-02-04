#!/usr/bin/env python3
"""購入率の高いアフィリエイト商品を追加するスクリプト"""
from database import add_amazon_product, add_rakuten_product

AMAZON_TAG = "bsprice-22"
RAKUTEN_ID = "507d6316.932e0e43.507d6317.e71fdd26"

# ==================== Amazon商品 ====================
amazon_products = [
    # スリーブ（最も購入率が高い）
    {
        "asin": "B004OKOJBE",
        "name": "やのまん カードプロテクター インナーガードJr. 100枚",
        "price": 320,
        "image_url": "https://m.media-amazon.com/images/I/41kB0PYLWQL._AC_.jpg"
    },
    {
        "asin": "B07NVRG1MR",
        "name": "ブロッコリー スリーブプロテクターS エンボス&クリア ミニ 80枚",
        "price": 480,
        "image_url": "https://m.media-amazon.com/images/I/51VuH0hZURL._AC_.jpg"
    },
    {
        "asin": "B09TVRXQNZ",
        "name": "Aclass デュエリストミニ ジャストサイドイン 100枚",
        "price": 398,
        "image_url": "https://m.media-amazon.com/images/I/51Ao8kZ8y5L._AC_.jpg"
    },
    # デッキケース
    {
        "asin": "B07D74Q88P",
        "name": "アンサー トレカデッキケース ブラック",
        "price": 264,
        "image_url": "https://m.media-amazon.com/images/I/41FvGCx+gAL._AC_.jpg"
    },
    {
        "asin": "B07N2LJM3K",
        "name": "Ultimate Guard サイドワインダー 80+ ブラック",
        "price": 1980,
        "image_url": "https://m.media-amazon.com/images/I/61RvD8Y7eeL._AC_.jpg"
    },
    # 新弾・ブースター
    {
        "asin": "B0DQJ7XCSY",
        "name": "バトルスピリッツ CB32 ウルトラマン ブースターBOX",
        "price": 4812,
        "image_url": "https://m.media-amazon.com/images/I/81Kk8YfM0qL._AC_.jpg"
    },
]

# ==================== 楽天商品 ====================
rakuten_products = [
    # スリーブ
    {
        "item_code": "yanoman_inner_jr",
        "name": "やのまん カードプロテクター インナーガードJr. 100枚",
        "price": 330,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/yellowsubmarine/cabinet/09/4979817390030.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2582%25A4%25E3%2583%25B3%25E3%2583%258A%25E3%2583%25BC%25E3%2582%25AC%25E3%2583%25BC%25E3%2583%2589Jr%2F"
    },
    {
        "item_code": "broccoli_sleeve_s",
        "name": "ブロッコリー スリーブプロテクターS ミニサイズ用",
        "price": 495,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/auc-mediaworld/cabinet/8/4510417413738.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2596%25E3%2583%25AD%25E3%2583%2583%25E3%2582%25B3%25E3%2583%25AA%25E3%2583%25BC%2B%25E3%2582%25B9%25E3%2583%25AA%25E3%2583%25BC%25E3%2583%2596%25E3%2583%2597%25E3%2583%25AD%25E3%2583%2586%25E3%2582%25AF%25E3%2582%25BF%25E3%2583%25BCS%2F"
    },
    # デッキケース
    {
        "item_code": "answer_deckcase",
        "name": "アンサー トレカデッキケース",
        "price": 280,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/6818/4573358446818.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2582%25A2%25E3%2583%25B3%25E3%2582%25B5%25E3%2583%25BC%2B%25E3%2583%2588%25E3%2583%25AC%25E3%2582%25AB%25E3%2583%2587%25E3%2583%2583%25E3%2582%25AD%25E3%2582%25B1%25E3%2583%25BC%25E3%2582%25B9%2F"
    },
    # 新弾
    {
        "item_code": "bs75_booster_box",
        "name": "バトルスピリッツ BS75 英雄傑集 ブースターBOX 2月発売",
        "price": 4950,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/amiami/cabinet/images/2024/n25454.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2590%25E3%2583%2588%25E3%2583%25AB%25E3%2582%25B9%25E3%2583%2594%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2584%2BBS75%2F"
    },
    {
        "item_code": "cb32_ultraman_box",
        "name": "バトルスピリッツ CB32 ウルトラマン ブースターBOX",
        "price": 4812,
        "image_url": "https://thumbnail.image.rakuten.co.jp/@0_mall/toysrus/cabinet/goods/738/679796700all.jpg",
        "affiliate_url": f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2590%25E3%2583%2588%25E3%2583%25AB%25E3%2582%25B9%25E3%2583%2594%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2584%2BCB32%2F"
    },
]

print("=== Amazon商品を追加 ===")
for p in amazon_products:
    try:
        product = add_amazon_product(
            asin=p["asin"],
            name=p["name"],
            price=p["price"],
            image_url=p["image_url"],
            affiliate_tag=AMAZON_TAG
        )
        print(f"  ✓ {product.name}")
    except Exception as e:
        print(f"  ✗ {p['name']}: {e}")

print("\n=== 楽天商品を追加 ===")
for p in rakuten_products:
    try:
        product = add_rakuten_product(
            item_code=p["item_code"],
            name=p["name"],
            price=p["price"],
            image_url=p["image_url"],
            affiliate_url=p["affiliate_url"]
        )
        print(f"  ✓ {product.name}")
    except Exception as e:
        print(f"  ✗ {p['name']}: {e}")

print("\n完了!")
