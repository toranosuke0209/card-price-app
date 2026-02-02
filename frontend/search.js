/**
 * 検索結果ページ用JavaScript
 * ページネーション対応
 */
document.addEventListener('DOMContentLoaded', () => {
    const keywordInput = document.getElementById('keyword');
    const searchBtn = document.getElementById('search-btn');
    const sortSelect = document.getElementById('sort-select');
    const stockFilter = document.getElementById('stock-filter');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error');
    const resultsEl = document.getElementById('results');
    const resultCountEl = document.getElementById('result-count');
    const paginationEl = document.getElementById('pagination');

    let favoriteCardIds = [];
    let currentSearchState = {
        keyword: '',
        page: 1,
        sort: 'price-asc',
        stock: 'all'
    };

    // URLパラメータから初期状態を取得
    function initFromURL() {
        const params = new URLSearchParams(window.location.search);
        currentSearchState.keyword = params.get('q') || '';
        currentSearchState.page = parseInt(params.get('page')) || 1;
        currentSearchState.sort = params.get('sort') || 'price-asc';
        currentSearchState.stock = params.get('stock') || 'all';

        // フォームに反映
        keywordInput.value = currentSearchState.keyword;
        sortSelect.value = currentSearchState.sort;
        stockFilter.value = currentSearchState.stock;

        // キーワードがあれば検索実行
        if (currentSearchState.keyword) {
            search();
        }
    }

    // お気に入りIDを読み込み（ログイン時のみ）
    async function loadFavoriteIds() {
        if (typeof Favorites !== 'undefined' && Auth.isLoggedIn()) {
            favoriteCardIds = await Favorites.getIds();
        }
    }

    // URLを更新（履歴に追加）
    function updateURL(pushState = true) {
        const params = new URLSearchParams();
        params.set('q', currentSearchState.keyword);
        if (currentSearchState.page > 1) params.set('page', currentSearchState.page);
        if (currentSearchState.sort !== 'price-asc') params.set('sort', currentSearchState.sort);
        if (currentSearchState.stock !== 'all') params.set('stock', currentSearchState.stock);

        const newURL = `/search?${params.toString()}`;
        if (pushState) {
            window.history.pushState(currentSearchState, '', newURL);
        } else {
            window.history.replaceState(currentSearchState, '', newURL);
        }
    }

    // 検索実行
    async function search(pushState = true) {
        const keyword = keywordInput.value.trim();
        if (!keyword) {
            showError('検索キーワードを入力してください');
            return;
        }

        // 状態を更新
        if (keyword !== currentSearchState.keyword) {
            currentSearchState.page = 1; // キーワード変更時はページをリセット
        }
        currentSearchState.keyword = keyword;
        currentSearchState.sort = sortSelect.value;
        currentSearchState.stock = stockFilter.value;

        // URL更新
        updateURL(pushState);

        // UI状態をリセット
        searchBtn.disabled = true;
        loadingEl.classList.remove('hidden');
        errorEl.classList.add('hidden');
        resultsEl.innerHTML = '';
        paginationEl.classList.add('hidden');
        resultCountEl.textContent = '';

        try {
            const params = new URLSearchParams({
                keyword: currentSearchState.keyword,
                page: currentSearchState.page,
                per_page: 20,
                sort: currentSearchState.sort,
                stock: currentSearchState.stock
            });

            const response = await fetch(`/api/search?${params.toString()}`);

            if (!response.ok) {
                throw new Error('検索に失敗しました');
            }

            const data = await response.json();
            renderProducts(data.items);
            renderPagination(data.page, data.total_pages, data.total_count);

            // ページタイトル更新
            document.title = `「${keyword}」の検索結果 | BSPrice - バトスピ価格比較`;

            // 結果件数表示
            const start = (data.page - 1) * 20 + 1;
            const end = Math.min(data.page * 20, data.total_count);
            if (data.total_count > 0) {
                resultCountEl.textContent = `${data.total_count}件中 ${start}-${end}件を表示`;
            } else {
                resultCountEl.textContent = '0件';
            }

            // Amazonセクション表示
            showAmazonSection(keyword);
            // 楽天セクション表示
            showRakutenSection(keyword);

        } catch (err) {
            showError(err.message);
        } finally {
            searchBtn.disabled = false;
            loadingEl.classList.add('hidden');
        }
    }

    // 商品を表示
    function renderProducts(items) {
        if (!items || items.length === 0) {
            resultsEl.innerHTML = '<p class="no-results">商品が見つかりませんでした</p>';
            return;
        }

        resultsEl.innerHTML = items.map(product => createProductCard(product)).join('');
    }

    // 画像URLを取得（ホビステはプロキシ経由）
    function getImageUrl(imageUrl) {
        if (!imageUrl) return null;
        if (imageUrl.includes('hobbystation-single.jp')) {
            return `/api/image-proxy?url=${encodeURIComponent(imageUrl)}`;
        }
        return imageUrl;
    }

    // 商品カードHTML生成
    function createProductCard(product) {
        const siteClass = getSiteClass(product.site);
        const stockClass = product.stock > 0 ? 'in-stock' : 'out-of-stock';
        const proxyImageUrl = getImageUrl(product.image_url);
        const imageHtml = proxyImageUrl
            ? `<img src="${escapeHtml(proxyImageUrl)}" alt="${escapeHtml(product.name)}" class="product-image" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="product-image-placeholder" style="display:none"></div>`
            : '<div class="product-image-placeholder"></div>';

        const redirectUrl = buildRedirectUrl(product.url, product.site, product.name);

        // お気に入りボタン（ログイン時のみ、card_idがある場合のみ）
        let favoriteBtn = '';
        if (typeof Auth !== 'undefined' && Auth.isLoggedIn() && product.card_id) {
            const isFav = favoriteCardIds.includes(product.card_id);
            favoriteBtn = `
                <button class="favorite-btn ${isFav ? 'active' : ''}"
                        onclick="toggleFavorite(${product.card_id}, this)"
                        title="${isFav ? 'お気に入りから削除' : 'お気に入りに追加'}">
                    ${isFav ? '&#9733;' : '&#9734;'}
                </button>
            `;
        }

        // カード詳細ページへのリンク
        const cardDetailUrl = product.card_id ? `/card/${product.card_id}` : null;

        return `
            <div class="product-card">
                ${imageHtml}
                <a href="${redirectUrl}" target="_blank" rel="noopener" class="site-badge ${siteClass}">${escapeHtml(product.site)}</a>
                <div class="product-name">
                    ${cardDetailUrl
                        ? `<a href="${cardDetailUrl}">${escapeHtml(product.name)}</a>`
                        : escapeHtml(product.name)
                    }
                </div>
                <div class="product-price-stock">
                    <div class="product-price">${escapeHtml(product.price_text)}</div>
                    <span class="product-stock ${stockClass}">${escapeHtml(product.stock_text)}</span>
                </div>
                ${favoriteBtn}
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
        if (siteName.includes('ドラスタ')) return 'dorasuta';
        return '';
    }

    // HTMLエスケープ
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // エラー表示
    function showError(message) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    }

    // ページネーション描画
    function renderPagination(currentPage, totalPages, totalCount) {
        if (totalPages <= 1) {
            paginationEl.classList.add('hidden');
            return;
        }

        paginationEl.classList.remove('hidden');
        let html = '';

        // 前へボタン
        if (currentPage > 1) {
            html += `<button class="pagination-btn" onclick="goToPage(${currentPage - 1})">前へ</button>`;
        } else {
            html += `<button class="pagination-btn disabled" disabled>前へ</button>`;
        }

        // ページ番号
        const maxButtons = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);

        if (endPage - startPage < maxButtons - 1) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        if (startPage > 1) {
            html += `<button class="pagination-btn" onclick="goToPage(1)">1</button>`;
            if (startPage > 2) {
                html += `<span class="pagination-ellipsis">...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            if (i === currentPage) {
                html += `<button class="pagination-btn active">${i}</button>`;
            } else {
                html += `<button class="pagination-btn" onclick="goToPage(${i})">${i}</button>`;
            }
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                html += `<span class="pagination-ellipsis">...</span>`;
            }
            html += `<button class="pagination-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
        }

        // 次へボタン
        if (currentPage < totalPages) {
            html += `<button class="pagination-btn" onclick="goToPage(${currentPage + 1})">次へ</button>`;
        } else {
            html += `<button class="pagination-btn disabled" disabled>次へ</button>`;
        }

        paginationEl.innerHTML = html;
    }

    // ページ移動（グローバル関数）
    window.goToPage = function(page) {
        currentSearchState.page = page;
        search(true);
        // ページトップにスクロール
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // お気に入り切り替え（グローバル関数）
    window.toggleFavorite = async function(cardId, btnEl) {
        if (typeof Favorites === 'undefined') return;

        try {
            const isFav = favoriteCardIds.includes(cardId);
            if (isFav) {
                await Favorites.remove(cardId);
                favoriteCardIds = favoriteCardIds.filter(id => id !== cardId);
                btnEl.classList.remove('active');
                btnEl.innerHTML = '&#9734;';
                btnEl.title = 'お気に入りに追加';
            } else {
                await Favorites.add(cardId);
                favoriteCardIds.push(cardId);
                btnEl.classList.add('active');
                btnEl.innerHTML = '&#9733;';
                btnEl.title = 'お気に入りから削除';
            }
        } catch (e) {
            alert(e.message);
        }
    };

    // イベントリスナー
    searchBtn.addEventListener('click', () => {
        currentSearchState.page = 1;
        search(true);
    });

    keywordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            currentSearchState.page = 1;
            search(true);
        }
    });

    // ソート・フィルター変更時
    sortSelect.addEventListener('change', () => {
        currentSearchState.page = 1;
        currentSearchState.sort = sortSelect.value;
        search(true);
    });

    stockFilter.addEventListener('change', () => {
        currentSearchState.page = 1;
        currentSearchState.stock = stockFilter.value;
        search(true);
    });

    // ブラウザの戻る・進むボタン対応
    window.addEventListener('popstate', (e) => {
        if (e.state) {
            currentSearchState = e.state;
            keywordInput.value = currentSearchState.keyword;
            sortSelect.value = currentSearchState.sort;
            stockFilter.value = currentSearchState.stock;
            search(false);
        }
    });

    // Amazon アフィリエイトセクションを表示
    async function showAmazonSection(keyword) {
        const section = document.getElementById('amazon-section');
        const productsEl = document.getElementById('amazon-products');
        const linksEl = document.getElementById('amazon-links');
        if (!section || !linksEl || !keyword) return;

        const affiliateId = 'bsprice-22';

        // APIから商品を取得
        try {
            const response = await fetch('/api/amazon-products');
            if (response.ok) {
                const data = await response.json();
                let products = data.products || [];

                // ランダムで3個選択
                if (products.length > 3) {
                    products = products.sort(() => Math.random() - 0.5).slice(0, 3);
                }

                if (products.length > 0) {
                    productsEl.innerHTML = products.map(product => `
                        <a href="${escapeHtml(product.affiliate_url)}" target="_blank" rel="noopener" class="amazon-product">
                            <img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" class="amazon-product-img">
                            <div class="amazon-product-info">
                                <div class="amazon-product-name">${escapeHtml(product.name)}</div>
                                <div class="amazon-product-price">${product.price_text} <span class="amazon-product-note">(税込)</span></div>
                            </div>
                        </a>
                    `).join('');
                }
            }
        } catch (e) {
            console.error('Amazon商品の取得に失敗:', e);
        }

        // 検索キーワードに基づいたリンクを生成
        const links = [
            { label: `「${keyword}」を検索`, query: `バトルスピリッツ ${keyword}` },
            { label: 'ブースターパック', query: 'バトルスピリッツ ブースターパック' },
            { label: 'スリーブ', query: 'バトルスピリッツ スリーブ' },
            { label: 'デッキケース', query: 'トレカ デッキケース' },
        ];

        linksEl.innerHTML = links.map(link => {
            const url = `https://www.amazon.co.jp/s?k=${encodeURIComponent(link.query)}&tag=${affiliateId}`;
            return `<a href="${url}" target="_blank" rel="noopener" class="amazon-link">${escapeHtml(link.label)}</a>`;
        }).join('');

        section.classList.remove('hidden');
    }

    // 楽天アフィリエイトセクションを表示
    async function showRakutenSection(keyword) {
        const section = document.getElementById('rakuten-section');
        const productsEl = document.getElementById('rakuten-products');
        const linksEl = document.getElementById('rakuten-links');
        if (!section || !linksEl || !keyword) return;

        const affiliateId = '507d6316.932e0e43.507d6317.e71fdd26';

        // APIから商品を取得
        try {
            const response = await fetch('/api/rakuten-products');
            if (response.ok) {
                const data = await response.json();
                let products = data.products || [];

                // ランダムで3個選択
                if (products.length > 3) {
                    products = products.sort(() => Math.random() - 0.5).slice(0, 3);
                }

                if (products.length > 0) {
                    productsEl.innerHTML = products.map(product => `
                        <a href="${escapeHtml(product.affiliate_url)}" target="_blank" rel="noopener sponsored" class="rakuten-product">
                            <img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" class="rakuten-product-img">
                            <div class="rakuten-product-info">
                                <div class="rakuten-product-name">${escapeHtml(product.name)}</div>
                                <div class="rakuten-product-price">${product.price_text} <span class="rakuten-product-note">(税込)</span></div>
                            </div>
                        </a>
                    `).join('');
                }
            }
        } catch (e) {
            console.error('楽天商品の取得に失敗:', e);
        }

        // 検索キーワードに基づいたリンクを生成
        const links = [
            { label: `「${keyword}」を検索`, query: `バトルスピリッツ ${keyword}` },
            { label: 'ブースターパック', query: 'バトルスピリッツ ブースターパック' },
            { label: 'スリーブ', query: 'バトルスピリッツ スリーブ' },
        ];

        linksEl.innerHTML = links.map(link => {
            const url = `https://hb.afl.rakuten.co.jp/hgc/${affiliateId}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F${encodeURIComponent(link.query)}%2F`;
            return `<a href="${url}" target="_blank" rel="noopener sponsored" class="rakuten-link">${escapeHtml(link.label)}</a>`;
        }).join('');

        section.classList.remove('hidden');
    }

    // 初期化
    loadFavoriteIds();
    initFromURL();
});
