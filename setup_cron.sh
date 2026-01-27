#!/bin/bash
# cron自動設定スクリプト
# 使用方法: bash setup_cron.sh

set -e

echo "====================================="
echo "カード価格バッチ cron設定"
echo "====================================="

# 既存のcronジョブを確認
echo "現在のcronジョブ:"
crontab -l 2>/dev/null || echo "(なし)"
echo ""

# 新しいcronジョブを追加（既存を保持）
CRON_JOB='*/30 * * * * cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch.py >> /var/log/card-price-batch.log 2>&1'
CLEANUP_JOB='0 3 * * * cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python -c "from database import cleanup_old_prices; cleanup_old_prices(90)" >> /var/log/card-price-cleanup.log 2>&1'

# 既存のcronに追加（重複チェック）
(crontab -l 2>/dev/null | grep -v "batch.py" | grep -v "cleanup_old_prices"; echo "$CRON_JOB"; echo "$CLEANUP_JOB") | crontab -

echo "cronジョブを設定しました:"
crontab -l
echo ""

# ログファイルの準備
echo "ログファイルを準備..."
sudo touch /var/log/card-price-batch.log
sudo touch /var/log/card-price-cleanup.log
sudo chown ubuntu:ubuntu /var/log/card-price-batch.log
sudo chown ubuntu:ubuntu /var/log/card-price-cleanup.log

echo ""
echo "====================================="
echo "設定完了！"
echo "====================================="
echo ""
echo "確認コマンド:"
echo "  crontab -l                    # cronジョブ一覧"
echo "  tail -f /var/log/card-price-batch.log  # バッチログ監視"
echo ""
