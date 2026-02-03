# Claude Code デプロイ手順

## EC2接続情報
- **キーペア**: `C:\Users\ykh2435064\Desktop\card-price-app-key.pem`
- **ユーザー**: `ubuntu`
- **ドメイン**: `bsprice.net`
- **注意**: IPアドレスは変わる可能性があるため、AWSコンソールで確認すること

## デプロイ手順

### 1. ファイルのアップロード (PowerShell経由)
```powershell
# バックエンドファイル
powershell.exe -Command "scp -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' 'C:\Users\ykh2435064\Desktop\project\backend\ファイル名' ubuntu@IPアドレス:/home/ubuntu/project/backend/"

# フロントエンドファイル
powershell.exe -Command "scp -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' 'C:\Users\ykh2435064\Desktop\project\frontend\ファイル名' ubuntu@IPアドレス:/home/ubuntu/project/frontend/"
```

### 2. SSH接続
```powershell
powershell.exe -Command "ssh -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' ubuntu@IPアドレス 'コマンド'"
```

### 3. サーバー再起動
```powershell
# プロセス停止
powershell.exe -Command "ssh -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' ubuntu@IPアドレス 'sudo pkill -f uvicorn'"

# プロセス起動
powershell.exe -Command "ssh -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' ubuntu@IPアドレス 'cd /home/ubuntu/project/backend && sudo nohup /home/ubuntu/project/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile=/etc/letsencrypt/live/bsprice.net/privkey.pem --ssl-certfile=/etc/letsencrypt/live/bsprice.net/fullchain.pem > /home/ubuntu/project/server.log 2>&1 &'"
```

### 4. プロセス確認
```powershell
powershell.exe -Command "ssh -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' ubuntu@IPアドレス 'ps aux | grep uvicorn | grep -v grep'"
```

### 5. ログ確認
```powershell
powershell.exe -Command "ssh -i 'C:\Users\ykh2435064\Desktop\card-price-app-key.pem' ubuntu@IPアドレス 'tail -50 /home/ubuntu/project/server.log'"
```

## DBマイグレーション
マイグレーションが必要な場合は、スクリプトファイルを作成してアップロード・実行する：
```python
# migrate_xxx.py
from database import migrate_関数名
migrate_関数名()
print("Migration completed!")
```

## 注意事項
- IPアドレスは変わることがあるので、接続できない場合はAWSコンソールで確認
- サービスはsystemdではなくnohupで起動している
- SSL証明書は Let's Encrypt (bsprice.net)
- ポート443でHTTPS直接提供（Nginx不使用）
