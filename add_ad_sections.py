#!/usr/bin/env python3
"""admin.htmlにAmazon/楽天商品管理セクションを追加"""

with open('/home/ubuntu/project/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 招待コード管理セクションの後に広告管理セクションを追加
ad_sections = '''
            <!-- Amazon商品管理 -->
            <div class="admin-section">
                <h2>Amazon商品管理</h2>
                <p class="section-desc">検索結果に表示するAmazonアフィリエイト商品を管理します。</p>
                <form id="amazon-form" class="admin-form" onsubmit="handleAddAmazonProduct(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="amazon-url">Amazon URL</label>
                            <input type="url" id="amazon-url" required placeholder="https://www.amazon.co.jp/dp/...">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="amazon-name">商品名</label>
                            <input type="text" id="amazon-name" required placeholder="商品名を入力">
                        </div>
                        <div class="form-group">
                            <label for="amazon-price">価格（税込）</label>
                            <input type="number" id="amazon-price" required placeholder="5390">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="amazon-image">画像URL</label>
                        <input type="url" id="amazon-image" required placeholder="https://m.media-amazon.com/...">
                    </div>
                    <div class="form-error" id="amazon-error"></div>
                    <div class="form-success" id="amazon-success"></div>
                    <button type="submit" class="admin-btn">商品を追加</button>
                </form>
                <div class="amazon-product-list" id="amazon-product-list"></div>
            </div>

            <!-- 楽天商品管理 -->
            <div class="admin-section">
                <h2>楽天商品管理</h2>
                <p class="section-desc">検索結果に表示する楽天アフィリエイト商品を管理します。</p>
                <form id="rakuten-form" class="admin-form" onsubmit="handleAddRakutenProduct(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="rakuten-name">商品名</label>
                            <input type="text" id="rakuten-name" required placeholder="商品名を入力">
                        </div>
                        <div class="form-group">
                            <label for="rakuten-price">価格（税込）</label>
                            <input type="number" id="rakuten-price" required placeholder="5390">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="rakuten-image">画像URL</label>
                        <input type="url" id="rakuten-image" required placeholder="https://thumbnail.image.rakuten.co.jp/...">
                    </div>
                    <div class="form-group">
                        <label for="rakuten-affiliate">アフィリエイトURL</label>
                        <input type="url" id="rakuten-affiliate" required placeholder="https://hb.afl.rakuten.co.jp/...">
                    </div>
                    <div class="form-error" id="rakuten-error"></div>
                    <div class="form-success" id="rakuten-success"></div>
                    <button type="submit" class="admin-btn">商品を追加</button>
                </form>
                <div class="rakuten-product-list" id="rakuten-product-list"></div>
            </div>
'''

# 招待コードセクションの閉じタグの後に挿入
insert_point = '</div>\n                <div class="invite-list" id="invite-list"></div>\n            </div>'
content = content.replace(insert_point, insert_point + ad_sections)

# JavaScriptの関数を追加（loadKeywords();の後に）
js_init = '''loadKeywords();
            loadAmazonProducts();
            loadRakutenProducts();'''
content = content.replace('loadKeywords();', js_init)

# Amazon/楽天の関数をスクリプト末尾に追加
js_functions = '''

        // === Amazon商品管理 ===
        async function loadAmazonProducts() {
            try {
                const response = await Auth.authFetch('/api/admin/amazon-products');
                if (!response.ok) return;
                const data = await response.json();
                renderAmazonProducts(data.products || []);
            } catch (e) {
                console.error('Failed to load Amazon products:', e);
            }
        }

        function renderAmazonProducts(products) {
            const listEl = document.getElementById('amazon-product-list');
            if (!listEl) return;
            if (products.length === 0) {
                listEl.innerHTML = '<p style="color:#888">商品が登録されていません</p>';
                return;
            }
            listEl.innerHTML = products.map((product, index) => `
                <div class="amazon-item ${product.is_active ? '' : 'inactive'}" data-id="${product.id}" style="display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #444;border-radius:8px;margin-bottom:10px;background:${product.is_active ? '#1a1a2e' : '#333'}">
                    <img src="${escapeHtml(product.image_url)}" alt="" style="width:60px;height:60px;object-fit:contain;background:#fff;border-radius:4px" onerror="this.style.display='none'">
                    <div style="flex:1">
                        <div class="amazon-item-name" style="font-weight:bold">${escapeHtml(product.name)}</div>
                        <div class="amazon-item-price" style="color:#f90">${product.price_text}</div>
                    </div>
                    <div style="display:flex;gap:5px">
                        <button class="keyword-btn" onclick="editAmazonProduct(${product.id})" style="background:#2196F3">編集</button>
                        <button class="keyword-btn" onclick="toggleAmazonProduct(${product.id}, ${product.is_active})" style="background:${product.is_active ? '#4CAF50' : '#666'}">${product.is_active ? '表示中' : '非表示'}</button>
                        <button class="keyword-btn" onclick="deleteAmazonProduct(${product.id})" style="background:#f44336">×</button>
                    </div>
                </div>
            `).join('');
        }

        async function handleAddAmazonProduct(event) {
            event.preventDefault();
            const errorEl = document.getElementById('amazon-error');
            const successEl = document.getElementById('amazon-success');
            errorEl.textContent = '';
            successEl.textContent = '';
            const url = document.getElementById('amazon-url').value;
            const name = document.getElementById('amazon-name').value;
            const price = parseInt(document.getElementById('amazon-price').value);
            const imageUrl = document.getElementById('amazon-image').value;
            try {
                const response = await Auth.authFetch('/api/admin/amazon-products', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, name, price, image_url: imageUrl })
                });
                const data = await response.json();
                if (response.ok) {
                    successEl.textContent = '商品を追加しました';
                    document.getElementById('amazon-url').value = '';
                    document.getElementById('amazon-name').value = '';
                    document.getElementById('amazon-price').value = '';
                    document.getElementById('amazon-image').value = '';
                    loadAmazonProducts();
                } else {
                    errorEl.textContent = data.detail || '追加に失敗しました';
                }
            } catch (e) {
                errorEl.textContent = 'エラー: ' + e.message;
            }
        }

        async function editAmazonProduct(productId) {
            const item = document.querySelector(`.amazon-item[data-id="${productId}"]`);
            if (!item) return;
            const nameEl = item.querySelector('.amazon-item-name');
            const priceEl = item.querySelector('.amazon-item-price');
            const imgEl = item.querySelector('img');
            const currentName = nameEl ? nameEl.textContent : '';
            const currentPrice = priceEl ? priceEl.textContent.replace(/[^0-9]/g, '') : '';
            const currentImage = imgEl ? imgEl.src : '';

            const newImageUrl = prompt('画像URLを入力:', currentImage);
            if (newImageUrl === null) return;
            const newName = prompt('商品名:', currentName);
            if (newName === null) return;
            const newPrice = prompt('価格:', currentPrice);
            if (newPrice === null) return;

            try {
                const response = await Auth.authFetch(`/api/admin/amazon-products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: newName || undefined,
                        price: newPrice ? parseInt(newPrice) : undefined,
                        image_url: newImageUrl || undefined
                    })
                });
                if (response.ok) {
                    alert('更新しました');
                    loadAmazonProducts();
                } else {
                    const err = await response.json();
                    alert('エラー: ' + (err.detail || '更新失敗'));
                }
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }

        async function toggleAmazonProduct(productId, currentActive) {
            try {
                const response = await Auth.authFetch(`/api/admin/amazon-products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_active: currentActive ? 0 : 1 })
                });
                if (response.ok) loadAmazonProducts();
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }

        async function deleteAmazonProduct(productId) {
            if (!confirm('この商品を削除しますか？')) return;
            try {
                const response = await Auth.authFetch(`/api/admin/amazon-products/${productId}`, { method: 'DELETE' });
                if (response.ok) loadAmazonProducts();
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }

        // === 楽天商品管理 ===
        async function loadRakutenProducts() {
            try {
                const response = await Auth.authFetch('/api/admin/rakuten-products');
                if (!response.ok) return;
                const data = await response.json();
                renderRakutenProducts(data.products || []);
            } catch (e) {
                console.error('Failed to load Rakuten products:', e);
            }
        }

        function renderRakutenProducts(products) {
            const listEl = document.getElementById('rakuten-product-list');
            if (!listEl) return;
            if (products.length === 0) {
                listEl.innerHTML = '<p style="color:#888">商品が登録されていません</p>';
                return;
            }
            listEl.innerHTML = products.map((product, index) => `
                <div class="rakuten-item ${product.is_active ? '' : 'inactive'}" data-id="${product.id}" style="display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #444;border-radius:8px;margin-bottom:10px;background:${product.is_active ? '#1a1a2e' : '#333'}">
                    <img src="${escapeHtml(product.image_url)}" alt="" style="width:60px;height:60px;object-fit:contain;background:#fff;border-radius:4px" onerror="this.style.display='none'">
                    <div style="flex:1">
                        <div class="rakuten-item-name" style="font-weight:bold">${escapeHtml(product.name)}</div>
                        <div class="rakuten-item-price" style="color:#bf0000">${product.price_text}</div>
                    </div>
                    <div style="display:flex;gap:5px">
                        <button class="keyword-btn" onclick="editRakutenProduct(${product.id})" style="background:#2196F3">編集</button>
                        <button class="keyword-btn" onclick="toggleRakutenProduct(${product.id}, ${product.is_active})" style="background:${product.is_active ? '#4CAF50' : '#666'}">${product.is_active ? '表示中' : '非表示'}</button>
                        <button class="keyword-btn" onclick="deleteRakutenProduct(${product.id})" style="background:#f44336">×</button>
                    </div>
                </div>
            `).join('');
        }

        async function handleAddRakutenProduct(event) {
            event.preventDefault();
            const errorEl = document.getElementById('rakuten-error');
            const successEl = document.getElementById('rakuten-success');
            errorEl.textContent = '';
            successEl.textContent = '';
            const name = document.getElementById('rakuten-name').value;
            const price = parseInt(document.getElementById('rakuten-price').value);
            const imageUrl = document.getElementById('rakuten-image').value;
            const affiliateUrl = document.getElementById('rakuten-affiliate').value;
            try {
                const response = await Auth.authFetch('/api/admin/rakuten-products', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, price, image_url: imageUrl, affiliate_url: affiliateUrl })
                });
                const data = await response.json();
                if (response.ok) {
                    successEl.textContent = '商品を追加しました';
                    document.getElementById('rakuten-name').value = '';
                    document.getElementById('rakuten-price').value = '';
                    document.getElementById('rakuten-image').value = '';
                    document.getElementById('rakuten-affiliate').value = '';
                    loadRakutenProducts();
                } else {
                    errorEl.textContent = data.detail || '追加に失敗しました';
                }
            } catch (e) {
                errorEl.textContent = 'エラー: ' + e.message;
            }
        }

        async function editRakutenProduct(productId) {
            const item = document.querySelector(`.rakuten-item[data-id="${productId}"]`);
            if (!item) return;
            const nameEl = item.querySelector('.rakuten-item-name');
            const priceEl = item.querySelector('.rakuten-item-price');
            const imgEl = item.querySelector('img');
            const currentName = nameEl ? nameEl.textContent : '';
            const currentPrice = priceEl ? priceEl.textContent.replace(/[^0-9]/g, '') : '';
            const currentImage = imgEl ? imgEl.src : '';

            const newImageUrl = prompt('画像URLを入力:', currentImage);
            if (newImageUrl === null) return;
            const newName = prompt('商品名:', currentName);
            if (newName === null) return;
            const newPrice = prompt('価格:', currentPrice);
            if (newPrice === null) return;

            try {
                const response = await Auth.authFetch(`/api/admin/rakuten-products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: newName || undefined,
                        price: newPrice ? parseInt(newPrice) : undefined,
                        image_url: newImageUrl || undefined
                    })
                });
                if (response.ok) {
                    alert('更新しました');
                    loadRakutenProducts();
                } else {
                    const err = await response.json();
                    alert('エラー: ' + (err.detail || '更新失敗'));
                }
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }

        async function toggleRakutenProduct(productId, currentActive) {
            try {
                const response = await Auth.authFetch(`/api/admin/rakuten-products/${productId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_active: currentActive ? 0 : 1 })
                });
                if (response.ok) loadRakutenProducts();
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }

        async function deleteRakutenProduct(productId) {
            if (!confirm('この商品を削除しますか？')) return;
            try {
                const response = await Auth.authFetch(`/api/admin/rakuten-products/${productId}`, { method: 'DELETE' });
                if (response.ok) loadRakutenProducts();
            } catch (e) {
                alert('エラー: ' + e.message);
            }
        }
'''

# </script>の前にJS関数を挿入
content = content.replace('</script>', js_functions + '\n    </script>')

with open('/home/ubuntu/project/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("admin.html updated with Amazon/Rakuten sections")
