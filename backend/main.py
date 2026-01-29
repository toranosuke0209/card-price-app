"""
カード価格比較API

変更履歴:
- 2026/01/27: 検索キーワード自動追加機能
- 2026/01/27: リダイレクトAPI追加（クリック計測）
- 2026/01/27: DB参照方式に変更（スクレイピング廃止）
- 旧実装は main_old.py に保存
"""
import secrets
from pathlib import Path
from urllib.parse import unquote
from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel
import httpx
from typing import Optional

# キーワードファイルのパス
KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"


def add_keyword_if_new(keyword: str) -> bool:
    """
    キーワードがkeywords.txtになければ追加する

    Returns:
        True: 追加した, False: 既に存在
    """
    keyword = keyword.strip()
    if not keyword or len(keyword) < 3:
        return False

    # 既存キーワードを読み込み
    existing = set()
    if KEYWORDS_FILE.exists():
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line.lower())

    # 既に存在する場合は追加しない
    if keyword.lower() in existing:
        return False

    # 新しいキーワードを追加
    with open(KEYWORDS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{keyword}")

    return True

from database import (
    init_database,
    init_shops,
    migrate_v2,
    migrate_v3_auth,
    migrate_v4_featured_keywords,
    get_all_shops,
    get_shop_by_name,
    get_latest_prices_by_keyword,
    get_recently_updated,
    get_price_increased_cards,
    get_price_decreased_cards,
    get_hot_cards,
    get_database_stats,
    search_cards,
    record_search,
    record_click,
    add_to_fetch_queue,
    get_recent_batch_logs,
    # 認証関連
    create_user,
    get_user_by_username,
    get_user_by_email,
    # お気に入り関連
    add_favorite,
    remove_favorite,
    get_user_favorites,
    get_user_favorite_ids,
    # 管理者関連
    create_admin_invite,
    get_admin_invite,
    use_admin_invite,
    get_all_admin_invites,
    get_admin_stats,
    get_card_by_id,
    get_or_create_card_v2,
    update_popular_cards,
    # 人気キーワード関連
    get_featured_keywords,
    add_featured_keyword,
    update_featured_keyword,
    delete_featured_keyword,
    reorder_featured_keywords,
)

from auth import (
    get_password_hash,
    create_access_token,
    authenticate_user,
    get_current_user,
    get_current_user_required,
    require_admin,
    UserCreate,
    AdminRegister,
    UserLogin,
    Token,
)
from models import User

app = FastAPI(title="カード価格比較API")

# フロントエンドの静的ファイルを配信
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.on_event("startup")
async def startup():
    """アプリ起動時にDB初期化"""
    init_database()
    migrate_v2()  # v2マイグレーション実行
    migrate_v3_auth()  # v3認証マイグレーション実行
    migrate_v4_featured_keywords()  # v4人気キーワードマイグレーション実行
    init_shops()


@app.get("/")
async def root():
    """フロントエンドのindex.htmlを返す"""
    return FileResponse(frontend_path / "index.html")


@app.get("/login")
async def login_page():
    """ログインページを返す"""
    return FileResponse(frontend_path / "login.html")


@app.get("/admin")
async def admin_page():
    """管理者ページを返す"""
    return FileResponse(frontend_path / "admin.html")


@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(..., description="画像URL")):
    """
    外部サイトの画像をプロキシして返す
    ホットリンク対策されているサイト（ホビステなど）の画像を表示するため
    """
    # 許可するドメインのみプロキシ
    allowed_domains = [
        "hobbystation-single.jp",
        "www.hobbystation-single.jp",
    ]

    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc not in allowed_domains:
        raise HTTPException(status_code=400, detail="Domain not allowed")

    # リファラーを付けて画像を取得
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Referer": f"https://{parsed.netloc}/"},
                timeout=10.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Image not found")

            content_type = response.headers.get("content-type", "image/jpeg")
            return Response(content=response.content, media_type=content_type)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Failed to fetch image")


