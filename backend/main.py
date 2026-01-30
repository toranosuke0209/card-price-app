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
    migrate_v5_amazon_products,
    get_connection,
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
    get_card_all_prices,
    get_card_price_history,
    get_unified_card_prices,
    get_related_cards,
    get_card_groups,
    get_group_members,
    add_card_to_group,
    remove_card_from_group,
    delete_card_group,
    migrate_v7_card_groups,
    update_card_numbers,
    get_or_create_card_v2,
    update_popular_cards,
    # 人気キーワード関連
    get_featured_keywords,
    add_featured_keyword,
    update_featured_keyword,
    delete_featured_keyword,
    reorder_featured_keywords,
    # Amazon商品関連
    get_amazon_products,
    get_amazon_product_by_id,
    add_amazon_product,
    update_amazon_product,
    delete_amazon_product,
    reorder_amazon_products,
    # アクセス解析関連
    get_search_stats,
    get_click_stats,
    get_keyword_ranking,
    get_shop_click_ranking,
    get_card_click_ranking,
    # ユーザー管理関連
    get_users_paginated,
    update_user_is_active,
    update_user_role,
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
    migrate_v5_amazon_products()  # v5 Amazon商品マイグレーション実行
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


@app.get("/search")
async def search_page():
    """検索結果ページを返す"""
    return FileResponse(frontend_path / "search.html")


@app.get("/privacy")
async def privacy_page():
    """プライバシーポリシーページを返す"""
    return FileResponse(frontend_path / "privacy.html")


@app.get("/about")
async def about_page():
    """このサイトについてページを返す"""
    return FileResponse(frontend_path / "about.html")


@app.get("/ranking")
async def ranking_page():
    """ランキングページを返す"""
    return FileResponse(frontend_path / "ranking.html")


@app.get("/shops")
async def shops_page():
    """ショップ一覧ページを返す"""
    return FileResponse(frontend_path / "shops.html")


@app.get("/favorites")
async def favorites_page():
    """お気に入りページを返す"""
    return FileResponse(frontend_path / "favorites.html")


@app.get("/card/{card_id}")
async def card_page(card_id: int):
    """カード詳細ページを返す"""
    return FileResponse(frontend_path / "card.html")


@app.get("/robots.txt")
async def robots_txt():
    """robots.txtを返す"""
    return FileResponse(frontend_path / "robots.txt", media_type="text/plain")


