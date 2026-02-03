#!/usr/bin/env python3
"""admin.htmlにAmazon商品編集機能を追加"""
import re

# ファイル読み込み
with open('/home/ubuntu/project/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 編集ボタンを追加（削除ボタンの前に）
old_delete_btn = '<button class="keyword-btn delete-btn" onclick="deleteAmazonProduct(${product.id})">'
new_btns = '''<button class="keyword-btn" onclick="editAmazonProduct(${product.id})" style="background:#2196F3">編集</button>
                        <button class="keyword-btn delete-btn" onclick="deleteAmazonProduct(${product.id})">'''

content = content.replace(old_delete_btn, new_btns)

# 2. editAmazonProduct関数を追加（deleteAmazonProduct関数の前に）
edit_function = '''
        // Amazon商品を編集
        async function editAmazonProduct(productId) {
            const item = document.querySelector(`.amazon-item[data-id="${productId}"]`);
            if (!item) return;

            const nameEl = item.querySelector('.amazon-item-name');
            const priceEl = item.querySelector('.amazon-item-price');
            const imgEl = item.querySelector('.amazon-item-img');

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

        // Amazon商品を削除'''

content = content.replace('// Amazon商品を削除', edit_function)

# ファイル書き込み
with open('/home/ubuntu/project/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("admin.html を更新しました")
