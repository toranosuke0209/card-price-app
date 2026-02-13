"""
ドラスタクローラー（ローカル実行用）
Seleniumを使用してCloudflareを通過

使用方法:
  python crawl_dorasuta.py                  # 50シリーズずつ巡回（進捗保存）
  python crawl_dorasuta.py --new-arrivals   # 新商品取得（最新シリーズのみ）
  python crawl_dorasuta.py --status         # 現在の進捗を表示
  python crawl_dorasuta.py --reset          # 進捗をリセット
  python crawl_dorasuta.py --resume 10410:6 # シリーズ10410のページ6から再開
  python crawl_dorasuta.py --series 13019   # 特定シリーズのみ
  python crawl_dorasuta.py --list-series    # シリーズ一覧を表示
  python crawl_dorasuta.py --special        # SALE・傷あり特価ページをクロール
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# 設定
BASE_URL = "https://dorasuta.jp"
OUTPUT_DIR = Path(__file__).parent / "output"
INTERVAL = 5  # ページ間隔（秒）- サーバー負荷軽減
BATCH_SIZE = 50  # 1回あたりのシリーズ数
PROGRESS_FILE = Path(__file__).parent / "dorasuta_progress.txt"

# 特価ページ（状態別）
SPECIAL_PAGES = [
    ("sale", "SALE", "https://dorasuta.jp/battlespirits/product-list?cocd=2"),
    ("damaged", "傷あり特価", "https://dorasuta.jp/battlespirits/product-list?cid=75&cocd=3"),
]

# バトルスピリッツのシリーズID一覧（179シリーズ）
BS_SERIES = [
    ("13019", "【BSC51】ディーバブースター メモリアルレコード"),
    ("10670", "【BSC50】アニメブースター RESONATING STARS"),
    ("10604", "[PB42]バトルスピリッツ コラボスターターセット 仮面ライダー おかしな絆"),
    ("10516", "【BS74】契約編:環 第3章 覇極来臨"),
    ("10410", "【BSC49】ドリームブースター 巡る星々"),
    ("10245", "【BS73】契約編:環 第2章 天地転世"),
    ("10145", "【BSC48】アニメブースター バーニングレガシー"),
    ("10026", "【BSC47】REBIRTH OF LEGENDS"),
    ("9905", "【BS72】契約編:環 第1章 廻帰再醒"),
    ("9737", "【CB34】仮面ライダー 善悪の選択"),
    ("9695", "【BSC46】ディーバブースター 10thアフターパーティー"),
    ("9610", "【CB33】コラボブースター ペルソナ3 リロード"),
    ("9545", "【BS71】契約編:真 第4章 神王の帰還"),
    ("9471", "【CB32】ウルトラマン イマジネーションパワー"),
    ("9034", "【BS70】契約編:真 第3章 全天の覇神"),
    ("8925", "【BSC45】ドリームブースター 巡るヒカリ"),
    ("8926", "【CB31】コラボブースター 仮面ライダー Exceed the limit"),
    ("8852", "【BSC44】ブースターパック AGE OF AVENGERS"),
    ("8851", "リミテッドパック2024 契約編 真 Vol.1"),
    ("8608", "【BS69】契約編:真 第2章 原初の襲来"),
    ("8556", "【BSC43】ディーバブースター 10thパーティー"),
    ("7863", "【CB30】仮面ライダー 神秘なる願い"),
    ("7814", "【CBX01】コラボブースターEX ガンダム 運命と自由"),
    ("7783", "【BS67】契約編:界 第4章 界導"),
    ("7696", "【CB29】ガンダム～魔女の宿命～"),
    ("7561", "【BS66】契約編:界 第3章 紡約"),
    ("7455", "【PB】アイカツ！ ルミナス＆トライスター"),
    ("7419", "【CB28】ゴジラ ～怪獣王ノ帰還～"),
    ("7197", "【BS65】契約編:界 第2章:極争"),
    ("7145", "【BSC42】ドラフトブースター【巡るキセキ】"),
    ("7153", "【PC05】エヴァンゲリオン 紡がれる想い"),
    ("7113", "【PC04】ウルトラマン 新たな光"),
    ("7063", "【BSC41】GREATEST RECORD 2023"),
    ("7002", "【BS64】契約編:界 第１章 閃刃"),
    ("6915", "【BSC40】ディーバブースター 白黒幻奏"),
    ("6867", "【CB27】ガンダム 魔女の覚醒"),
    ("6739", "【BS63】契約編 第4章 ビヨンドエボリューション"),
    ("6668", "【CB26】TIGER & BUNNY HERO SCRAMBLE"),
    ("6618", "【CB25】ガンダム ～魔女の切り札～"),
    ("6539", "【BS62】契約編 第3章 ライズオブライバルズ"),
    ("6490", "【CB24】仮面ライダー最高の相棒"),
    ("6440", "【BS61】契約編 第2章リベレーションオブゴッド"),
    ("6392", "【CB23】エヴァンゲリオン シン実の贖罪"),
    ("6272", "【BS60】契約編 第1章ファーストパートナー"),
    ("5734", "【CB22】コラボブースターウルトラマン受け継がれる光"),
    ("5724", "【BSC39】ディーバブースター詩姫の戦歌"),
    ("5684", "【BS59】真・転醒編 第4章 運命の変革"),
    ("5609", "【CB21】エヴァンゲリオン 胎動の序曲"),
    ("5599", "【CB20】仮面ライダー ～Extra Expansion～"),
    ("5598", "【BS58】真･転醒編 第3章:始原の鼓動"),
    ("5355", "【CB19】仮面ライダー僕らの希望"),
    ("5354", "【BS57】真･転醒編 第2章 究極の神醒"),
    ("5353", "【CB18】ウルトラヒーロー英雄譚"),
    ("5352", "【BSC38】Xレアパック2021"),
    ("5350", "【BS56】真･転醒編 第1章:世界の真実"),
    ("5349", "【CB17】仮面ライダー響鳴する剣"),
    ("5347", "【CB16】ガンダム戦場に咲く鉄の華"),
    ("5346", "【BS55】転醒編 第4章 天地万象"),
    ("5343", "【BSC37】オールキラブースター【プレミアムディーバセレクション】"),
    ("5342", "【BS54】転醒編 第3章 紫電一閃"),
    ("5341", "【CB15】仮面ライダー 相棒との道"),
    ("5340", "【BS53】転醒編 第2章:神出鬼没"),
    ("5339", "【BSC36】GREATEST RECORD 2020"),
    ("5338", "【CB14】オールアイカツ!ドリームオンステージ"),
    ("5337", "【CB13】ガンダム宇宙を駆ける戦士"),
    ("5336", "【BS52】転醒編 第1章 輪廻転生"),
    ("5334", "【CB12】仮面ライダー ～Extreme edition～"),
    ("5332", "【CB11】デジモンLAST EVOLUTION"),
    ("5331", "【BS51】超煌臨編 第4章:神攻勢力"),
    ("5330", "【CB10】仮面ライダー～開戦!ライダーウォーズ"),
    ("5328", "【BSC35】ディーバブースター【ドリームアイドルフェスティバル!】"),
    ("5327", "【BS50】超煌臨編 第3章:全知全能"),
    ("5326", "【CB09】仮面ライダー ～新世界への進化～"),
    ("5325", "【BS49】超煌臨編 第2章:双刃乃神"),
    ("5324", "【BSC34】オールキラブースター【神光の導き】"),
    ("5323", "【BS48】超煌臨編 第1章:神話覚醒"),
    ("5322", "【BSC33】ディーバブースター【学園神話】"),
    ("5321", "【CB08】仮面ライダー～欲望と切札と王の誕生"),
    ("5320", "【BS47】神煌臨編 第4章:神の帰還"),
    ("5319", "【CB07】デジモン 決めろ!カードスラッシュ～"),
    ("5317", "【BS46】神煌臨編 第3章:神々の運命"),
    ("5316", "【CB06】仮面ライダー～疾走する運命～"),
    ("5315", "【BSC32】ドリームブースター【俺たちのキセキ】"),
    ("5314", "【BS45】神煌臨編 第2章:蘇る究極神"),
    ("5313", "【CB05】ぼくらのデジモンアドベンチャー"),
    ("5312", "【BS44】神煌臨編 第1章:創界神の鼓動"),
    ("5311", "【CB04】仮面ライダー ～伝説の始まり～"),
    ("5310", "【BSC31】ディーバブースター【真夏の学園】"),
    ("5309", "【BS43】煌臨編 第4章:選バレシ者"),
    ("5308", "【BSC30】オールキラブースター【烈火伝承】"),
    ("5307", "リミテッドパック2017"),
    ("5306", "【BS42】煌臨編 第3章:革命ノ神器"),
    ("5305", "【CB02】デジモン超進化!"),
    ("5304", "【BS41】煌臨編 第2章:蒼キ海賊"),
    ("5303", "【CB01】ウルトラヒーロー大集結"),
    ("5301", "【BS40】煌臨編 第1章:伝説ノ英雄"),
    ("5299", "【BSC29】ドリームブースター【バトスピフェスティバル】"),
    ("5298", "【BS39】十二神皇編 第5章"),
    ("5297", "【BSC28】ディーバブースター【詩姫学園】"),
    ("5296", "【BS38】十二神皇編 第4章"),
    ("5295", "【BSC27】オールキラブースター【究極再来】"),
    ("5294", "【BS37】十二神皇編 第3章"),
    ("5293", "【BSC26】コラボブースター【怪獣王ノ咆哮】"),
    ("5292", "【BS36】十二神皇編 第2章"),
    ("5291", "【BSC25】ドリームブースター【炎と風の異魔神】"),
    ("5290", "【BS35】十二神皇編 第1章"),
    ("5288", "【BSC24】コラボブースター【ウルトラ怪獣超決戦】"),
    ("5287", "【BSC23】ディーバブースター【戦乱魂歌】"),
    ("5286", "【BS34】烈火伝第4章"),
    ("5285", "【BSC22】リバイバルブースター【龍皇再誕】"),
    ("5284", "【BS33】烈火伝第3章"),
    ("5283", "【BSC21】オールキラブースター【名刀コレクション】"),
    ("5282", "【BS32】烈火伝第2章"),
    ("5281", "【BSC20】戦略ブースター【激闘!戦国15ノ陣】"),
    ("5280", "【BS31】烈火伝第1章"),
    ("5279", "【BSC19】コラボブースター【東宝怪獣大決戦】"),
    ("5278", "【BSC18】ディーバブースター【詩姫の交響曲】"),
    ("5277", "【BS30】アルティメットバトル07"),
    ("5276", "【BS29】アルティメットバトル06"),
    ("5275", "【BS28】アルティメットバトル05"),
    ("5274", "【BSC17】オールキラブースター【眩き究極の王者】"),
    ("5273", "【BS27】アルティメットバトル04"),
    ("5272", "【BS26】アルティメットバトル03"),
    ("5271", "【BSC16】ディーバブースター【女神達の調べ】"),
    ("5270", "【BS25】アルティメットバトル02"),
    ("5269", "【BS24】アルティメットバトル01"),
    ("5268", "【BS23】剣刃編第5弾:剣刃神話"),
    ("5267", "【BS22】剣刃編第4弾:暗黒刃翼"),
    ("5266", "【BS21】剣刃編第3弾:光輝剣武"),
    ("5265", "【BS20】剣刃編第2弾:乱剣戦記"),
    ("5264", "【BS19】剣刃編第1弾:聖剣時代"),
    ("5263", "【BS18】覇王編第5弾:覇王大決戦"),
    ("5262", "【BS17】覇王編第4弾:剣舞う世界"),
    ("5261", "【BS16】覇王編第3弾:爆烈の覇道"),
    ("5260", "【BS15】覇王編第2弾:黄金の大地"),
    ("5259", "【BS14】覇王編第1弾:英雄龍の伝説"),
    ("5258", "【BS13】星座編第四弾:星空の王者"),
    ("5257", "【BS12】星座編第三弾:月の咆哮"),
    ("5256", "【BS11】星座編第二弾:灼熱の太陽"),
    ("5255", "【BS10】星座編第一弾:八星龍降臨"),
    ("5254", "【BS09】第九弾超星"),
    ("5253", "【BS08】第八弾戦嵐"),
    ("5252", "【BS07】第七弾天醒"),
    ("5251", "【BS06】第六弾爆神"),
    ("5250", "【BS05】第五弾皇騎"),
    ("5249", "【BS04】第四弾龍帝"),
    ("5248", "【BS03】第三弾覇闘"),
    ("5247", "【BS02】第二弾激翔"),
    ("5246", "【BS01】第一弾"),
    ("9613", "【SD70】コラボスターター ペルソナ3 リロード"),
    ("9474", "【SD69】メガデッキ 豪炎の創世主"),
    ("8020", "【BS】BS68 契約編:真 第1章 神々の戦い"),
    ("7923", "【SD68】太陽神の顕現"),
    ("7730", "【PC11】バトスピプレミアムカードセットゴジラ対エヴァンゲリオン"),
    ("7735", "【PC12】バトスピプレミアムカードセット新世紀エヴァンゲリオン"),
    ("7460", "【PB】TIGER＆BUNNY UNSTOPPABLE HERO"),
    ("7457", "【PB】カードセット アイカツ！ ソレイユ＆ぽわぽわプリリン"),
    ("7684", "【PC06】バトルスピリッツ 少年突破バシン"),
    ("7687", "【PC07】バトスピプレミアムカードセット 最強銀河 究極ゼロ ~バトルスピリッツ~"),
    ("7254", "【SD66】バトスピドリームデッキ 紅蓮の異世界"),
    ("7257", "【SD67】バトスピドリームデッキ 究極の新星"),
    ("6958", "【SD65】メガデッキ ニュージェネレーション"),
    ("6470", "【PC03】バトスピプレミアムカードセット"),
    ("6312", "【PC01】バトスピプレミアムカードセット イアン"),
    ("6315", "【PC02】バトスピプレミアムカードセット ショコラ"),
    ("6320", "【SD64】バトスピダッシュデッキ【無限の絆】"),
    ("5744", "【SD63】メガデッキ【光主の共鳴】"),
    ("5610", "【SD62】コラボスターター【エヴァンゲリオン 目醒めの刻】"),
    ("5600", "【SD60】エントリーデッキ【紫翼の未来】"),
    ("5597", "【SD61】エントリーデッキ【白銀の記憶】"),
    ("5351", "【SD59】バトスピダッシュデッキ【革命の竜騎士】"),
    ("5348", "【SD58】メガデッキ【学園演奏会】"),
    ("5344", "【SD56】メガデッキ【覇王見斬】"),
    ("5345", "【SD57】メガデッキ【魔王災誕】"),
    ("5335", "【SD55】バトスピダッシュデッキ【創醒の書】"),
    ("5333", "【SD52～SD54】コラボスターター【ガンダム OPERATIONシリーズ】"),
    ("5329", "【SD51】メガデッキ【ダブルノヴァデッキX】"),
    ("5302", "戦国プレミアムBOX"),
    ("7679", "ツインウエハース 15thメモリアル"),
]

# 新商品取得用シリーズ（最新弾のみ）
NEW_ARRIVALS_SERIES = [
    ("13019", "【BSC51】ディーバブースター メモリアルレコード"),
    ("10670", "【BSC50】アニメブースター RESONATING STARS"),
    ("10516", "【BS74】契約編:環 第3章 覇極来臨"),
    ("10410", "【BSC49】ドリームブースター 巡る星々"),
    ("10245", "【BS73】契約編:環 第2章 天地転世"),
]


def get_driver():
    """WebDriverを取得（専用プロファイルを使用）"""
    import os
    options = Options()

    # 専用のプロファイルディレクトリを使用（Cookieを保持）
    profile_dir = Path(__file__).parent / "chrome_profile"
    profile_dir.mkdir(exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")
    print(f"プロファイル: {profile_dir}")

    # Bot検知回避
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 画面表示あり
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=ja-JP")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")

    driver = webdriver.Chrome(options=options)

    # webdriver プロパティを隠す
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })

    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    return driver


def wait_for_cloudflare(driver, timeout=120):
    """Cloudflareチェックを通過するまで待機"""
    print("Cloudflare認証待機中...")
    print("※ブラウザでチェックボックスをクリックしてください")

    start = time.time()
    while time.time() - start < timeout:
        title = driver.title
        if "お待ち" not in title and "moment" not in title.lower() and "challenge" not in title.lower():
            print("Cloudflare通過完了!")
            return True
        time.sleep(1)

    print("タイムアウト - Cloudflareを通過できませんでした")
    raise Exception("Cloudflare認証タイムアウト - クローラーを停止します")


def crawl_series(driver, series_id: str, series_name: str, start_page: int = 1) -> list[dict]:
    """1つのシリーズをクロール（全ページ）"""
    all_cards = []
    page = start_page

    # 最初のページ
    url = f"{BASE_URL}/battlespirits/product-list?sid={series_id}"
    print(f"  ページ {page}: {url}")
    driver.get(url)
    time.sleep(3)

    # Cloudflareチェック
    if "お待ち" in driver.title or "moment" in driver.title.lower():
        wait_for_cloudflare(driver)  # 失敗時は例外で停止

    # 指定ページまでスキップ
    if start_page > 1:
        print(f"  ページ {start_page} までスキップ中...")
        for skip_page in range(2, start_page + 1):
            driver.execute_script(f"$.formSubmit('#form110200', 'search', ['pager', '{skip_page}']);")
            time.sleep(3)
        print(f"  ページ {start_page} に到達")

    while True:
        # ページ読み込み待機
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.element"))
            )
        except:
            print("    要素が見つかりません")
            break

        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # 商品を取得
        cards = parse_products(soup, series_id, series_name)
        if not cards:
            break

        all_cards.extend(cards)
        print(f"    {len(cards)}件取得 (累計: {len(all_cards)})")

        # 次のページがあるか確認
        max_page = get_max_page(soup)
        if page >= max_page:
            break

        # 次のページへ（JavaScript実行）
        page += 1
        print(f"  ページ {page}/{max_page}")
        try:
            driver.execute_script(f"$.formSubmit('#form110200', 'search', ['pager', '{page}']);")
            time.sleep(INTERVAL)

            # Cloudflareチェック（再認証が必要な場合）
            if "お待ち" in driver.title or "moment" in driver.title.lower():
                wait_for_cloudflare(driver)  # 失敗時は例外で停止
        except Exception as e:
            print(f"    ページ遷移エラー: {e}")
            raise  # エラー時は停止

    return all_cards


def crawl_special_page(driver, page_id: str, page_name: str, page_url: str) -> list[dict]:
    """特価ページをクロール（全ページ）"""
    all_cards = []
    page = 1

    # 状態名（condition）を設定
    condition = page_name  # "SALE" or "傷あり特価"

    print(f"  ページ 1: {page_url}")
    driver.get(page_url)
    time.sleep(3)

    # Cloudflareチェック
    if "お待ち" in driver.title or "moment" in driver.title.lower():
        wait_for_cloudflare(driver)

    while True:
        # ページ読み込み待機
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.element"))
            )
        except:
            print("    要素が見つかりません")
            break

        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "lxml")

        # 商品を取得（conditionを渡す）
        cards = parse_products(soup, page_id, page_name, condition)
        if not cards:
            break

        all_cards.extend(cards)
        print(f"    {len(cards)}件取得 (累計: {len(all_cards)})")

        # 次のページがあるか確認
        max_page = get_max_page(soup)
        if page >= max_page:
            break

        # 次のページへ
        page += 1
        print(f"  ページ {page}/{max_page}")
        try:
            driver.execute_script(f"$.formSubmit('#form110200', 'search', ['pager', '{page}']);")
            time.sleep(INTERVAL)

            if "お待ち" in driver.title or "moment" in driver.title.lower():
                wait_for_cloudflare(driver)
        except Exception as e:
            print(f"    ページ遷移エラー: {e}")
            raise

    return all_cards


def get_max_page(soup) -> int:
    """最大ページ数を取得"""
    max_page = 1
    pager_elems = soup.select("div.pager a, div.pager div.page_num")
    for elem in pager_elems:
        text = elem.get_text(strip=True)
        if text.isdigit():
            max_page = max(max_page, int(text))
    return max_page


def parse_products(soup, series_id: str, series_name: str, condition: str = "通常") -> list[dict]:
    """商品リストをパース"""
    cards = []
    elements = soup.select("div.element:has(div.description)")

    for elem in elements:
        try:
            card = parse_product(elem, series_id, series_name, condition)
            if card:
                cards.append(card)
        except Exception:
            continue

    return cards


def parse_product(element, series_id: str, series_name: str, condition: str = "通常") -> dict | None:
    """1商品をパース"""
    # 商品名とURL
    name_elem = element.select_one("div.description li.change_hight a")
    if not name_elem:
        return None

    name = name_elem.get_text(strip=True)
    if not name:
        return None

    detail_url = name_elem.get("href", "")
    if detail_url and not detail_url.startswith("http"):
        detail_url = BASE_URL + detail_url

    # カード番号を抽出
    card_no = None
    card_no_match = re.search(r'([A-Z]{2,3}\d{1,2}-[A-Z]?\d{1,3})', name)
    if card_no_match:
        card_no = card_no_match.group(1)

    # 価格
    price = 0
    for li in element.select("div.description ul li"):
        text = li.get_text()
        if "円" in text:
            match = re.search(r'([\d,]+)円', text)
            if match:
                price = int(match.group(1).replace(",", ""))
            break

    # 在庫
    stock = 0
    stock_text = ""
    soldout = element.select_one("a.condition.soldout, .soldout")
    if soldout:
        stock = 0
        stock_text = "SOLDOUT"
    else:
        stock_elem = element.select_one("div.selectbox[data-value]")
        if stock_elem:
            stock_val = stock_elem.get("data-value", "0")
            if stock_val.isdigit():
                stock = int(stock_val)
                stock_text = f"在庫: {stock}"
        elif price > 0:
            stock = 1
            stock_text = "在庫あり"

    # 画像URL
    image_url = ""
    img_elem = element.select_one("div.content img[data-src]")
    if img_elem:
        image_url = img_elem.get("data-src", "")
        if image_url and not image_url.startswith("http"):
            image_url = BASE_URL + image_url

    return {
        "name": name,
        "card_no": card_no,
        "series_id": series_id,
        "series_name": series_name,
        "detail_url": detail_url,
        "price": price,
        "stock": stock,
        "stock_text": stock_text,
        "image_url": image_url,
        "condition": condition,
    }


def load_progress() -> int:
    """進捗を読み込み（次に処理するインデックスを返す）"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r") as f:
                return int(f.read().strip())
        except:
            pass
    return 0


