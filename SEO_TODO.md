# BSPrice SEO対策 TODO

## 1. 技術的なSEO

### 1.1 構造化データ（JSON-LD）の追加
- [ ] 検索結果ページに商品の構造化データを追加
- [ ] トップページにWebSite構造化データを追加
- [ ] パンくずリストの構造化データを追加

```html
<!-- 例: 商品の構造化データ -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "カード名",
  "offers": {
    "@type": "AggregateOffer",
    "lowPrice": "100",
    "highPrice": "500",
    "priceCurrency": "JPY"
  }
}
</script>
```

### 1.2 サイトマップ（sitemap.xml）
- [x] sitemap.xml を作成
- [x] 主要ページを含める（トップ、ランキング、ショップ一覧）
- [x] Google Search Console に送信

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://bs-price.com/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://bs-price.com/ranking</loc>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://bs-price.com/shops</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
```

### 1.3 robots.txt
- [x] robots.txt を作成
- [x] クロール許可/禁止を設定

```
User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/
Sitemap: https://bs-price.com/sitemap.xml
```

### 1.4 ページ速度の改善
- [ ] 画像の圧縮・WebP形式への変換
- [ ] CSS/JSの圧縮（minify）
- [ ] キャッシュヘッダーの設定
- [ ] 遅延読み込み（lazy loading）の実装

### 1.5 その他の技術対策
- [ ] canonical タグの追加（重複コンテンツ対策）
- [x] OGP（Open Graph Protocol）タグの追加（SNS共有用）
- [ ] favicon の設定

```html
<!-- OGPタグ例 -->
<meta property="og:title" content="BSPrice - バトスピ価格比較">
<meta property="og:description" content="バトルスピリッツのカード価格を複数ショップで比較">
<meta property="og:type" content="website">
<meta property="og:url" content="https://bs-price.com/">
<meta property="og:image" content="https://bs-price.com/static/ogp.png">
```

---

## 2. コンテンツSEO

### 2.1 キーワード最適化
- [ ] 各ページのtitle/descriptionを見直し
- [ ] h1/h2タグの適切な使用
- [ ] 検索されやすいキーワードを含める
  - 「バトスピ 価格」
  - 「バトスピ シングル」
  - 「バトルスピリッツ 買取」
  - 「バトスピ 相場」

### 2.2 コンテンツの充実
- [ ] カード詳細ページの作成（個別カードのURL）
- [ ] ブログ/お知らせページの追加
- [ ] FAQ/使い方ガイドの追加

### 2.3 内部リンクの最適化
- [ ] 関連カードへのリンク
- [ ] パンくずリストの追加

---

## 3. 外部対策

### 3.1 Google Search Console
- [x] サイトを登録
- [x] 所有権を確認
- [x] サイトマップを送信
- [ ] インデックス状況を確認

### 3.2 Google Analytics
- [ ] GA4を導入
- [ ] アクセス解析を開始

### 3.3 被リンク獲得
- [ ] SNSアカウント作成（Twitter/X）
- [ ] バトスピ関連コミュニティでの紹介
- [ ] ブログ/まとめサイトへの掲載依頼

---

## 4. 優先順位

### 高（すぐやるべき）
1. ~~Google Search Console 登録~~ ✅ 完了
2. ~~sitemap.xml 作成・送信~~ ✅ 完了
3. ~~robots.txt 作成~~ ✅ 完了
4. ~~OGPタグ追加~~ ✅ 完了

### 中（余裕があれば）
5. 構造化データ追加
6. ページ速度改善
7. Google Analytics 導入

### 低（将来的に）
8. カード詳細ページ作成
9. ブログ機能追加
10. SNS運用

---

## 参考リンク

- Google Search Console: https://search.google.com/search-console/
- Google Analytics: https://analytics.google.com/
- 構造化データテスト: https://search.google.com/test/rich-results
- PageSpeed Insights: https://pagespeed.web.dev/
