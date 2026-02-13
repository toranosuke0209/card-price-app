
// === Amazon商品編集機能 ===
async function editAmazonProduct(productId) {
    const item = document.querySelector(`.amazon-item[data-id="${productId}"]`);
    if (!item) return;

    const name = item.querySelector('.amazon-item-name').textContent;
    const priceText = item.querySelector('.amazon-item-price').textContent;
    const price = parseInt(priceText.replace(/[^0-9]/g, ''));
    const img = item.querySelector('.amazon-item-img');
    const imageUrl = img ? img.src : '';

    const newImageUrl = prompt('画像URLを入力してください:', imageUrl);
    if (newImageUrl === null) return; // キャンセル

    const newName = prompt('商品名を入力してください:', name);
    if (newName === null) return;

    const newPrice = prompt('価格を入力してください:', price);
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
