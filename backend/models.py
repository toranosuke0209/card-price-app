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
