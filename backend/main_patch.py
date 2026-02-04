

# === Amazon商品更新API（パッチ追加） ===
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
