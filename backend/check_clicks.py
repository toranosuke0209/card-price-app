from database import get_connection

with get_connection() as conn:
    # カード別クリック数
    cursor = conn.execute("""
        SELECT c.name, COUNT(*) as cnt
        FROM clicks cl
        JOIN cards c ON cl.card_id = c.id
        GROUP BY cl.card_id
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print("=== カード別クリック数 TOP15 ===")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}回")

    # 総クリック数
    cursor = conn.execute("SELECT COUNT(*) FROM clicks")
    total = cursor.fetchone()[0]
    print(f"\n総クリック数: {total}")

    # 同一秒での重複確認
    cursor = conn.execute("""
        SELECT card_id, shop_id, clicked_at, COUNT(*) as cnt
        FROM clicks
        GROUP BY card_id, shop_id, strftime('%Y-%m-%d %H:%M:%S', clicked_at)
        HAVING cnt > 1
        LIMIT 10
    """)
    dups = cursor.fetchall()
    print("\n=== 同一秒での重複クリック ===")
    if dups:
        for row in dups:
            print(f"card_id={row[0]}, shop_id={row[1]}, time={row[2]}, count={row[3]}")
    else:
        print("なし（重複なし）")
