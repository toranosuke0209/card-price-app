#!/usr/bin/env python3
"""バッチログを確認するスクリプト"""
from database import get_connection

with get_connection() as conn:
    cursor = conn.cursor()

    # 全ショップ名を取得
    cursor.execute("SELECT DISTINCT shop_name FROM batch_logs")
    shops = [row[0] for row in cursor.fetchall()]
    print(f"登録されているショップ: {shops}")

    # 各ショップの最新ログを取得
    cursor.execute("""
        SELECT shop_name, status, cards_total, cards_new, finished_at
        FROM batch_logs b1
        WHERE finished_at = (
            SELECT MAX(finished_at) FROM batch_logs b2
            WHERE b2.shop_name = b1.shop_name
        )
        ORDER BY finished_at DESC
    """)
    rows = cursor.fetchall()

    print(f"\n各ショップの最新ログ ({len(rows)}件):")
    for row in rows:
        print(f"  {row[0]}: {row[1]}, {row[2]}件取得, {row[3]}件新規, {row[4]}")

    # 直近10件のログ
    cursor.execute("""
        SELECT shop_name, batch_type, status, cards_total, finished_at
        FROM batch_logs
        ORDER BY finished_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()

    print(f"\n直近10件のログ:")
    for row in rows:
        print(f"  {row[0]}: {row[1]}, {row[2]}, {row[3]}件, {row[4]}")
