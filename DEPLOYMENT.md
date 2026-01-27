# AWS EC2デプロイ手順

## 前提条件
- AWSアカウント
- ローカルマシンにSSHクライアント

## ステップ1: EC2インスタンスの作成

1. AWS EC2コンソールにアクセス
2. 「インスタンスを起動」をクリック
3. 以下の設定を選択：
   - **名前**: card-price-app（任意）
   - **AMI**: Ubuntu Server 22.04 LTS
   - **インスタンスタイプ**: t2.medium（推奨）
     - t2.smallでも動作しますが、Selenium使用時にメモリ不足の可能性あり
   - **キーペア**: 新規作成または既存のキーペアを選択
   - **ストレージ**: 20GB gp3

4. **セキュリティグループの設定**:
   - SSH（ポート22）: 自分のIPアドレスから
   - カスタムTCP（ポート8000）: 0.0.0.0/0（全て）
     - セキュリティ強化のため、後でNginx（ポート80/443）を設定推奨

5. インスタンスを起動

6. **Elastic IP（オプション）**:
   - 固定IPが必要な場合は、Elastic IPを割り当て

## ステップ2: EC2に接続

```bash
# キーファイルの権限を変更（初回のみ）
chmod 400 your-key.pem

# SSH接続
ssh -i your-key.pem ubuntu@<EC2のパブリックIP>
```

## ステップ3: 必要なソフトウェアのインストール

EC2インスタンスに接続したら、以下のコマンドを実行：

```bash
# システムパッケージを更新
sudo apt update && sudo apt upgrade -y

# Python 3とpipをインストール
sudo apt install -y python3-pip python3-venv

# Chrome/Chromiumと依存関係をインストール
sudo apt install -y chromium-browser chromium-chromedriver

# または、最新のChromeをインストール（推奨）
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# ChromeDriverをインストール
sudo apt install -y unzip
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)
wget https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.87/linux64/chromedriver-linux64.zip
unzip chromedriver-linux64.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
rm -rf chromedriver-linux64.zip chromedriver-linux64

# 日本語フォントをインストール（オプション）
sudo apt install -y fonts-noto-cjk
```

## ステップ4: プロジェクトファイルのアップロード

### オプションA: SCP経由（ローカルマシンから）

```bash
# ローカルマシンで実行
cd C:\Users\toraa\OneDrive\デスクトップ
scp -i your-key.pem -r project ubuntu@<EC2のIP>:~/
```

### オプションB: Git経由（推奨）

```bash
# EC2インスタンスで実行
cd ~
git clone https://github.com/your-username/your-repo.git project
cd project
```

## ステップ5: コードの修正

EC2インスタンスで以下を実行：

```bash
cd ~/project/backend

# base.pyを編集
nano scrapers/base.py
```

`CHROMEDRIVER_PATH` の行を以下に変更：

```python
# 変更前
CHROMEDRIVER_PATH = r"C:\Users\toraa\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"

# 変更後
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
```

保存して終了（Ctrl+O, Enter, Ctrl+X）

## ステップ6: Python依存関係のインストール

```bash
cd ~/project/backend

# 仮想環境を作成（推奨）
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install --upgrade pip
pip install -r requirements.txt
```

## ステップ7: サーバーの起動

### オプションA: テスト起動

```bash
cd ~/project/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

ブラウザで `http://<EC2のIP>:8000` にアクセスして動作確認

### オプションB: バックグラウンド実行（nohup）

```bash
cd ~/project/backend
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# ログを確認
tail -f server.log

# サーバーを停止する場合
pkill -f uvicorn
```

### オプションC: systemdサービス（推奨）

systemdサービスファイルを作成：

```bash
sudo nano /etc/systemd/system/card-price-app.service
```

以下の内容を貼り付け：

```ini
[Unit]
Description=Card Price Comparison App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/project/backend
Environment="PATH=/home/ubuntu/project/backend/venv/bin"
ExecStart=/home/ubuntu/project/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

サービスを有効化して起動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable card-price-app
sudo systemctl start card-price-app

# ステータス確認
sudo systemctl status card-price-app

# ログ確認
sudo journalctl -u card-price-app -f
```

## ステップ8: Nginx + HTTPS設定（オプション、推奨）

### Nginxのインストール

```bash
sudo apt install -y nginx
```

### Nginx設定

```bash
sudo nano /etc/nginx/sites-available/card-price-app
```

以下の内容を貼り付け：

```nginx
server {
    listen 80;
    server_name <your-domain.com or EC2のIP>;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

設定を有効化：

```bash
sudo ln -s /etc/nginx/sites-available/card-price-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### セキュリティグループの更新

- ポート80（HTTP）を追加
- ポート443（HTTPS）を追加
- ポート8000への直接アクセスを削除（127.0.0.1からのみ許可）

### Let's Encrypt SSL証明書（HTTPSのため）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## トラブルシューティング

### ChromeDriverエラー

```bash
# ChromeDriverのバージョン確認
chromedriver --version
google-chrome --version

# バージョンが一致しない場合は再インストール
```

### メモリ不足エラー

```bash
# スワップ領域を追加
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### ポート8000にアクセスできない

```bash
# ファイアウォール確認
sudo ufw status

# ポートが開いているか確認
sudo netstat -tulpn | grep 8000

# セキュリティグループを再確認
```

## メンテナンス

### サーバー再起動

```bash
sudo systemctl restart card-price-app
```

### ログ確認

```bash
# systemdログ
sudo journalctl -u card-price-app -n 100

# Nginxログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### アプリ更新

```bash
cd ~/project
git pull  # Gitを使用している場合
sudo systemctl restart card-price-app
```

## コスト削減のヒント

1. **インスタンスの停止**: 使用しない時はインスタンスを停止（ストレージ料金のみ）
2. **リザーブドインスタンス**: 長期利用の場合はコスト削減
3. **スポットインスタンス**: 開発環境では検討可能

## セキュリティのベストプラクティス

1. SSH鍵の管理を厳重に
2. 不要なポートは閉じる
3. 定期的なシステムアップデート
4. HTTPSを必ず使用（本番環境）
5. 環境変数で機密情報を管理（.envファイルなど）