@app.get("/api/search")
async def search(keyword: str = Query(..., min_length=1, description="検索キーワード")):
    """
    キーワードで商品を検索（DB参照）

    - keyword: 検索キーワード（必須）

    レスポンス形式は旧API互換を維持
    """
    # DBから最新価格を取得
    prices = get_latest_prices_by_keyword(keyword, limit=200)

    # 検索ログを記録
    record_search(keyword, len(prices))

    # 結果が少なければキーワードを自動追加（次回バッチで取得される）
    if len(prices) < 5:
        add_keyword_if_new(keyword)
        # キューにも追加（batch_queue.pyで処理される）
        add_to_fetch_queue(keyword, source='search', priority=0)

    # サイト別にグループ化（旧API互換形式）
    site_items = {}
    for price in prices:
        site_name = price.shop_name
        if site_name not in site_items:
            site_items[site_name] = []
        site_items[site_name].append(price.to_dict())

    # 全ショップのリストを取得（データがないショップも含める）
    all_shops = get_all_shops()
    site_results = []

    for shop in all_shops:
        items = site_items.get(shop.name, [])
        site_results.append({
            "site": shop.name,
            "items": items
        })

    return {
        "keyword": keyword,
        "results": site_results,
        "total_count": len(prices)
    }


@app.get("/api/sites")
async def get_sites():
    """対応サイト一覧を返す（DB参照）"""
    shops = get_all_shops()
    return {
        "sites": [
            {"name": shop.name, "url": shop.url}
            for shop in shops
        ]
    }


@app.get("/api/home")
async def get_home_data():
    """
    ホーム画面用データを取得

    - recently_updated: 最近価格更新されたカード
    - price_up: 値上がりしたカード
    - price_down: 値下がりしたカード
    - hot_cards: よくクリックされているカード
    - stats: DB統計情報
    - batch_logs: 最近のバッチ実行結果
    - featured_keywords: 管理者設定の人気キーワード
    """
    # 最近更新されたカード
    recently_updated = get_recently_updated(limit=10)
    recently_updated_list = [p.to_dict() for p in recently_updated]

    # 値上がりカード
    price_up = get_price_increased_cards(limit=10)

    # 値下がりカード
    price_down = get_price_decreased_cards(limit=10)

    # ホットカード（クリック数）
    hot_cards = get_hot_cards(days=7, limit=10)

    # DB統計
    stats = get_database_stats()

    # 最近のバッチ実行結果（各ショップの最新1件）
    batch_logs = get_recent_batch_logs(per_shop=True)

    # 人気キーワード（管理者設定）
    featured_keywords = get_featured_keywords(active_only=True)
    featured_keywords_list = [kw.to_dict() for kw in featured_keywords]

    return {
        "recently_updated": recently_updated_list,
        "price_up": price_up,
        "price_down": price_down,
        "hot_cards": hot_cards,
        "stats": {
            "total_cards": stats["cards"],
            "total_prices": stats["prices"],
            "last_updated": stats["newest_price"],
        },
        "batch_logs": batch_logs,
        "featured_keywords": featured_keywords_list,
    }


@app.get("/api/redirect")
async def redirect_to_shop(
    url: str = Query(..., description="リダイレクト先URL"),
    site: str = Query(None, description="ショップ名"),
    card: str = Query(None, description="カード名"),
):
    """
    外部ショップへリダイレクト（クリック計測用）

    - url: リダイレクト先の商品ページURL（必須）
    - site: ショップ名（オプション、計測用）
    - card: カード名（オプション、計測用）

    将来的にアフィリエイトURLへの変換もここで行う
    """
    # クリック記録
    card_id = None
    shop_id = None

    if site:
        shop = get_shop_by_name(site)
        if shop:
            shop_id = shop.id

    if card:
        cards = search_cards(card)
        if cards:
            # 完全一致を優先、なければ最初の結果
            for c in cards:
                if c.name == card:
                    card_id = c.id
                    break
            if card_id is None and cards:
                card_id = cards[0].id

    # クリックをDBに記録
    if shop_id or card_id:
        record_click(card_id=card_id, shop_id=shop_id)

    # URLをデコードしてリダイレクト
    decoded_url = unquote(url)

    # 将来のアフィリエイト対応用フック
    # affiliate_url = convert_to_affiliate(decoded_url, site)

    return RedirectResponse(url=decoded_url, status_code=302)


