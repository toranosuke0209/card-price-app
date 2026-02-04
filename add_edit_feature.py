#!/usr/bin/env python3
"""Amazon商品編集機能を追加するスクリプト"""

# 1. database.py に追加
db_code = '''

def get_amazon_product_by_id(product_id: int):
    """IDでAmazon商品を取得"""
    from models import AmazonProduct
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM amazon_products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if row:
            return AmazonProduct(
                id=row[0], asin=row[1], name=row[2], price=row[3],
                image_url=row[4], affiliate_url=row[5], display_order=row[6],
                is_active=row[7], created_at=row[8], updated_at=row[9]
            )
    return None


def update_amazon_product(product_id: int, **kwargs):
    """Amazon商品を更新"""
    allowed = ["name", "price", "image_url", "is_active"]
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return get_amazon_product_by_id(product_id)
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [product_id]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE amazon_products SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        conn.commit()
    return get_amazon_product_by_id(product_id)
'''

with open('/home/ubuntu/project/backend/database.py', 'a') as f:
    f.write(db_code)
print("database.py updated")

# 2. main.py に追加
main_code = '''

# === Amazon商品更新API ===
from database import update_amazon_product, get_amazon_product_by_id

class AmazonProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[int] = None


@app.put("/api/admin/amazon-products/{product_id}")
async def update_amazon_product_api(
    product_id: int,
    data: AmazonProductUpdate,
    admin_user: User = Depends(require_admin)
):
    """Amazon商品を更新"""
    product = get_amazon_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品が見つかりません")
    updated = update_amazon_product(
        product_id, name=data.name, price=data.price,
        image_url=data.image_url, is_active=data.is_active
    )
    return {"message": "商品を更新しました", "product": updated.to_dict()}
'''

with open('/home/ubuntu/project/backend/main.py', 'a') as f:
    f.write(main_code)
print("main.py updated")

# 3. admin.html を更新
with open('/home/ubuntu/project/frontend/admin.html', 'r') as f:
    html = f.read()

# 編集ボタンを追加
old_delete = '<button class="keyword-btn delete-btn" onclick="deleteAmazonProduct(${product.id})">'
new_btns = '<button class="keyword-btn" onclick="editAmazonProduct(${product.id})" style="background:#2196F3">編集</button>\n                        <button class="keyword-btn delete-btn" onclick="deleteAmazonProduct(${product.id})">'
html = html.replace(old_delete, new_btns)

# 編集関数を追加
edit_func = '''
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

html = html.replace('// Amazon商品を削除', edit_func)

with open('/home/ubuntu/project/frontend/admin.html', 'w') as f:
    f.write(html)
print("admin.html updated")

print("\n完了！サーバーを再起動してください。")
