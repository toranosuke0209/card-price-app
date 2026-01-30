# BSPrice SEO対策 TODO

**最終更新: 2026-01-31**

---

## 完了済み

### 高優先度 ✅
1. ~~Google Search Console 登録~~ ✅ 完了
2. ~~sitemap.xml 作成・送信~~ ✅ 完了
3. ~~robots.txt 作成~~ ✅ 完了
4. ~~OGPタグ追加~~ ✅ 完了
5. ~~カード詳細ページ作成~~ ✅ 完了

### 中優先度 ✅
6. ~~構造化データ(JSON-LD)追加~~ ✅ 完了 (2026-01-31)
   - WebSite + SearchAction (トップページ)
   - Product + AggregateOffer (カード詳細ページ)
   - BreadcrumbList (検索/カード詳細ページ)
7. ~~Google Analytics 導入~~ ✅ 完了 (2026-01-31)
   - 測定ID: G-5WL1F00NNC
   - 全HTMLページに設置済み

---

## 次にやること（優先順）

### 1. favicon設定
- [ ] favicon.ico を作成（32x32, 16x16）
- [ ] apple-touch-icon.png を作成（180x180）
- [ ] 全HTMLに `<link rel="icon">` を追加

### 2. ページ速度改善
- [ ] 画像の圧縮・WebP形式への変換
- [ ] CSS/JSの圧縮（minify）
- [ ] キャッシュヘッダーの設定
- [ ] 遅延読み込み（lazy loading）の実装
- 確認: https://pagespeed.web.dev/

### 3. canonicalタグ追加
- [ ] 各ページに canonical タグを追加（重複コンテンツ対策）

### 4. SNSアカウント作成
- [ ] Twitter/X アカウント作成
- [ ] バトスピ関連コミュニティでの紹介

---

## 低優先度（将来的に）

- [ ] ブログ/お知らせ機能追加
- [ ] FAQ/使い方ガイド
- [ ] キーワード最適化（title/description見直し）

---

## 参考リンク

- Google Search Console: https://search.google.com/search-console/
- Google Analytics: https://analytics.google.com/
- 構造化データテスト: https://search.google.com/test/rich-results
- PageSpeed Insights: https://pagespeed.web.dev/

---

## 技術メモ

### サーバー情報
- IP: 54.64.210.46
- ユーザー: ubuntu
- SSHキー: C:\Users\ykh2435064\Desktop\card-price-app-key.pem

### デプロイコマンド
```bash
# HTMLファイルをデプロイ
scp -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" frontend/*.html ubuntu@54.64.210.46:/home/ubuntu/project/frontend/

# サーバー再起動
ssh -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" ubuntu@54.64.210.46 "sudo pkill -f uvicorn; sleep 2; cd /home/ubuntu/project/backend && sudo nohup /home/ubuntu/project/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile /etc/letsencrypt/live/bsprice.net/privkey.pem --ssl-certfile /etc/letsencrypt/live/bsprice.net/fullchain.pem > /tmp/uvicorn.log 2>&1 &"
```

### 巡回バッチ手動実行
```bash
ssh -i "C:\Users\ykh2435064\Desktop\card-price-app-key.pem" ubuntu@54.64.210.46 "cd /home/ubuntu/project/backend && /home/ubuntu/venv/bin/python batch_crawl.py --shop all --pages 50"
```