# =============================================================================
# 認証API
# =============================================================================

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    """
    ユーザー登録
    """
    # バリデーション
    if len(user_data.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザー名は3文字以上である必要があります"
        )
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="パスワードは6文字以上である必要があります"
        )
    if "@" not in user_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有効なメールアドレスを入力してください"
        )

    # 重複チェック
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名は既に使用されています"
        )
    if get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このメールアドレスは既に使用されています"
        )

    # ユーザー作成
    password_hash = get_password_hash(user_data.password)
    user = create_user(
        username=user_data.username,
        email=user_data.email,
        password_hash=password_hash,
        role='user'
    )

    # トークン発行
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
async def login(login_data: UserLogin):
    """
    ログイン（JWT発行）
    """
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user_required)):
    """
    現在のユーザー情報を取得
    """
    return current_user.to_dict()


@app.post("/api/auth/admin-register", response_model=Token)
async def admin_register(admin_data: AdminRegister):
    """
    管理者登録（招待コード必須）
    """
    # バリデーション
    if len(admin_data.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザー名は3文字以上である必要があります"
        )
    if len(admin_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="パスワードは6文字以上である必要があります"
        )

    # 招待コードチェック
    invite = get_admin_invite(admin_data.invite_code)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無効な招待コードです"
        )
    if invite.used_by is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="この招待コードは既に使用されています"
        )

    # 重複チェック
    if get_user_by_username(admin_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名は既に使用されています"
        )
    if get_user_by_email(admin_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このメールアドレスは既に使用されています"
        )

    # 管理者ユーザー作成
    password_hash = get_password_hash(admin_data.password)
    user = create_user(
        username=admin_data.username,
        email=admin_data.email,
        password_hash=password_hash,
        role='admin'
    )

    # 招待コードを使用済みに
    use_admin_invite(admin_data.invite_code, user.id)

    # トークン発行
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}


# =============================================================================
# お気に入りAPI
# =============================================================================

class FavoriteRequest(BaseModel):
    card_id: int


@app.get("/api/favorites")
async def get_favorites(current_user: User = Depends(get_current_user_required)):
    """
    お気に入り一覧を取得
    """
    favorites = get_user_favorites(current_user.id)
    return {"favorites": favorites}


@app.get("/api/favorites/ids")
async def get_favorite_ids(current_user: User = Depends(get_current_user_required)):
    """
    お気に入りカードIDリストを取得（軽量API）
    """
    ids = get_user_favorite_ids(current_user.id)
    return {"card_ids": ids}


@app.post("/api/favorites")
async def add_favorite_card(
    request: FavoriteRequest,
    current_user: User = Depends(get_current_user_required)
):
    """
    お気に入りに追加
    """
    # カード存在チェック
    card = get_card_by_id(request.card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カードが見つかりません"
        )

    favorite = add_favorite(current_user.id, request.card_id)
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="既にお気に入りに登録されています"
        )

    return {"message": "お気に入りに追加しました", "card_id": request.card_id}


@app.delete("/api/favorites/{card_id}")
async def remove_favorite_card(
    card_id: int,
    current_user: User = Depends(get_current_user_required)
):
    """
    お気に入りから削除
    """
    success = remove_favorite(current_user.id, card_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="お気に入りに登録されていません"
        )

    return {"message": "お気に入りから削除しました", "card_id": card_id}


# =============================================================================
# 管理者API
# =============================================================================

class CardCreate(BaseModel):
    name: str
    card_no: Optional[str] = None


@app.get("/api/admin/stats")
async def get_admin_statistics(admin_user: User = Depends(require_admin)):
    """
    管理者用統計情報を取得
    """
    stats = get_admin_stats()
    return {"stats": stats}


@app.post("/api/admin/cards")
async def create_card(
    card_data: CardCreate,
    admin_user: User = Depends(require_admin)
):
    """
    カードを手動登録
    """
    if len(card_data.name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="カード名は2文字以上である必要があります"
        )

    card = get_or_create_card_v2(
        name=card_data.name,
        card_no=card_data.card_no
    )
    return {"message": "カードを登録しました", "card": card.to_dict()}


@app.post("/api/admin/cards/{card_id}/popular")
async def toggle_popular(
    card_id: int,
    admin_user: User = Depends(require_admin)
):
    """
    人気カードフラグを切り替え
    """
    from database import get_connection
    card = get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="カードが見つかりません"
        )

    new_status = 0 if card.is_popular else 1
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cards SET is_popular = ? WHERE id = ?",
            (new_status, card_id)
        )
        conn.commit()

    return {
        "message": "人気カードを更新しました",
        "card_id": card_id,
        "is_popular": new_status
    }


