document.addEventListener('DOMContentLoaded', () => {
    const keywordInput = document.getElementById('keyword');
    const searchBtn = document.getElementById('search-btn');
    const sortSelect = document.getElementById('sort-select');
    const stockFilter = document.getElementById('stock-filter');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const resultsEl = document.getElementById('results');
    const resultCountEl = document.getElementById('result-count');
    const homeEl = document.getElementById('home');

    let allProducts = [];

    // ホーム画面データを読み込み
    loadHomeData();

    // 検索実行
    async function search() {
        const keyword = keywordInput.value.trim();
        if (!keyword) {
            showError('検索キーワードを入力してください');
            return;
        }

        // UI状態をリセット
        searchBtn.disabled = true;
        loadingEl.classList.remove('hidden');
        errorEl.classList.add('hidden');
        resultsEl.innerHTML = '';
        resultCountEl.textContent = '';

        // ホーム画面を非表示
        if (homeEl) homeEl.classList.add('hidden');

        try {
            const response = await fetch(`/api/search?keyword=${encodeURIComponent(keyword)}`);

            if (!response.ok) {
                throw new Error('検索に失敗しました');
            }

            const data = await response.json();
            allProducts = flattenResults(data.results);
            renderProducts();
            resultCountEl.textContent = `${data.total_count}件の商品が見つかりました`;

        } catch (err) {
            showError(err.message);
        } finally {
            searchBtn.disabled = false;
            loadingEl.classList.add('hidden');
        }
    }

    // 結果をフラット化
    function flattenResults(results) {
        const products = [];
        for (const siteResult of results) {
            for (const item of siteResult.items) {
                products.push(item);
            }
        }
        return products;
    }

    // 商品を表示
    function renderProducts() {
        // フィルター処理
        const filteredProducts = filterProducts(allProducts, stockFilter ? stockFilter.value : 'all');
        // ソート処理
        const sortedProducts = sortProducts(filteredProducts, sortSelect.value);

        if (sortedProducts.length === 0) {
            resultsEl.innerHTML = '<p style="text-align:center;padding:20px;color:#666;">商品が見つかりませんでした</p>';
            return;
        }

        resultsEl.innerHTML = sortedProducts.map(product => createProductCard(product)).join('');

        // フィルター後の件数を表示
        if (filteredProducts.length !== allProducts.length) {
            resultCountEl.textContent = `${filteredProducts.length}件表示 / 全${allProducts.length}件`;
        }
    }

    // フィルター処理
    function filterProducts(products, filterType) {
        switch (filterType) {
            case 'in-stock':
                return products.filter(p => p.stock > 0);
            case 'out-of-stock':
                return products.filter(p => p.stock === 0);
            default:
                return products;
        }
    }

    // ソート処理
    function sortProducts(products, sortType) {
        const sorted = [...products];

        switch (sortType) {
            case 'price-asc':
                sorted.sort((a, b) => a.price - b.price);
                break;
            case 'price-desc':
                sorted.sort((a, b) => b.price - a.price);
                break;
            case 'site':
                sorted.sort((a, b) => a.site.localeCompare(b.site));
                break;
        }

        return sorted;
    }

    // 商品カードHTML生成
    function createProductCard(product) {
        const siteClass = getSiteClass(product.site);
        const stockClass = product.stock > 0 ? 'in-stock' : 'out-of-stock';
        const imageHtml = product.image_url
            ? `<img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" class="product-image" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="product-image-placeholder" style="display:none"></div>`
            : '<div class="product-image-placeholder"></div>';

        // リダイレクトAPI経由のURL（クリック計測用）
        const redirectUrl = buildRedirectUrl(product.url, product.site, product.name);

        return `
            <div class="product-card">
                ${imageHtml}
                <span class="site-badge ${siteClass}">${escapeHtml(product.site)}</span>
                <div class="product-name">
                    <a href="${redirectUrl}" target="_blank" rel="noopener">
                        ${escapeHtml(product.name)}
                    </a>
                </div>
                <div class="product-price">${escapeHtml(product.price_text)}</div>
                <span class="product-stock ${stockClass}">${escapeHtml(product.stock_text)}</span>
            </div>
        `;
    }

    // リダイレクトURL生成（クリック計測用）
    function buildRedirectUrl(url, site, cardName) {
        const params = new URLSearchParams();
        params.set('url', url);
        if (site) params.set('site', site);
        if (cardName) params.set('card', cardName);
        return `/api/redirect?${params.toString()}`;
    }

    // サイト名からCSSクラスを取得
    function getSiteClass(siteName) {
        if (siteName.includes('カードラッシュ')) return 'cardrush';
        if (siteName.includes('Tier')) return 'tierone';
        if (siteName.includes('バトスキ')) return 'batosuki';
        if (siteName.includes('フルアヘッド')) return 'fullahead';
        if (siteName.includes('遊々亭')) return 'yuyutei';
        if (siteName.includes('ホビーステーション')) return 'hobbystation';
        return '';
    }

    // HTMLエスケープ
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // エラー表示
    function showError(message) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    }

    // ホーム画面データ読み込み
    async function loadHomeData() {
        try {
            const response = await fetch('/api/home');
            if (!response.ok) return;

            const data = await response.json();
            renderHomeData(data);
        } catch (err) {
            console.error('Failed to load home data:', err);
        }
    }

    // ホーム画面描画
    function renderHomeData(data) {
        // 統計情報
        const statsEl = document.getElementById('home-stats');
        if (statsEl && data.stats) {
            statsEl.innerHTML = `
                <span>登録カード: <strong>${data.stats.total_cards.toLocaleString()}</strong>件</span>
                <span>価格データ: <strong>${data.stats.total_prices.toLocaleString()}</strong>件</span>
                ${data.stats.last_updated ? `<span>最終更新: <strong>${formatDate(data.stats.last_updated)}</strong></span>` : ''}
            `;
        }

        // バッチ実行通知
        renderBatchNotification(data.batch_logs);

        // 最近更新
        renderHomeList('recently-updated', data.recently_updated, (item) => `
            <div class="home-item">
                <span class="home-item-name" onclick="searchCard('${escapeHtml(item.name)}')">${escapeHtml(truncate(item.name, 25))}</span>
                <span class="home-item-price">${escapeHtml(item.price_text)}</span>
                <span class="home-item-shop">${escapeHtml(item.site)}</span>
            </div>
        `);

        // 値上がり
        renderHomeList('price-up', data.price_up, (item) => `
            <div class="home-item">
                <span class="home-item-name" onclick="searchCard('${escapeHtml(item.card_name)}')">${escapeHtml(truncate(item.card_name, 20))}</span>
                <span class="home-item-diff up">+${item.diff.toLocaleString()}円</span>
                <span class="home-item-shop">${escapeHtml(item.shop_name)}</span>
            </div>
        `);

        // 値下がり
        renderHomeList('price-down', data.price_down, (item) => `
            <div class="home-item">
                <span class="home-item-name" onclick="searchCard('${escapeHtml(item.card_name)}')">${escapeHtml(truncate(item.card_name, 20))}</span>
                <span class="home-item-diff down">-${item.diff.toLocaleString()}円</span>
                <span class="home-item-shop">${escapeHtml(item.shop_name)}</span>
            </div>
        `);

        // 注目カード
        renderHomeList('hot-cards', data.hot_cards, (item) => `
            <div class="home-item">
                <span class="home-item-name" onclick="searchCard('${escapeHtml(item.card_name)}')">${escapeHtml(truncate(item.card_name, 25))}</span>
                <span class="home-item-clicks">${item.click_count} clicks</span>
            </div>
        `);
    }

    // バッチ実行通知を描画
    function renderBatchNotification(batchLogs) {
        const notificationEl = document.getElementById('batch-notification');
        if (!notificationEl) return;

        // 最新の成功ログを取得（24時間以内）
        if (!batchLogs || batchLogs.length === 0) {
            notificationEl.classList.add('hidden');
            return;
        }

        // 24時間以内のログのみ表示
        const now = new Date();
        const recentLogs = batchLogs.filter(log => {
            const logDate = new Date(log.finished_at);
            const diffHours = (now - logDate) / (1000 * 60 * 60);
            return diffHours < 24 && log.status === 'success';
        });

        if (recentLogs.length === 0) {
            notificationEl.classList.add('hidden');
            return;
        }

        // 各ショップの最新ログを取得
        const shopLogs = {};
        recentLogs.forEach(log => {
            if (!shopLogs[log.shop_name]) {
                shopLogs[log.shop_name] = log;
            }
        });

        const formatTime = (dateStr) => {
            const d = new Date(dateStr);
            return d.toLocaleString('ja-JP', {
                month: 'numeric',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        };

        notificationEl.classList.remove('hidden');
        notificationEl.classList.remove('error');

        const logsHtml = Object.values(shopLogs).map(log => `
            <div class="batch-shop-item">
                <div class="batch-shop-name">${escapeHtml(log.shop_name)}</div>
                <div class="batch-shop-stats">
                    <span>${log.cards_total.toLocaleString()}件取得</span>
                    <span>${log.cards_new.toLocaleString()}件新規</span>
                    <span>${formatTime(log.finished_at)}</span>
                </div>
            </div>
        `).join('');

        notificationEl.innerHTML = `
            <div class="batch-title">巡回完了</div>
            <div class="batch-shops">${logsHtml}</div>
        `;
    }

    // ホームリスト描画
    function renderHomeList(elementId, items, itemRenderer) {
        const el = document.getElementById(elementId);
        if (!el) return;

        if (!items || items.length === 0) {
            el.innerHTML = '<div class="home-empty">データがありません</div>';
            return;
        }

        el.innerHTML = items.map(itemRenderer).join('');
    }

    // 文字列を切り詰め
    function truncate(str, maxLength) {
        if (!str) return '';
        return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
    }

    // 日付フォーマット
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleString('ja-JP', {
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // カード名で検索（グローバル関数）
    window.searchCard = function(cardName) {
        keywordInput.value = cardName;
        search();
    };

    // イベントリスナー
    searchBtn.addEventListener('click', search);

    keywordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            search();
        }
    });

    sortSelect.addEventListener('change', () => {
        if (allProducts.length > 0) {
            renderProducts();
        }
    });

    if (stockFilter) {
        stockFilter.addEventListener('change', () => {
            if (allProducts.length > 0) {
                renderProducts();
            }
        });
    }
});
