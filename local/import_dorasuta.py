"""
ドラスタデータインポート（EC2で実行）
ローカルでクロールしたJSONデータをDBに取り込む

使用方法:
  python import_dorasuta.py --input /home/ubuntu/project/data/dorasuta_20260202.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# backend ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from database import (
    get_or_create_card_v2,
    get_shop_by_name,
    save_price_if_changed,
    save_batch_log,
)

SHOP_NAME = "ドラスタ"


def main():
    parser = argparse.ArgumentParser(description="ドラスタデータインポート")
    parser.add_argument("--input", type=str, required=True, help="入力JSONファイル")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"エラー: ファイルが見つかりません: {input_path}")
        return

    print(f"ドラスタデータインポート開始")
    print(f"入力ファイル: {input_path}")

    # JSONを読み込み
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cards = data.get("cards", [])
    print(f"カード数: {len(cards)}")

    # ショップを取得
    shop = get_shop_by_name(SHOP_NAME)
    if not shop:
        print(f"エラー: ショップ '{SHOP_NAME}' が見つかりません")
        print("先にshopsテーブルにドラスタを追加してください")
        print("  python -c \"from database import init_shops; init_shops()\"")
        return

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_cards = 0
    new_cards = 0
    prices_saved = 0
    by_condition = {}

    for card_data in cards:
        total_cards += 1

        # カードを登録
        card = get_or_create_card_v2(
            name=card_data["name"],
            card_no=card_data.get("card_no"),
            source_shop_id=shop.id,
            detail_url=card_data.get("detail_url"),
        )

        today_str = datetime.now().strftime("%Y-%m-%d")
        if card.first_seen_at and str(card.first_seen_at).startswith(today_str):
            new_cards += 1

        # 価格を保存
        if card_data.get("price", 0) > 0:
            # 状態（SALE/傷あり特価）をstock_textに追加
            condition = card_data.get("condition", "通常")
            stock_text = card_data.get("stock_text", "")
            if condition != "通常":
                stock_text = f"【{condition}】{stock_text}"

            save_price_if_changed(
                card_id=card.id,
                shop_id=shop.id,
                price=card_data["price"],
                stock=card_data.get("stock", 0),
                stock_text=stock_text,
                url=card_data.get("detail_url", ""),
                image_url=card_data.get("image_url", ""),
            )
            prices_saved += 1
            by_condition[condition] = by_condition.get(condition, 0) + 1

    print()
    print(f"インポート完了")
    print(f"  処理カード数: {total_cards}")
    print(f"  新規登録数: {new_cards}")
    print(f"  価格保存数: {prices_saved}")
    if len(by_condition) > 1 or (len(by_condition) == 1 and "通常" not in by_condition):
        print(f"  状態別内訳:")
        for cond, count in sorted(by_condition.items()):
            print(f"    {cond}: {count}件")

    # バッチログを保存
    save_batch_log(
        batch_type="import",
        shop_name=SHOP_NAME,
        status="success",
        pages_processed=1,
        cards_total=total_cards,
        cards_new=new_cards,
        message=f"ローカルからインポート完了",
        started_at=started_at
    )


if __name__ == "__main__":
    main()