@app.post("/api/admin/invites")
async def create_invite(admin_user: User = Depends(require_admin)):
    """
    招待コードを生成
    """
    code = secrets.token_urlsafe(16)
    invite = create_admin_invite(code, admin_user.id)
    return {"message": "招待コードを生成しました", "invite": invite.to_dict()}


@app.get("/api/admin/invites")
async def list_invites(admin_user: User = Depends(require_admin)):
    """
    招待コード一覧を取得
    """
    invites = get_all_admin_invites()
    return {"invites": [inv.to_dict() for inv in invites]}


@app.post("/api/admin/update-popular")
async def run_update_popular(admin_user: User = Depends(require_admin)):
    """
    人気カードフラグを自動更新
    """
    updated = update_popular_cards()
    return {"message": f"{updated}件のカードを人気カードに更新しました"}


# =============================================================================
# 人気キーワード管理API
# =============================================================================

class FeaturedKeywordCreate(BaseModel):
    keyword: str


class FeaturedKeywordUpdate(BaseModel):
    keyword: Optional[str] = None
    is_active: Optional[int] = None


class FeaturedKeywordReorder(BaseModel):
    keyword_ids: list[int]


@app.get("/api/admin/featured-keywords")
async def list_featured_keywords(admin_user: User = Depends(require_admin)):
    """
    人気キーワード一覧を取得（管理者用、非アクティブも含む）
    """
    keywords = get_featured_keywords(active_only=False)
    return {"keywords": [kw.to_dict() for kw in keywords]}


@app.post("/api/admin/featured-keywords")
async def create_featured_keyword(
    data: FeaturedKeywordCreate,
    admin_user: User = Depends(require_admin)
):
    """
    人気キーワードを追加
    """
    if not data.keyword or len(data.keyword.strip()) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="キーワードを入力してください"
        )

    keyword = add_featured_keyword(data.keyword.strip(), admin_user.id)
    return {"message": "キーワードを追加しました", "keyword": keyword.to_dict()}


@app.put("/api/admin/featured-keywords/{keyword_id}")
async def update_featured_keyword_api(
    keyword_id: int,
    data: FeaturedKeywordUpdate,
    admin_user: User = Depends(require_admin)
):
    """
    人気キーワードを更新
    """
    keyword = update_featured_keyword(
        keyword_id,
        keyword=data.keyword,
        is_active=data.is_active
    )
    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="キーワードが見つかりません"
        )

    return {"message": "キーワードを更新しました", "keyword": keyword.to_dict()}


@app.delete("/api/admin/featured-keywords/{keyword_id}")
async def delete_featured_keyword_api(
    keyword_id: int,
    admin_user: User = Depends(require_admin)
):
    """
    人気キーワードを削除
    """
    success = delete_featured_keyword(keyword_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="キーワードが見つかりません"
        )

    return {"message": "キーワードを削除しました"}


@app.post("/api/admin/featured-keywords/reorder")
async def reorder_featured_keywords_api(
    data: FeaturedKeywordReorder,
    admin_user: User = Depends(require_admin)
):
    """
    人気キーワードの表示順を変更
    """
    reorder_featured_keywords(data.keyword_ids)
    return {"message": "表示順を更新しました"}


@app.post("/api/admin/featured-keywords/{keyword_id}/update-prices")
async def update_keyword_prices_api(
    keyword_id: int,
    admin_user: User = Depends(require_admin)
):
    """
    指定キーワードの価格を即座に更新
    """
    from update_featured_prices import update_single_keyword

    # キーワードを取得
    keywords = get_featured_keywords(active_only=False)
    keyword = next((k for k in keywords if k.id == keyword_id), None)

    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="キーワードが見つかりません"
        )

    # 価格更新実行
    try:
        stats = update_single_keyword(keyword.keyword)
        return {
            "message": f"「{keyword.keyword}」の価格を更新しました",
            "stats": {
                "total": stats["total"],
                "new": stats["new"],
                "shops": stats["shops"]
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"価格更新に失敗しました: {str(e)}"
        )


@app.post("/api/admin/featured-keywords/update-all-prices")
async def update_all_keyword_prices_api(
    admin_user: User = Depends(require_admin)
):
    """
    全ての人気キーワードの価格を更新
    """
    from update_featured_prices import update_all_featured_keywords

    try:
        stats = update_all_featured_keywords()
        return {
            "message": "全キーワードの価格を更新しました",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"価格更新に失敗しました: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
