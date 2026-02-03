#!/usr/bin/env python3
"""各ショップのデータ状況を確認"""
import sqlite3

conn = sqlite3.connect('card_price.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 各ショップのカード数と番号抽出状況
cur.execute("""
SELECT s.name as shop,
       COUNT(DISTINCT p.card_id) as cards,
       COUNT(DISTINCT CASE WHEN c.extracted_card_no IS NOT NULL THEN c.id END) as with_no
FROM prices p
JOIN cards c ON p.card_id = c.id
JOIN shops s ON p.shop_id = s.id
WHERE p.id IN (SELECT MAX(id) FROM prices GROUP BY card_id, shop_id)
GROUP BY s.id
ORDER BY cards DESC
""")

print("=== ショップ別カード数 ===")
for row in cur.fetchall():
    pct = (row['with_no'] / row['cards'] * 100) if row['cards'] > 0 else 0
    print(f"{row['shop']}: {row['cards']}枚 (番号抽出: {row['with_no']}枚 = {pct:.1f}%)")

# サンプルカード名を表示
print("\n=== 各ショップのカード名サンプル ===")
cur.execute("""
SELECT s.name as shop, c.name as card_name, c.extracted_card_no
FROM prices p
JOIN cards c ON p.card_id = c.id
JOIN shops s ON p.shop_id = s.id
WHERE p.id IN (SELECT MAX(id) FROM prices GROUP BY card_id, shop_id)
GROUP BY s.id, c.id
ORDER BY s.name, p.id DESC
LIMIT 30
""")

current_shop = None
for row in cur.fetchall():
    if row['shop'] != current_shop:
        current_shop = row['shop']
        print(f"\n【{current_shop}】")
    print(f"  {row['card_name'][:50]} -> {row['extracted_card_no'] or 'なし'}")
