# BSPrice TODO & 作業ログ

**最終更新: 2026-02-02**

---

## 現在のTODO（優先順）

### 1. SEO対策

#### 完了済み
- [x] Google Search Console 登録
- [x] sitemap.xml 作成・送信
- [x] robots.txt 作成
- [x] OGPタグ追加
- [x] カード詳細ページ作成
- [x] 構造化データ(JSON-LD)追加
- [x] Google Analytics 導入 (G-5WL1F00NNC)

#### 次にやること
- [x] **favicon設定**
  - favicon.ico (32x32, 16x16)
  - apple-touch-icon.png (180x180)
  - 全HTMLに `<link rel="icon">` 追加
- [ ] ページ速度改善
  - 画像圧縮・WebP変換
  - CSS/JS圧縮
  - 遅延読み込み実装
- [ ] canonicalタグ追加
- [ ] SNSアカウント作成

### 2. 機能追加（低優先度）

- [ ] お気に入りカードの価格一覧ページ
- [ ] 価格変動通知機能
- [ ] ブログ/お知らせ機能
- [ ] FAQ/使い方ガイド

### 3. 運用改善（低優先度）

- [ ] systemdサービス化
- [ ] ログローテーション設定
- [ ] バックアップ自動化

---

## 作業履歴

### 2026-02-02: ドラスタ追加・favicon設定
- ドラスタ（ドラゴンスター）クローラー追加
  - Selenium使用（Cloudflare対策）
  - 50シリーズずつバッチ処理、進捗管理
  - SALE・傷あり特価ページ対応（--special）
  - 本日87シリーズ完了、残り92シリーズ
- favicon設定完了（favicon.io使用）
- デスクトップショートカット作成
  - DorasutaCrawl.lnk（通常）
  - DorasutaSpecial.lnk（特価）

### 2026-01-31: SEO対策
- 構造化データ(JSON-LD)追加
  - WebSite + SearchAction (トップページ)
  - Product + AggregateOffer (カード詳細ページ)
  - BreadcrumbList (検索/カード詳細ページ)
- Google Analytics導入 (G-5WL1F00NNC)

### 2026-01-30: 認証バグ修正・広告管理改善
- JWT `sub`クレームを文字列に修正（401エラー解消）
- bcryptを4.0.1にダウングレード（互換性エラー解消）
- Amazon/楽天商品管理APIの修正
- 広告商品の編集機能追加

### 2026-01-29: HTTPS化・人気キーワード機能
- Let's Encrypt SSL証明書でHTTPS化
- ホビステ画像プロキシAPI追加
- フルアヘッド画像修正完了
- 遊々亭クローラー全セット対応
- 人気キーワード管理機能実装（cron 6時/18時自動更新）

### 2026-01-28: ログイン機能・バッチ通知
- JWT認証ベースのログイン機能実装
- お気に入り機能実装
- 管理者ダッシュボード作成
- バッチ成功通知バナー追加
- 在庫フィルター機能追加
- 追加ショップ巡回実装（ホビステ、バトスキ、フルアヘッド）
- 遊々亭ローカルクローラー実装

### 2026-01-27: DB参照方式に移行
- スクレイピング廃止→DB参照方式に変更
- バッチ処理（1時間間隔）
- リダイレクトAPI（クリック計測）
- ホーム画面API（値上がり/値下がり/注目カード）
- キーワード自動追加機能
- 30日間未検索キーワードの自動削除

### 2026-01-25: 初版リリース
- 6サイト対応（遊々亭は403ブロック）
- Seleniumタイムアウト問題解決
- t3.mediumへアップグレード
- 画像エラーハンドリング追加

---

## 参考リンク

- Google Search Console: https://search.google.com/search-console/
- Google Analytics: https://analytics.google.com/
- 構造化データテスト: https://search.google.com/test/rich-results
- PageSpeed Insights: https://pagespeed.web.dev/

---

## DBスキーマ

### usersテーブル
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### favoritesテーブル
```sql
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, card_id)
);
```

### admin_invitesテーブル
```sql
CREATE TABLE admin_invites (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    created_by INTEGER,
    used_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    used_at TEXT
);
```
