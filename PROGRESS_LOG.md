# カード価格比較アプリ 進捗ログ

## 2026/01/28 作業記録（最終更新）

### 完了した作業

#### 1. バッチ成功通知機能の実装
- `batch_logs`テーブルをDBに追加
- `save_batch_log()`, `get_recent_batch_logs()`関数を実装
- `batch_crawl.py`で巡回完了時にログを自動保存
- `/api/home`にbatch_logsを追加
- フロントエンドにバッチ通知バナーを追加（紫グラデーション）
- 24時間以内の成功ログを表示（ショップ名、取得カード数、新規追加数、完了時刻）

#### 2. EC2環境の修正
- SSHユーザー名が`ec2-user`から`ubuntu`に変更されていることを確認
- 必要なPythonパッケージをインストール: uvicorn, fastapi, httpx, beautifulsoup4, lxml

#### 3. 在庫フィルター機能の追加
- フロントエンドに「在庫あり/売り切れ」フィルターを追加
- `filterProducts()`関数で在庫状態によるフィルタリング

#### 4. 追加ショップの巡回実装（EC2自動）
- **ホビーステーション** (httpx使用) - テスト完了
- **バトスキ** (httpx使用) - テスト完了
- **フルアヘッド** (Selenium使用) - テスト完了

#### 5. 遊々亭ローカルクローラーの実装
- EC2からは403ブロック → ローカルPC方式で対応
- `local/crawl_yuyutei.py` - ローカル実行用クローラー
- `local/import_yuyutei.py` - EC2でのインポートスクリプト
- `local/crawl_and_upload.bat` - 自動化バッチファイル
- テスト完了: BS74セット 169件取得・インポート成功

### サーバー情報
- Elastic IP: 54.64.210.46
- SSH接続: `ssh -i card-price-app-key.pem ubuntu@54.64.210.46`
- プロジェクトパス: `/home/ubuntu/project`
- 仮想環境: `/home/ubuntu/venv`

### Cronスケジュール（UTC時間）
- 18:00 (JST 3:00) - batch_crawl.py --shop all --pages 50

---

## 現在のDB状況
- 登録カード: 3,902件
- 価格データ: 4,553件
- 遊々亭カード: 167件

## 対応ショップ一覧

| ショップ | 方式 | 実行場所 | ステータス |
|---------|------|---------|-----------|
| カードラッシュ | Selenium | EC2 | 自動（Cron） |
| Tier One | httpx | EC2 | 自動（Cron） |
| ホビーステーション | httpx | EC2 | 自動（Cron） |
| バトスキ | httpx | EC2 | 自動（Cron） |
| フルアヘッド | Selenium | EC2 | 自動（Cron） |
| 遊々亭 | httpx | ローカルPC | 手動/タスクスケジューラ |

---

## 遊々亭ローカルクローラーの使い方

### 手動実行
```bash
cd C:\Users\ykh2435064\Desktop\project\local

# 全セットをクロール
python crawl_yuyutei.py

# 特定セットのみ
python crawl_yuyutei.py --sets bs74 bs73

# セット一覧を表示
python crawl_yuyutei.py --list-sets
```

### 自動実行（Windowsタスクスケジューラ）
1. タスクスケジューラを開く
2. 「基本タスクの作成」
3. トリガー: 毎日 22:00（PCが起動している時間）
4. 操作: `crawl_and_upload.bat` を実行
5. 開始: `C:\Users\ykh2435064\Desktop\project\local`

### ファイル構成
```
C:\Users\ykh2435064\Desktop\project\local\
├── crawl_yuyutei.py      # クローラー
├── import_yuyutei.py     # インポート（EC2側にもコピー）
├── crawl_and_upload.bat  # 自動化バッチ
└── output/               # 出力JSON
    └── yuyutei_YYYYMMDD_HHMMSS.json
```

---

## 今後のタスク

### 優先度: 高
1. **Cronの動作確認**
   - 翌朝、ホーム画面でバッチ通知が5ショップ分表示されるか確認

### 優先度: 中
2. **遊々亭の定期実行設定**
   - Windowsタスクスケジューラで自動化
   - 全セット巡回（約40セット）

3. **batch_popular.py の動作確認**

### 優先度: 低
4. **モニタリング強化**
   - サーバーログの定期確認
   - エラー通知の仕組み

---

## ファイル構成（EC2）
```
/home/ubuntu/project/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── batch_crawl.py    # 5ショップ対応
│   └── card_price.db
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── local/
│   └── import_yuyutei.py # インポートスクリプト
├── data/
│   └── *.json            # アップロードされたデータ
└── logs/
```
