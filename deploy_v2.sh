#!/bin/bash
# v2デプロイスクリプト
# EC2上で実行してください

set -e

echo "=== v2 デプロイ開始 ==="

cd ~/project/backend

# 仮想環境をアクティベート
source venv/bin/activate

# DBマイグレーション実行
echo "DBマイグレーション実行中..."
python -c "from database import migrate_v2; migrate_v2()"

# 進捗テーブル初期化（カードラッシュ用）
echo "バッチ進捗初期化中..."
python -c "
from database import init_batch_progress, get_shop_by_name
shop = get_shop_by_name('カードラッシュ')
if shop:
    init_batch_progress(shop.id)
    print(f'Initialized batch progress for shop_id={shop.id}')
"

# サービス再起動
echo "サービス再起動中..."
sudo systemctl restart card-price-app

# ステータス確認
echo "サービスステータス:"
sudo systemctl status card-price-app --no-pager

echo ""
echo "=== デプロイ完了 ==="
echo ""
echo "新しいバッチコマンド:"
echo "  python batch_crawl.py --status    # 巡回進捗確認"
echo "  python batch_crawl.py --pages 5   # 5ページ巡回テスト"
echo "  python batch_popular.py --stats   # 人気カード統計"
echo "  python batch_queue.py --status    # キュー状況確認"
