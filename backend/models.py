"""
データモデル定義
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Shop:
    """ショップ情報"""
    id: int
    name: str
    url: str
    is_active: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Card:
    """カード情報"""
    id: int
    name: str
    name_normalized: str
    first_seen_at: Optional[datetime] = None
    # v2追加カラム
    card_no: Optional[str] = None
    source_shop_id: Optional[int] = None
    detail_url: Optional[str] = None
    is_popular: int = 0
    last_price_fetch_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Price:
    """価格情報"""
    id: int
    card_id: int
    shop_id: int
    price: int
    stock: int
    stock_text: str
    url: str
    image_url: str
    fetched_at: Optional[datetime] = None

    # JOIN結果用の追加フィールド
    card_name: Optional[str] = None
    shop_name: Optional[str] = None

    def to_dict(self) -> dict:
        """既存APIレスポンス形式に変換"""
        return {
            "card_id": self.card_id,
            "site": self.shop_name or "",
            "name": self.card_name or "",
            "price": self.price,
            "price_text": f"{self.price:,}円(税込)",
            "stock": self.stock,
            "stock_text": self.stock_text,
            "url": self.url,
            "image_url": self.image_url or "",
        }


@dataclass
class Click:
    """クリック記録"""
    id: int
    card_id: Optional[int]
    shop_id: Optional[int]
    price_id: Optional[int]
    clicked_at: Optional[datetime] = None


@dataclass
class SearchLog:
    """検索ログ"""
    id: int
    keyword: str
    result_count: int = 0
    searched_at: Optional[datetime] = None


@dataclass
class BatchProgress:
    """バッチ進捗管理"""
    id: int
    shop_id: int
    kana_type: str  # 'hiragana' / 'katakana'
    kana: str       # 'あ', 'い', ... 'ア', 'イ', ...
    current_page: int = 1
    total_pages: Optional[int] = None
    status: str = 'pending'  # 'pending' / 'in_progress' / 'completed'
    last_fetched_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FetchQueue:
    """取得キュー"""
    id: int
    card_name: str
    source: str = 'search'  # 'search' / 'batch'
    priority: int = 0       # 0:通常, 1:優先
    status: str = 'pending' # 'pending' / 'processing' / 'done'
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class User:
    """ユーザー情報"""
    id: int
    username: str
    email: str
    password_hash: str
    role: str = 'user'  # 'user' / 'admin'
    is_active: int = 1
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """パスワードを除いた辞書を返す"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": str(self.created_at) if self.created_at else None,
        }


@dataclass
class Favorite:
    """お気に入り"""
    id: int
    user_id: int
    card_id: int
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AdminInvite:
    """管理者招待コード"""
    id: int
    code: str
    created_by: Optional[int] = None
    used_by: Optional[int] = None
    created_at: Optional[datetime] = None
    used_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "created_by": self.created_by,
            "used_by": self.used_by,
            "created_at": str(self.created_at) if self.created_at else None,
            "used_at": str(self.used_at) if self.used_at else None,
            "is_used": self.used_by is not None,
        }


@dataclass
class FeaturedKeyword:
    """人気キーワード（管理者設定）"""
    id: int
    keyword: str
    display_order: int = 0
    is_active: int = 1
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "created_at": str(self.created_at) if self.created_at else None,
        }


@dataclass
class AmazonProduct:
    """Amazon商品（アフィリエイト用）"""
    id: int
    asin: str
    name: str
    price: int
    image_url: str
    affiliate_url: str
    display_order: int = 0
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "asin": self.asin,
            "name": self.name,
            "price": self.price,
            "price_text": f"¥{self.price:,}",
            "image_url": self.image_url,
            "affiliate_url": self.affiliate_url,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }


@dataclass
class RakutenProduct:
    """楽天商品（アフィリエイト用）"""
    id: int
    item_code: str  # 楽天の商品コード
    name: str
    price: int
    image_url: str
    affiliate_url: str
    display_order: int = 0
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_code": self.item_code,
            "name": self.name,
            "price": self.price,
            "price_text": f"¥{self.price:,}",
            "image_url": self.image_url,
            "affiliate_url": self.affiliate_url,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }
