"""
遊々亭クローラー（ローカル実行用）
自宅PCから遊々亭をクロールしてJSONファイルに保存する

使用方法:
  python crawl_yuyutei.py                  # 全セット巡回
  python crawl_yuyutei.py --sets bs74 bs73 # 特定セットのみ
  python crawl_yuyutei.py --list-sets      # セット一覧を表示
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# 設定
BASE_URL = "https://yuyu-tei.jp"
OUTPUT_DIR = Path(__file__).parent / "output"
INTERVAL = 3  # ページ間隔（秒）

# バトルスピリッツのセットコード一覧（全セット）
BS_SETS = [
    # 契約編
    "bs74", "bs73", "bs72", "bs71", "bs70", "bs69", "bs68", "bs67",
    # 真・転醒編
    "bs66", "bs65", "bs64", "bs63", "bs62", "bs61", "bs60", "bs59", "bs58", "bs57", "bs56",
    # 転醒編
    "bs55", "bs54", "bs53", "bs52", "bs51", "bs50", "bs49", "bs48",
    # 超煌臨編
    "bs47", "bs46", "bs45", "bs44", "bs43", "bs42", "bs41", "bs40",
    # 神煌臨編
    "bs39", "bs38", "bs37", "bs36", "bs35", "bs34",
    # 煌臨編
    "bs33", "bs32", "bs31", "bs30", "bs29", "bs28",
    # 十二神皇編・烈火伝
    "bs27", "bs26", "bs25", "bs24", "bs23", "bs22", "bs21", "bs20", "bs19",
    # アルティメットバトル・覇王編
    "bs18", "bs17", "bs16", "bs15", "bs14", "bs13", "bs12", "bs11", "bs10",
    # 初期シリーズ
    "bs09", "bs08", "bs07", "bs06", "bs05", "bs04", "bs03", "bs02", "bs01",
    # BSC（コラボ・構築済み）全シリーズ
    "bsc50", "bsc49", "bsc48", "bsc47", "bsc46", "bsc45", "bsc44", "bsc43", "bsc42", "bsc41", "bsc40",
    "bsc39", "bsc38", "bsc37", "bsc36", "bsc35", "bsc34", "bsc33", "bsc32", "bsc31", "bsc30",
    "bsc29", "bsc28", "bsc27", "bsc26", "bsc25", "bsc24", "bsc23", "bsc22", "bsc21", "bsc20",
    "bsc19", "bsc18", "bsc17", "bsc16", "bsc15", "bsc14", "bsc13", "bsc12", "bsc11", "bsc10",
    "bsc09", "bsc08", "bsc07", "bsc06", "bsc05", "bsc04", "bsc03", "bsc02", "bsc01",
    # SD（スターターデッキ）
    "sd67", "sd66", "sd65", "sd64", "sd63", "sd62", "sd61", "sd60",
    "sd59", "sd58", "sd57", "sd56", "sd55", "sd54", "sd53", "sd52", "sd51", "sd50",
    "sd49", "sd48", "sd47", "sd46", "sd45", "sd44", "sd43", "sd42", "sd41", "sd40",
    "sd39", "sd38", "sd37", "sd36", "sd35", "sd34", "sd33", "sd32", "sd31", "sd30",
    "sd29", "sd28", "sd27", "sd26", "sd25", "sd24", "sd23", "sd22", "sd21", "sd20",
    "sd19", "sd18", "sd17", "sd16", "sd15", "sd14", "sd13", "sd12", "sd11", "sd10",
    "sd09", "sd08", "sd07", "sd06", "sd05", "sd04", "sd03", "sd02", "sd01",
    # PB（プロモ）全シリーズ
    "pb46", "pb45", "pb44", "pb43", "pb42", "pb41", "pb40",
    "pb39", "pb38", "pb37", "pb36", "pb35", "pb34", "pb33", "pb32", "pb31", "pb30",
    "pb29", "pb28", "pb27", "pb26", "pb25", "pb24", "pb23", "pb22", "pb21", "pb20",
    "pb19", "pb18", "pb17", "pb16", "pb15", "pb14", "pb13", "pb12", "pb11", "pb10",
    "pb09", "pb08", "pb07", "pb06", "pb05", "pb04", "pb03", "pb02", "pb01",
    # CB（コラボブースター）
    "cb30", "cb29", "cb28", "cb27", "cb26", "cb25", "cb24", "cb23", "cb22", "cb21", "cb20",
    "cb19", "cb18", "cb17", "cb16", "cb15", "cb14", "cb13", "cb12", "cb11", "cb10",
    "cb09", "cb08", "cb07", "cb06", "cb05", "cb04", "cb03", "cb02", "cb01",
    # 特殊
    "sale", "damage", "new",
]


def get_set_list():
    """利用可能なセット一覧を取得"""
    client = httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True
    )

    try:
        r = client.get(f"{BASE_URL}/top/bs")
        soup = BeautifulSoup(r.text, "lxml")

        sets = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            match = re.search(r"/sell/bs/s/([a-zA-Z0-9]+)", href)
            if match:
                sets.add(match.group(1))

        return sorted(sets)
    finally:
        client.close()


def crawl_set(client, set_code: str) -> list[dict]:
    """1つのセットをクロール"""
    url = f"{BASE_URL}/sell/bs/s/{set_code}"
    print(f"  クロール中: {url}")

    try:
        r = client.get(url)
        if r.status_code != 200:
            print(f"    エラー: HTTP {r.status_code}")
            return []
    except Exception as e:
        print(f"    エラー: {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    products = soup.find_all(class_="card-product")

    cards = []
    for p in products:
        try:
            card = parse_product(p, set_code)
            if card:
                cards.append(card)
        except Exception as e:
            continue

    print(f"    {len(cards)}件取得")
    return cards


def parse_product(element, set_code: str) -> dict | None:
    """商品要素をパース"""
    # 在庫状態
    is_sold_out = "sold-out" in element.get("class", [])

    # 商品URL
    link = element.select_one("a[href*='/sell/bs/card/']")
    if not link:
        return None
    detail_url = link.get("href", "")
    if not detail_url.startswith("http"):
        detail_url = BASE_URL + detail_url

    # カード番号
    card_no_elem = element.select_one("span.d-block.border")
    card_no = card_no_elem.get_text(strip=True) if card_no_elem else None

    # カード名
    name_elem = element.select_one("h4.text-primary")
    name = name_elem.get_text(strip=True) if name_elem else None
    if not name:
        return None

    # 価格
    price = 0
    price_elem = element.select_one("strong.d-block")
    if price_elem:
        price_text = price_elem.get_text(strip=True)
        match = re.search(r"([\d,]+)", price_text)
        if match:
            price = int(match.group(1).replace(",", ""))

    # 在庫数
    stock = 0 if is_sold_out else 1
    stock_text = "売切" if is_sold_out else "在庫あり"

    # 在庫詳細を取得
    stock_label = element.select_one("label.cart_sell_zaiko")
    if stock_label:
        stock_full_text = stock_label.get_text(strip=True)
        if "×" in stock_full_text or "売切" in stock_full_text:
            stock = 0
            stock_text = "売切"

    # 画像URL
    image_url = ""
    img_elem = element.select_one("img.card")
    if img_elem:
        image_url = img_elem.get("src", "")

    return {
        "name": name,
        "card_no": card_no,
        "set_code": set_code,
        "detail_url": detail_url,
        "price": price,
        "stock": stock,
        "stock_text": stock_text,
        "image_url": image_url,
    }


def main():
    parser = argparse.ArgumentParser(description="遊々亭クローラー（ローカル実行用）")
    parser.add_argument("--sets", nargs="+", help="クロールするセットコード（指定しない場合は全セット）")
    parser.add_argument("--list-sets", action="store_true", help="セット一覧を表示")
    parser.add_argument("--output", type=str, help="出力ファイル名（デフォルト: yuyutei_YYYYMMDD.json）")

    args = parser.parse_args()

    if args.list_sets:
        print("利用可能なセット:")
        for s in BS_SETS:
            print(f"  {s}")
        return

    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # クロール対象セット
    sets = args.sets if args.sets else BS_SETS

    print(f"遊々亭クローラー開始")
    print(f"対象セット数: {len(sets)}")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")
    print()

    client = httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        follow_redirects=True
    )

    all_cards = []

    try:
        for i, set_code in enumerate(sets, 1):
            print(f"[{i}/{len(sets)}] セット: {set_code}")
            cards = crawl_set(client, set_code)
            all_cards.extend(cards)

            if i < len(sets):
                time.sleep(INTERVAL)
    finally:
        client.close()

    # 結果を保存
    output_file = args.output if args.output else f"yuyutei_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = OUTPUT_DIR / output_file

    result = {
        "crawled_at": datetime.now().isoformat(),
        "total_cards": len(all_cards),
        "sets_crawled": len(sets),
        "cards": all_cards,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print()
    print(f"クロール完了")
    print(f"  合計カード数: {len(all_cards)}")
    print(f"  出力ファイル: {output_path}")


if __name__ == "__main__":
    main()
