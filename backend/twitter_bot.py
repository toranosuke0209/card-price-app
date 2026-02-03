#!/usr/bin/env python3
"""
X (Twitter) BOT モジュール

価格変動通知をXに投稿する
"""

import os
import tweepy
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

# API認証情報
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')


def get_client():
    """Tweepy Client を取得"""
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        raise ValueError("X API認証情報が設定されていません。.envファイルを確認してください。")

    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    return client


def post_tweet(text: str) -> dict:
    """
    ツイートを投稿

    Args:
        text: 投稿するテキスト（最大280文字）

    Returns:
        投稿結果
    """
    client = get_client()
    response = client.create_tweet(text=text)
    return {
        'success': True,
        'tweet_id': response.data['id'],
        'text': text
    }


def post_price_drop(card_name: str, shop_name: str, old_price: int, new_price: int, card_url: str = None) -> dict:
    """
    値下げ通知を投稿
    """
    diff = old_price - new_price
    percent = (diff / old_price * 100) if old_price > 0 else 0

    # ツイート本文を作成
    text = f"📉 値下げ通知\n\n"
    text += f"【{card_name}】\n"
    text += f"🏪 {shop_name}\n"
    text += f"💰 {old_price:,}円 → {new_price:,}円\n"
    text += f"🔻 -{diff:,}円 ({percent:.1f}%OFF)\n"

    if card_url:
        text += f"\n🔗 {card_url}"

    text += "\n\n#バトスピ #バトルスピリッツ #BSPrice"

    # 280文字制限チェック
    if len(text) > 280:
        # カード名を短縮
        max_name_len = 20
        if len(card_name) > max_name_len:
            card_name = card_name[:max_name_len] + "..."
        text = f"📉 値下げ: {card_name} @ {shop_name}\n{old_price:,}円→{new_price:,}円 (-{diff:,}円)\n#バトスピ #BSPrice"

    return post_tweet(text)


def post_price_rise(card_name: str, shop_name: str, old_price: int, new_price: int, card_url: str = None) -> dict:
    """
    値上げ通知を投稿
    """
    diff = new_price - old_price
    percent = (diff / old_price * 100) if old_price > 0 else 0

    # ツイート本文を作成
    text = f"📈 値上げ通知\n\n"
    text += f"【{card_name}】\n"
    text += f"🏪 {shop_name}\n"
    text += f"💰 {old_price:,}円 → {new_price:,}円\n"
    text += f"🔺 +{diff:,}円 (+{percent:.1f}%)\n"

    if card_url:
        text += f"\n🔗 {card_url}"

    text += "\n\n#バトスピ #バトルスピリッツ #BSPrice"

    # 280文字制限チェック
    if len(text) > 280:
        max_name_len = 20
        if len(card_name) > max_name_len:
            card_name = card_name[:max_name_len] + "..."
        text = f"📈 値上げ: {card_name} @ {shop_name}\n{old_price:,}円→{new_price:,}円 (+{diff:,}円)\n#バトスピ #BSPrice"

    return post_tweet(text)


def test_connection():
    """API接続テスト"""
    try:
        client = get_client()
        # 自分のユーザー情報を取得してテスト
        me = client.get_me()
        return {
            'success': True,
            'username': me.data.username,
            'name': me.data.name
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    # 接続テスト
    print("X API 接続テスト...")
    result = test_connection()

    if result['success']:
        print(f"✅ 接続成功!")
        print(f"   アカウント: @{result['username']} ({result['name']})")
    else:
        print(f"❌ 接続失敗: {result['error']}")
