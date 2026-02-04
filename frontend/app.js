/**
 * ホームページ用JavaScript
 * ホーム画面のデータ表示のみを担当
 */
document.addEventListener('DOMContentLoaded', () => {
    // ホーム画面データを読み込み
    loadHomeData();

    // フォーム送信時の空チェック
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            const keyword = document.getElementById('keyword').value.trim();
            if (!keyword) {
                e.preventDefault();
                alert('検索キーワードを入力してください');
            }
        });
    }

    // HTMLエスケープ
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        // 人気キーワード
        renderFeaturedKeywords(data.featured_keywords);

        // 統計情報
        const statsEl = document.getElementById('home-stats');
        if (statsEl && data.stats) {
            statsEl.innerHTML = `
                <span>登録カード: <strong>${data.stats.total_cards.toLocaleString()}</strong>件</span>
                <span>価格データ: <strong>${data.stats.total_prices.toLocaleString()}</strong>件</span>
                ${data.stats.last_updated ? `<span>最終更新: <strong>${formatDate(data.stats.last_updated)}</strong></span>` : ''}
            `;
        }

        // 最近更新
        renderHomeList('recently-updated', data.recently_updated, (item) => `
            <a href="/search?q=${encodeURIComponent(item.name)}" class="home-item">
                <span class="home-item-name">${escapeHtml(truncate(item.name, 25))}</span>
                <span class="home-item-price">${escapeHtml(item.price_text)}</span>
                <span class="home-item-shop">${escapeHtml(item.site)}</span>
            </a>
        `);

        // 値上がり
        renderHomeList('price-up', data.price_up, (item) => `
            <a href="/search?q=${encodeURIComponent(item.card_name)}" class="home-item">
                <span class="home-item-name">${escapeHtml(truncate(item.card_name, 20))}</span>
                <span class="home-item-diff up">+${item.diff.toLocaleString()}円</span>
                <span class="home-item-shop">${escapeHtml(item.shop_name)}</span>
            </a>
        `);

        // 値下がり
        renderHomeList('price-down', data.price_down, (item) => `
            <a href="/search?q=${encodeURIComponent(item.card_name)}" class="home-item">
                <span class="home-item-name">${escapeHtml(truncate(item.card_name, 20))}</span>
                <span class="home-item-diff down">-${item.diff.toLocaleString()}円</span>
                <span class="home-item-shop">${escapeHtml(item.shop_name)}</span>
            </a>
        `);

        // 注目カード
        renderHomeList('hot-cards', data.hot_cards, (item) => `
            <a href="/search?q=${encodeURIComponent(item.card_name)}" class="home-item">
                <span class="home-item-name">${escapeHtml(truncate(item.card_name, 25))}</span>
                <span class="home-item-clicks">${item.click_count} clicks</span>
            </a>
        `);
    }

    // 人気キーワードを描画
    function renderFeaturedKeywords(keywords) {
        const el = document.getElementById('featured-keywords');
        if (!el) return;

        if (!keywords || keywords.length === 0) {
            el.classList.add('hidden');
            return;
        }

        el.classList.remove('hidden');
        el.innerHTML = `
            <div class="featured-keywords-label">人気のキーワード:</div>
            <div class="featured-keywords-list">
                ${keywords.map(kw => `
                    <a href="/search?q=${encodeURIComponent(kw.keyword)}" class="featured-keyword-tag">
                        ${escapeHtml(kw.keyword)}
                    </a>
                `).join('')}
            </div>
        `;
    }

    // バッチ実行通知を描画（管理者のみ）
    function renderBatchNotification(batchLogs) {
        const notificationEl = document.getElementById('batch-notification');
        if (!notificationEl) return;

        // 管理者以外には表示しない
        if (!Auth.isAdmin()) {
            notificationEl.classList.add('hidden');
            return;
        }

        // 最新の成功ログを取得（24時間以内）
        if (!batchLogs || batchLogs.length === 0) {
            notificationEl.classList.add('hidden');
            return;
        }

        // 48時間以内のログのみ表示（巡回は1日1回のため）
        const now = new Date();
        const recentLogs = batchLogs.filter(log => {
            const logDate = new Date(log.finished_at);
            const diffHours = (now - logDate) / (1000 * 60 * 60);
            return diffHours < 48 && log.status === 'success';
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
                timeZone: 'Asia/Tokyo',
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

    // 日付フォーマット（UTCをJSTに変換）
    function formatDate(dateStr) {
        if (!dateStr) return '';
        // UTCとして解釈するためにZを追加
        let utcStr = dateStr;
        if (!dateStr.endsWith('Z') && !dateStr.includes('+')) {
            utcStr = dateStr.replace(' ', 'T') + 'Z';
        }
        const date = new Date(utcStr);
        return date.toLocaleString('ja-JP', {
            timeZone: 'Asia/Tokyo',
            month: 'numeric',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
});
