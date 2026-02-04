#!/usr/bin/env python3
"""
価格変動検知 & 通知バッチ

お気に入りに登録されているカードの価格変動を検出し、
ユーザーに通知を送信する。

実行方法:
    python batch_notify.py
    python batch_notify.py --dry-run       # 実際には通知を作成しない
    python batch_notify.py --no-x-queue    # X投稿キューをスキップ
    python batch_notify.py --summary-only  # まとめ投稿のみ生成
"""

import argparse
from datetime import datetime

from database import (
    get_connection,
    save_price_change,
    create_notification,
    get_users_with_favorite_card,
    detect_price_changes_for_favorites,
    get_notification_settings,
    # X投稿キュー関連
    create_x_post,
    generate_x_post_content_single,
    generate_x_post_content_summary,
)


def detect_and_notify(dry_run: bool = False, enable_x_queue: bool = True, summary_only: bool = False):
    """価格変動を検出して通知を作成"""
    print(f"[{datetime.now()}] 価格変動検知バッチ開始")
    print(f"  設定: dry_run={dry_run}, x_queue={enable_x_queue}, summary_only={summary_only}")

    # 価格変動を検出
    changes = detect_price_changes_for_favorites()
    print(f"  検出された価格変動: {len(changes)}件")

    if not changes:
        print("  価格変動なし")
        return

    notifications_created = 0
    price_changes_saved = 0
    x_posts_created = 0

    for change in changes:
        card_id = change['card_id']
        shop_id = change['shop_id']
        old_price = change['old_price']
        new_price = change['new_price']
        card_name = change['card_name']
        shop_name = change['shop_name']

        # 価格変動を記録
        change_amount = new_price - old_price
        change_percent = (change_amount / old_price * 100) if old_price > 0 else 0

        if dry_run:
            print(f"  [DRY-RUN] 価格変動: {card_name} @ {shop_name}: {old_price} -> {new_price} ({change_amount:+d}円, {change_percent:+.1f}%)")
            price_change_id = None
        else:
            price_change_id = save_price_change(card_id, shop_id, old_price, new_price)
            price_changes_saved += 1

        # X投稿キューに追加（個別投稿、大きな変動のみ）
        if enable_x_queue and not summary_only:
            # 500円以上または20%以上の変動で個別投稿
            if abs(change_amount) >= 500 or abs(change_percent) >= 20:
                content = generate_x_post_content_single(card_name, shop_name, old_price, new_price, card_id)
                post_type = 'price_drop' if change_amount < 0 else 'price_rise'

                if dry_run:
                    print(f"    [DRY-RUN] X投稿キュー追加: {card_name}")
                else:
                    create_x_post(post_type, content, card_id, price_change_id)
                    x_posts_created += 1

        # サイト内通知
        users = get_users_with_favorite_card(card_id)

        for user in users:
            user_id = user['id']
            site_enabled = user.get('site_enabled', 1)
            price_drop_threshold = user.get('price_drop_threshold', 0) or 0
            price_rise_threshold = user.get('price_rise_threshold', 0) or 0

            # 通知設定をチェック
            if not site_enabled:
                continue

            # 閾値チェック
            if change_amount < 0 and abs(change_amount) < price_drop_threshold:
                continue
            if change_amount > 0 and change_amount < price_rise_threshold:
                continue

            # 通知タイプを決定
            if change_amount < 0:
                notif_type = 'price_drop'
                title = f"値下げ: {card_name}"
                message = f"{shop_name}で{abs(change_amount):,}円値下げ ({old_price:,}円 → {new_price:,}円)"
            else:
                notif_type = 'price_rise'
                title = f"値上げ: {card_name}"
                message = f"{shop_name}で{change_amount:,}円値上げ ({old_price:,}円 → {new_price:,}円)"

            if dry_run:
                print(f"    [DRY-RUN] 通知作成: user_id={user_id}, {title}")
            else:
                create_notification(
                    user_id=user_id,
                    type=notif_type,
                    title=title,
                    message=message,
                    card_id=card_id,
                    price_change_id=price_change_id
                )
                notifications_created += 1

    # まとめ投稿を作成（変動が3件以上ある場合）
    if enable_x_queue and len(changes) >= 3:
        summary_content = generate_x_post_content_summary(changes)
        if dry_run:
            print(f"  [DRY-RUN] まとめX投稿キュー追加")
        else:
            create_x_post('summary', summary_content)
            x_posts_created += 1

    print(f"  価格変動記録: {price_changes_saved}件")
    print(f"  サイト内通知: {notifications_created}件")
    print(f"  X投稿キュー: {x_posts_created}件")
    print(f"[{datetime.now()}] 価格変動検知バッチ完了")


def main():
    parser = argparse.ArgumentParser(description='価格変動検知 & 通知バッチ')
    parser.add_argument('--dry-run', action='store_true', help='実際には通知を作成しない')
    parser.add_argument('--no-x-queue', action='store_true', help='X投稿キューをスキップ')
    parser.add_argument('--summary-only', action='store_true', help='まとめ投稿のみ生成')
    args = parser.parse_args()

    detect_and_notify(
        dry_run=args.dry_run,
        enable_x_queue=not args.no_x_queue,
        summary_only=args.summary_only
    )


if __name__ == '__main__':
    main()