@app.get("/ads.txt")
async def ads_txt():
    """ads.txtを返す"""
    return FileResponse(frontend_path / "ads.txt", media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap_xml():
    """sitemap.xmlを返す"""
    return FileResponse(frontend_path / "sitemap.xml", media_type="application/xml")


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
async def search(
    keyword: str = Query(..., min_length=1, description="検索キーワード"),
    page: int = Query(1, ge=1, description="ページ番号"),
    per_page: int = Query(20, ge=1, le=100, description="1ページあたりの件数"),
    sort: str = Query("price-asc", description="ソート順"),
    stock: str = Query("all", description="在庫フィルター")
):
    """
    キーワードで商品を検索（DB参照）

    - keyword: 検索キーワード（必須）
    - page: ページ番号（デフォルト: 1）
    - per_page: 1ページあたりの件数（デフォルト: 20、最大: 100）
    - sort: ソート順（price-asc, price-desc, site）
    - stock: 在庫フィルター（all, in-stock, out-of-stock）
    """
    # DBから最新価格を取得（全件取得してからフィルタ・ソート）
    prices = get_latest_prices_by_keyword(keyword, limit=500)

    # 検索ログを記録（初回ページのみ）
    if page == 1:
        record_search(keyword, len(prices))

        # 結果が少なければキーワードを自動追加（次回バッチで取得される）
        if len(prices) < 5:
            add_keyword_if_new(keyword)
            # キューにも追加（batch_queue.pyで処理される）
            add_to_fetch_queue(keyword, source='search', priority=0)

    # フラット化してリストに変換
    all_items = [price.to_dict() for price in prices]

    # 在庫フィルター
    if stock == "in-stock":
        all_items = [item for item in all_items if item.get("stock", 0) > 0]
    elif stock == "out-of-stock":
        all_items = [item for item in all_items if item.get("stock", 0) == 0]

    # ソート
    if sort == "price-asc":
        all_items.sort(key=lambda x: x.get("price", 0))
    elif sort == "price-desc":
        all_items.sort(key=lambda x: x.get("price", 0), reverse=True)
    elif sort == "site":
        all_items.sort(key=lambda x: x.get("site", ""))

    # 総件数
    total_count = len(all_items)
    total_pages = (total_count + per_page - 1) // per_page

    # ページネーション
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_items[start:end]

    return {
        "keyword": keyword,
        "items": paginated_items,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "sort": sort,
        "stock": stock
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


@app.get("/api/ranking")
async def get_ranking_data():
    """
    ランキングページ用データを取得
    """
    # 人気検索キーワード（過去30日）
    keyword_ranking = get_keyword_ranking(days=30, limit=30)

    # 人気カード（クリック数、過去30日）
    hot_cards = get_hot_cards(days=30, limit=30)

    # 値上がりカード
    price_up = get_price_increased_cards(limit=30)

    # 値下がりカード
    price_down = get_price_decreased_cards(limit=30)

    return {
        "keyword_ranking": keyword_ranking,
        "hot_cards": hot_cards,
        "price_up": price_up,
        "price_down": price_down,
    }


@app.get("/api/shops")
async def get_shops_data():
    """
    ショップ一覧ページ用データを取得
    """
    shops = get_all_shops(active_only=True)

    # ショップ情報に追加データを付与
    shop_list = []
    for shop in shops:
        shop_dict = shop.to_dict()
        # ショップごとの価格データ数を取得
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM prices WHERE shop_id = ?",
                (shop.id,)
            )
            shop_dict["price_count"] = cursor.fetchone()[0]
        shop_list.append(shop_dict)

    return {"shops": shop_list}


@app.get("/api/card/{card_id}")
async def get_card_detail(card_id: int):
    """
    カード詳細情報を取得（カード詳細ページ用）
    - 同じカード番号を持つカードの価格を統合
    - リバイバル/旧版などの関連カードを表示
    """
    # 統合された価格情報を取得
    unified = get_unified_card_prices(card_id)
    if not unified:
        raise HTTPException(status_code=404, detail="Card not found")

    card = unified['card']
    prices = unified['prices']

    # 価格履歴を取得（関連カード全ての価格履歴を統合）
    price_history = get_card_price_history(card_id, days=30)

    # 関連カード（リバイバル/旧版）を取得
    related_cards = get_related_cards(card_id, unified.get('base_name'))

    return {
        "card": card,
        "card_no": unified.get('card_no'),
        "base_name": unified.get('base_name'),
        "prices": [p.to_dict() for p in prices],
        "price_history": price_history,
        "min_price": min(p.price for p in prices) if prices else None,
        "max_price": max(p.price for p in prices) if prices else None,
        "shop_count": len(set(p.shop_id for p in prices)),
        "related_cards": related_cards,
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
        data={"sub": str(user.id), "username": user.username}
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
        data={"sub": str(user.id), "username": user.username}
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
        data={"sub": str(user.id), "username": user.username}
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


# =============================================================================
# Amazon商品API
# =============================================================================

AMAZON_AFFILIATE_TAG = "bsprice-22"


class AmazonProductCreate(BaseModel):
    url: str  # AmazonのURL（ASINを抽出する）
    name: str
    price: int
    image_url: str


class AmazonProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[int] = None


class AmazonProductReorder(BaseModel):
    product_ids: list[int]


def extract_asin_from_url(url: str) -> Optional[str]:
    """AmazonのURLからASINを抽出"""
    import re
    # /dp/ASIN or /gp/product/ASIN パターン
    patterns = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


@app.get("/api/amazon-products")
async def list_amazon_products():
    """Amazon商品一覧を取得（公開API）"""
    products = get_amazon_products(active_only=True)
    return {"products": [p.to_dict() for p in products]}


@app.get("/api/admin/amazon-products")
async def list_amazon_products_admin(admin_user: User = Depends(require_admin)):
    """Amazon商品一覧を取得（管理者用、非アクティブも含む）"""
    products = get_amazon_products(active_only=False)
    return {"products": [p.to_dict() for p in products]}


@app.post("/api/admin/amazon-products")
async def create_amazon_product(
    data: AmazonProductCreate,
    admin_user: User = Depends(require_admin)
):
    """Amazon商品を追加"""
    # ASINを抽出
    asin = extract_asin_from_url(data.url)
    if not asin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AmazonのURLからASINを抽出できませんでした"
        )

    try:
        product = add_amazon_product(
            asin=asin,
            name=data.name,
            price=data.price,
            image_url=data.image_url,
            affiliate_tag=AMAZON_AFFILIATE_TAG
        )
        return {"message": "商品を追加しました", "product": product.to_dict()}
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="この商品は既に登録されています"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"追加に失敗しました: {str(e)}"
        )


