

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
