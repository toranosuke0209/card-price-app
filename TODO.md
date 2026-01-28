# TODO

## 未完了タスク（2026/01/27）

### 1. EC2の更新（GitHubからプル＆cron変更）
コードはGitHubにプッシュ済み。EC2で以下を実行：

```bash
# 最新コードを取得
cd /home/ubuntu/project && git pull

# cronを1時間間隔に更新
echo '0 * * * * cd /home/ubuntu/project/backend && /home/ubuntu/project/backend/venv/bin/python batch.py >> /var/log/card-price-batch.log 2>&1' > /tmp/mycron && crontab /tmp/mycron

# 確認
crontab -l
```

### 2. スマホでの不具合
- 詳細未確認（要調査）

### 3. ホームに戻るボタンの追加
- 検索結果画面からホーム画面に戻るボタンを追加する




4　24時間に1回にするが時間ごとに検索するキーワードを分ける
---

## 完了済み（2026/01/27）
- [x] DB参照方式に変更（スクレイピング廃止）
- [x] バッチ処理（30分→1時間に変更）
- [x] リダイレクトAPI（クリック計測）
- [x] ホーム画面API（値上がり/値下がり/注目カード）
- [x] キーワード自動追加機能（3文字以上のみ）
- [x] 30日間検索されていないキーワードの自動削除
- [x] EC2デプロイ（http://54.64.210.46:8000）