@app.put("/api/admin/amazon-products/{product_id}")
async def update_amazon_product_api(
    product_id: int,
    data: AmazonProductUpdate,
    admin_user: User = Depends(require_admin)
):
    """Amazon商品を更新"""
    product = update_amazon_product(
        product_id,
        name=data.name,
        price=data.price,
        image_url=data.image_url,
        is_active=data.is_active
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品が見つかりません"
        )
    return {"message": "商品を更新しました", "product": product.to_dict()}


@app.delete("/api/admin/amazon-products/{product_id}")
async def delete_amazon_product_api(
    product_id: int,
    admin_user: User = Depends(require_admin)
):
    """Amazon商品を削除"""
    success = delete_amazon_product(product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品が見つかりません"
        )
    return {"message": "商品を削除しました"}


@app.post("/api/admin/amazon-products/reorder")
async def reorder_amazon_products_api(
    data: AmazonProductReorder,
    admin_user: User = Depends(require_admin)
):
    """Amazon商品の表示順を変更"""
    reorder_amazon_products(data.product_ids)
    return {"message": "表示順を更新しました"}


# ==================== 楽天商品API ====================

from database import (
    get_rakuten_products, get_rakuten_product_by_id, add_rakuten_product,
    update_rakuten_product, delete_rakuten_product, reorder_rakuten_products
)

RAKUTEN_AFFILIATE_ID = "507d6316.932e0e43.507d6317.e71fdd26"


class RakutenProductCreate(BaseModel):
    name: str
    price: int
    image_url: str
    affiliate_url: str


class RakutenProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[int] = None


class RakutenProductReorder(BaseModel):
    product_ids: list[int]


@app.get("/api/rakuten-products")
async def list_rakuten_products():
    """楽天商品一覧を取得（公開API）"""
    products = get_rakuten_products(active_only=True)
    return {"products": [p.to_dict() for p in products]}


@app.get("/api/admin/rakuten-products")
async def list_rakuten_products_admin(admin_user: User = Depends(require_admin)):
    """楽天商品一覧を取得（管理者用、非アクティブも含む）"""
    products = get_rakuten_products(active_only=False)
    return {"products": [p.to_dict() for p in products]}


@app.post("/api/admin/rakuten-products")
async def create_rakuten_product(
    data: RakutenProductCreate,
    admin_user: User = Depends(require_admin)
):
    """楽天商品を追加"""
    # URLから商品コードを抽出（簡易的に）
    import re
    item_code_match = re.search(r'item\.rakuten\.co\.jp/([^/]+)/([^/]+)', data.affiliate_url)
    if item_code_match:
        item_code = f"{item_code_match.group(1)}_{item_code_match.group(2)}"
    else:
        item_code = str(hash(data.affiliate_url))[:16]

    product = add_rakuten_product(
        item_code=item_code,
        name=data.name,
        price=data.price,
        image_url=data.image_url,
        affiliate_url=data.affiliate_url
    )
    return {"product": product.to_dict()}