def save_progress(index: int):
    """進捗を保存"""
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(index))


def reset_progress():
    """進捗をリセット"""
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    print("進捗をリセットしました。次回は最初から実行します。")


def main():
    parser = argparse.ArgumentParser(description="ドラスタクローラー（ローカル実行用）")
    parser.add_argument("--new-arrivals", action="store_true", help="新商品取得モード（最新シリーズのみ巡回）")
    parser.add_argument("--series", nargs="+", help="クロールするシリーズID")
    parser.add_argument("--list-series", action="store_true", help="シリーズ一覧を表示")
    parser.add_argument("--output", type=str, help="出力ファイル名")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help=f"1回あたりのシリーズ数（デフォルト: {BATCH_SIZE}）")
    parser.add_argument("--reset", action="store_true", help="進捗をリセットして最初から")
    parser.add_argument("--status", action="store_true", help="現在の進捗を表示")
    parser.add_argument("--resume", type=str, help="シリーズID:ページ番号 から再開（例: 10410:6）")
    parser.add_argument("--special", action="store_true", help="SALE・傷あり特価ページをクロール")
    parser.add_argument("--check-duplicates", type=str, help="既存JSONと重複チェック")

    args = parser.parse_args()

    if args.list_series:
        print("登録済みシリーズ:")
        for i, (sid, name) in enumerate(BS_SERIES):
            print(f"  {i+1}. {sid}: {name}")
        print(f"\n合計: {len(BS_SERIES)} シリーズ")
        return

    if args.reset:
        reset_progress()
        return

    if args.status:
        progress = load_progress()
        remaining = len(BS_SERIES) - progress
        print(f"進捗: {progress}/{len(BS_SERIES)} シリーズ完了")
        print(f"残り: {remaining} シリーズ")
        if progress >= len(BS_SERIES):
            print("全シリーズ完了しています。--reset で最初からやり直せます。")
        return

    # 重複チェック
    if args.check_duplicates:
        check_path = Path(args.check_duplicates)
        if not check_path.exists():
            print(f"エラー: ファイルが見つかりません: {check_path}")
            return
        with open(check_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_cards = {(c["name"], c["card_no"]) for c in existing_data.get("cards", [])}
        print(f"既存データ: {len(existing_cards)} 件のカード")
        return

    # --new-arrivals: 新商品取得モード
    if args.new_arrivals:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print("=== 新商品取得モード ===")
        print(f"対象シリーズ数: {len(NEW_ARRIVALS_SERIES)}")
        print(f"出力ディレクトリ: {OUTPUT_DIR}")
        print()
        print("※ Cloudflareのチェックが表示されたら手動でクリックしてください")
        print()

        driver = get_driver()
        all_cards = []

        try:
            for i, (series_id, series_name) in enumerate(NEW_ARRIVALS_SERIES, 1):
                print(f"[{i}/{len(NEW_ARRIVALS_SERIES)}] シリーズ: {series_id} {series_name}")
                cards = crawl_series(driver, series_id, series_name)
                all_cards.extend(cards)

                if i < len(NEW_ARRIVALS_SERIES):
                    time.sleep(INTERVAL)

            output_file = args.output if args.output else f"dorasuta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = OUTPUT_DIR / output_file

            result = {
                "crawled_at": datetime.now().isoformat(),
                "total_cards": len(all_cards),
                "series_crawled": len(NEW_ARRIVALS_SERIES),
                "cards": all_cards,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print()
            print(f"新商品取得完了")
            print(f"  合計カード数: {len(all_cards)}")
            print(f"  出力ファイル: {output_path}")

        except Exception as e:
            print()
            print(f"エラーで停止: {e}")
            if all_cards:
                output_file = f"dorasuta_{datetime.now().strftime('%Y%m%d_%H%M%S')}_partial.json"
                output_path = OUTPUT_DIR / output_file
                result = {
                    "crawled_at": datetime.now().isoformat(),
                    "total_cards": len(all_cards),
                    "series_crawled": "partial",
                    "cards": all_cards,
                }
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"途中結果を保存: {output_path}")

        finally:
            print()
            print("5秒後にブラウザを閉じます...")
            time.sleep(5)
            driver.quit()

        return

    # --special: 特価ページのクロール
    if args.special:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print("特価ページクローラー開始")
        print(f"対象: {', '.join([p[1] for p in SPECIAL_PAGES])}")
        print()
        print("※ Cloudflareのチェックが表示されたら手動でクリックしてください")
        print()

        driver = get_driver()
        all_cards = []

        try:
            for i, (page_id, page_name, page_url) in enumerate(SPECIAL_PAGES, 1):
                print(f"[{i}/{len(SPECIAL_PAGES)}] {page_name}")
                cards = crawl_special_page(driver, page_id, page_name, page_url)
                all_cards.extend(cards)

                if i < len(SPECIAL_PAGES):
                    time.sleep(INTERVAL)

            # 結果を保存
            output_file = args.output if args.output else f"dorasuta_special_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_path = OUTPUT_DIR / output_file

            result = {
                "crawled_at": datetime.now().isoformat(),
                "total_cards": len(all_cards),
                "type": "special",
                "cards": all_cards,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print()
            print(f"クロール完了")
            print(f"  合計カード数: {len(all_cards)}")
            print(f"  出力ファイル: {output_path}")

            # 状態別の内訳
            by_condition = {}
            for card in all_cards:
                cond = card.get("condition", "通常")
                by_condition[cond] = by_condition.get(cond, 0) + 1
            print(f"  内訳:")
            for cond, count in by_condition.items():
                print(f"    {cond}: {count}件")

        except Exception as e:
            print()
            print(f"エラーで停止: {e}")
            if all_cards:
                output_file = f"dorasuta_special_{datetime.now().strftime('%Y%m%d_%H%M%S')}_partial.json"
                output_path = OUTPUT_DIR / output_file
                result = {
                    "crawled_at": datetime.now().isoformat(),
                    "total_cards": len(all_cards),
                    "type": "special_partial",
                    "cards": all_cards,
                }
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"途中結果を保存: {output_path}")

        finally:
            print()
            print("5秒後にブラウザを閉じます...")
            time.sleep(5)
            driver.quit()

        return

    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 再開用の開始ページ
    resume_start_page = 1
    resume_series_id = None

    # --resume オプションの処理
    if args.resume:
        parts = args.resume.split(":")
        resume_series_id = parts[0]
        if len(parts) > 1:
            resume_start_page = int(parts[1])

        # シリーズのインデックスを検索
        start_index = None
        for idx, (sid, name) in enumerate(BS_SERIES):
            if sid == resume_series_id:
                start_index = idx
                break

        if start_index is None:
            print(f"エラー: シリーズID {resume_series_id} が見つかりません")
            return

        end_index = min(start_index + args.batch, len(BS_SERIES))
        target_series = BS_SERIES[start_index:end_index]

        print(f"再開: シリーズ {resume_series_id} のページ {resume_start_page} から")
        print(f"今回の対象: {len(target_series)} シリーズ")

    # クロール対象シリーズ
    elif args.series:
        target_series = [(sid, "") for sid in args.series]
        start_index = 0
    else:
        # 進捗から続きを取得
        start_index = load_progress()
        if start_index >= len(BS_SERIES):
            print("全シリーズのクロールが完了しています。")
            print("最初からやり直す場合は --reset を指定してください。")
            return

        end_index = min(start_index + args.batch, len(BS_SERIES))
        target_series = BS_SERIES[start_index:end_index]

        print(f"進捗: {start_index}/{len(BS_SERIES)} から再開")
        print(f"今回の対象: シリーズ {start_index + 1} 〜 {end_index}（{len(target_series)}件）")

    print(f"ドラスタクローラー開始")
    print(f"対象シリーズ数: {len(target_series)}")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")
    print()
    print("※ Cloudflareのチェックが表示されたら手動でクリックしてください")
    print()

    driver = get_driver()
    all_cards = []

    try:
        for i, (series_id, series_name) in enumerate(target_series, 1):
            print(f"[{i}/{len(target_series)}] シリーズ: {series_id} {series_name}")

            # 最初のシリーズで再開ページが指定されている場合
            if i == 1 and resume_series_id == series_id and resume_start_page > 1:
                cards = crawl_series(driver, series_id, series_name, start_page=resume_start_page)
            else:
                cards = crawl_series(driver, series_id, series_name)
            all_cards.extend(cards)

            if i < len(target_series):
                time.sleep(INTERVAL)

        # 結果を保存
        output_file = args.output if args.output else f"dorasuta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = OUTPUT_DIR / output_file

        result = {
            "crawled_at": datetime.now().isoformat(),
            "total_cards": len(all_cards),
            "series_crawled": len(target_series),
            "cards": all_cards,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 進捗を保存（--series指定時は保存しない、--resume時は更新する）
        if not args.series:
            new_progress = start_index + len(target_series)
            save_progress(new_progress)
            remaining = len(BS_SERIES) - new_progress
            print()
            print(f"クロール完了")
            print(f"  合計カード数: {len(all_cards)}")
            print(f"  出力ファイル: {output_path}")
            print()
            print(f"進捗: {new_progress}/{len(BS_SERIES)} シリーズ完了")
            if remaining > 0:
                print(f"残り: {remaining} シリーズ（次回実行で続きから）")
            else:
                print("全シリーズのクロールが完了しました！")
        else:
            print()
            print(f"クロール完了")
            print(f"  合計カード数: {len(all_cards)}")
            print(f"  出力ファイル: {output_path}")

    except Exception as e:
        print()
        print(f"エラーで停止: {e}")
        # エラー発生時も途中結果を保存
        if all_cards:
            output_file = args.output if args.output else f"dorasuta_{datetime.now().strftime('%Y%m%d_%H%M%S')}_partial.json"
            output_path = OUTPUT_DIR / output_file
            result = {
                "crawled_at": datetime.now().isoformat(),
                "total_cards": len(all_cards),
                "series_crawled": "partial",
                "cards": all_cards,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"途中結果を保存: {output_path}")
            print(f"  保存カード数: {len(all_cards)}")

    finally:
        print()
        print("5秒後にブラウザを閉じます...")
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    main()
