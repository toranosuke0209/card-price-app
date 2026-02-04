#!/usr/bin/env python3
"""Amazon商品のASINを正しいものに修正するスクリプト"""
from database import get_connection

# 正しいASINのマッピング（商品名 -> 正しいASIN）
corrections = {
    "やのまん カードプロテクター インナーガードJr. 100枚": "B003CP0AQO",
    "ブロッコリー スリーブプロテクターS エンボス&クリア ミニ 80枚": "B07JQC7BHM",
    "Aclass デュエリストミニ ジャストサイドイン 100枚": "B00UWNNBCE",
    "アンサー トレカデッキケース ブラック": "B00TZMJ93S",
    "Ultimate Guard サイドワインダー 80+ ブラック": "B09C8HXKBP",
    "バトルスピリッツ CB32 ウルトラマン ブースターBOX": "B0DGPZVBRZ",
}

print("=== Amazon商品のASINを修正 ===")

with get_connection() as conn:
    cursor = conn.cursor()

    for name, correct_asin in corrections.items():
        cursor.execute(
            "UPDATE amazon_products SET asin = ? WHERE name = ?",
            (correct_asin, name)
        )
        if cursor.rowcount > 0:
            print(f"  ✓ {name} -> {correct_asin}")
        else:
            print(f"  - {name} (対象なし)")

    conn.commit()

print("\n修正完了!")

# 確認
print("\n=== 登録済みAmazon商品一覧 ===")
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT asin, name FROM amazon_products ORDER BY id")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