@app.put("/api/admin/rakuten-products/{product_id}")
async def update_rakuten_product_api(
    product_id: int,
    data: RakutenProductUpdate,
    admin_user: User = Depends(require_admin)
):
    """楽天商品を更新"""
    product = update_rakuten_product(
        product_id,
        name=data.name,
        price=data.price,
        image_url=data.image_url,
        is_active=data.is_active
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    return {"product": product.to_dict()}


@app.delete("/api/admin/rakuten-products/{product_id}")
async def delete_rakuten_product_api(
    product_id: int,
    admin_user: User = Depends(require_admin)
):
    """楽天商品を削除"""
    if delete_rakuten_product(product_id):
        return {"message": "削除しました"}
    raise HTTPException(status_code=404, detail="商品が見つかりません")


@app.post("/api/admin/rakuten-products/reorder")
async def reorder_rakuten_products_api(
    data: RakutenProductReorder,
    admin_user: User = Depends(require_admin)
):
    """楽天商品の表示順を変更"""
    reorder_rakuten_products(data.product_ids)
    return {"message": "表示順を更新しました"}


# =============================================================================
# アクセス解析API
# =============================================================================

@app.get("/api/admin/analytics/searches")
async def get_analytics_searches(
    period: str = Query("daily", description="集計期間: daily, weekly, monthly"),
    days: int = Query(30, ge=1, le=365, description="取得日数"),
    admin_user: User = Depends(require_admin)
):
    """検索統計を取得"""
    stats = get_search_stats(period=period, days=days)
    return {"period": period, "days": days, "stats": stats}


@app.get("/api/admin/analytics/clicks")
async def get_analytics_clicks(
    period: str = Query("daily", description="集計期間: daily, weekly, monthly"),
    days: int = Query(30, ge=1, le=365, description="取得日数"),
    admin_user: User = Depends(require_admin)
):
    """クリック統計を取得"""
    stats = get_click_stats(period=period, days=days)
    return {"period": period, "days": days, "stats": stats}


@app.get("/api/admin/analytics/keywords")
async def get_analytics_keywords(
    days: int = Query(30, ge=1, le=365, description="取得日数"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    admin_user: User = Depends(require_admin)
):
    """人気検索キーワードランキングを取得"""
    ranking = get_keyword_ranking(days=days, limit=limit)
    return {"days": days, "ranking": ranking}


@app.get("/api/admin/analytics/shops")
async def get_analytics_shops(
    days: int = Query(30, ge=1, le=365, description="取得日数"),
    admin_user: User = Depends(require_admin)
):
    """ショップ別クリック数を取得"""
    ranking = get_shop_click_ranking(days=days)
    return {"days": days, "ranking": ranking}


@app.get("/api/admin/analytics/cards")
async def get_analytics_cards(
    days: int = Query(30, ge=1, le=365, description="取得日数"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    admin_user: User = Depends(require_admin)
):
    """人気カードランキング（クリック数）を取得"""
    ranking = get_card_click_ranking(days=days, limit=limit)
    return {"days": days, "ranking": ranking}


# =============================================================================
# ユーザー管理API
# =============================================================================

@app.get("/api/admin/users")
async def get_admin_users(
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    search: str = Query(None, description="検索キーワード"),
    admin_user: User = Depends(require_admin)
):
    """ユーザー一覧を取得（ページネーション対応）"""
    users, total = get_users_paginated(limit=limit, offset=offset, search=search)
    return {
        "users": [u.to_dict() for u in users],
        "total": total,
        "limit": limit,
        "offset": offset
    }


class UserStatusUpdate(BaseModel):
    is_active: int


@app.put("/api/admin/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    admin_user: User = Depends(require_admin)
):
    """ユーザーのBAN/BAN解除"""
    if data.is_active not in (0, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="is_activeは0または1である必要があります"
        )

    user = update_user_is_active(user_id, data.is_active, admin_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザーが見つからないか、自分自身は変更できません"
        )

    action = "BAN解除" if data.is_active else "BAN"
    return {"message": f"ユーザーを{action}しました", "user": user.to_dict()}


class UserRoleUpdate(BaseModel):
    role: str


@app.put("/api/admin/users/{user_id}/role")
async def update_user_role_api(
    user_id: int,
    data: UserRoleUpdate,
    admin_user: User = Depends(require_admin)
):
    """ユーザーの権限を変更"""
    if data.role not in ('user', 'admin'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="roleはuserまたはadminである必要があります"
        )

    user = update_user_role(user_id, data.role, admin_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ユーザーが見つからないか、自分自身は変更できません"
        )

    action = "管理者権限を付与" if data.role == 'admin' else "一般ユーザーに変更"
    return {"message": f"{action}しました", "user": user.to_dict()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
