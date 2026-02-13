#!/usr/bin/env python3
"""
Amazon商品更新機能を追加するパッチスクリプト

以下のファイルに追記が必要:
1. database.py - update_amazon_product関数
2. main.py - AmazonProductUpdate, PUT endpoint
"""

# database.py に追加するコード
DATABASE_PATCH = '''
def update_amazon_product(product_id: int, **kwargs) -> Optional[AmazonProduct]:
    """Amazon商品を更新"""
    allowed_fields = ['name', 'price', 'image_url', 'is_active']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

    if not updates:
        return get_amazon_product_by_id(product_id)

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [product_id]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE amazon_products
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)
        conn.commit()

    return get_amazon_product_by_id(product_id)


def get_amazon_product_by_id(product_id: int) -> Optional[AmazonProduct]:
    """IDでAmazon商品を取得"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM amazon_products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if row:
            return AmazonProduct(
                id=row[0],
                asin=row[1],
                name=row[2],
                price=row[3],
                image_url=row[4],
                affiliate_url=row[5],
                display_order=row[6],
                is_active=row[7],
                created_at=row[8],
                updated_at=row[9]
            )
    return None
'''

# main.py に追加するコード
MAIN_PATCH = '''
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
    from database import update_amazon_product, get_amazon_product_by_id

    product = get_amazon_product_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品が見つかりません"
        )

    updated = update_amazon_product(
        product_id,
        name=data.name,
        price=data.price,
        image_url=data.image_url,
        is_active=data.is_active
    )
    return {"message": "商品を更新しました", "product": updated.to_dict()}
'''

print("=== database.py に追加するコード ===")
print(DATABASE_PATCH)
print("\n=== main.py に追加するコード ===")
print(MAIN_PATCH)
