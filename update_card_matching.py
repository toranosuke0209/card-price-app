#!/usr/bin/env python3
"""カード番号再抽出と類似度マッチング"""
from database import get_connection, extract_card_number, extract_base_card_name, match_cards_by_name

def update_all_card_numbers():
    """全カードのカード番号・基本名を再抽出"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 全カードを取得
        cursor.execute("SELECT id, name FROM cards")
        cards = cursor.fetchall()

        updated = 0
        for card in cards:
            card_no = extract_card_number(card['name'])
            base_name = extract_base_card_name(card['name'])

            cursor.execute("""
                UPDATE cards
                SET extracted_card_no = ?, base_name = ?
                WHERE id = ?
            """, (card_no, base_name, card['id']))
            updated += 1

        conn.commit()
        print(f"Updated {updated} cards")

def show_stats():
    """ショップ別統計を表示"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
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

        print("\n=== ショップ別カード番号抽出率 ===")
        for row in cursor.fetchall():
            pct = (row['with_no'] / row['cards'] * 100) if row['cards'] > 0 else 0
            print(f"{row['shop']}: {row['cards']}枚中 {row['with_no']}枚 ({pct:.1f}%)")

if __name__ == "__main__":
    print("=== Step 1: カード番号再抽出 ===")
    update_all_card_numbers()

    print("\n=== Step 2: 名前マッチング ===")
    match_cards_by_name()

    show_stats()
