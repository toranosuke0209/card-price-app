#!/bin/bash
# EC2インスタンス自動セットアップスクリプト
# 使用方法: bash setup_ec2.sh

set -e

echo "========================================="
echo "カード価格比較アプリ EC2セットアップ"
echo "========================================="

# 色付きメッセージ用
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# システムパッケージの更新
echo -e "${GREEN}[1/7] システムパッケージを更新中...${NC}"
sudo apt update && sudo apt upgrade -y

# Python 3とpipのインストール
echo -e "${GREEN}[2/7] Python 3とpipをインストール中...${NC}"
sudo apt install -y python3-pip python3-venv

# Google Chromeのインストール
echo -e "${GREEN}[3/7] Google Chromeをインストール中...${NC}"
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# ChromeDriverのインストール
echo -e "${GREEN}[4/7] ChromeDriverをインストール中...${NC}"
sudo apt install -y unzip wget
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)
echo "Chrome version: $CHROME_VERSION"

# ChromeDriverの最新版をダウンロード（Chrome 131用）
wget -q https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.87/linux64/chromedriver-linux64.zip
unzip -q chromedriver-linux64.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
rm -rf chromedriver-linux64.zip chromedriver-linux64

# ChromeDriverのバージョン確認
chromedriver --version

# 日本語フォントのインストール
echo -e "${GREEN}[5/7] 日本語フォントをインストール中...${NC}"
sudo apt install -y fonts-noto-cjk

# Python仮想環境の作成
echo -e "${GREEN}[6/7] Python仮想環境を作成中...${NC}"
cd ~/project/backend
python3 -m venv venv
source venv/bin/activate

# Python依存関係のインストール
echo -e "${GREEN}[7/9] Python依存関係をインストール中...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# データベース初期化
echo -e "${GREEN}[8/9] データベースを初期化中...${NC}"
python database.py

# ログディレクトリの準備
echo -e "${GREEN}[9/9] ログディレクトリを準備中...${NC}"
sudo touch /var/log/card-price-batch.log
sudo touch /var/log/card-price-cleanup.log
sudo chown ubuntu:ubuntu /var/log/card-price-batch.log
sudo chown ubuntu:ubuntu /var/log/card-price-cleanup.log

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}セットアップが完了しました！${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}次のステップ:${NC}"
echo ""
echo "1. バッチ処理を手動実行してデータを蓄積:"
echo "   cd ~/project/backend"
echo "   source venv/bin/activate"
echo "   python batch.py"
echo ""
echo "2. cron設定（30分ごとにバッチ実行）:"
echo "   crontab -e"
echo "   # 以下を追加:"
echo "   */30 * * * * cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch.py >> /var/log/card-price-batch.log 2>&1"
echo ""
echo "3. サーバーを起動:"
echo "   cd ~/project/backend"
echo "   source venv/bin/activate"
echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "4. systemdで常駐化（推奨）:"
echo "   sudo cp ~/project/card-price-app.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable card-price-app"
echo "   sudo systemctl start card-price-app"
echo ""
echo "5. ブラウザで http://$(curl -s ifconfig.me):8000 にアクセス"
echo ""
