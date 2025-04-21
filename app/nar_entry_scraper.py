from playwright.sync_api import sync_playwright, TimeoutError
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import os
import csv
import re
import json

# ユーザーエージェントリスト
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'
]

# HTTPヘッダーのテンプレート
HEADERS_TEMPLATE = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate', 
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"'
}

# navigator.webdriverを無効化するスクリプト
WEBDRIVER_DISABLE_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
});
"""

# 指紋対策スクリプト
FINGERPRINT_PROTECT_SCRIPT = """
// Canvas指紋対策
const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type) {
    const context = originalGetContext.apply(this, arguments);
    if (type === '2d') {
        const originalGetImageData = context.getImageData;
        context.getImageData = function() {
            const imageData = originalGetImageData.apply(this, arguments);
            // 少しだけノイズを加える
            const pixels = imageData.data;
            for (let i = 0; i < pixels.length; i += 4) {
                const offset = Math.floor(Math.random() * 3);
                pixels[i] = pixels[i] + offset;
                pixels[i+1] = pixels[i+1] + offset;
                pixels[i+2] = pixels[i+2] + offset;
            }
            return imageData;
        };
    }
    return context;
};

// Audio指紋対策
const originalGetChannelData = AudioBuffer.prototype.getChannelData;
if (originalGetChannelData) {
    AudioBuffer.prototype.getChannelData = function() {
        const channelData = originalGetChannelData.apply(this, arguments);
        // 少しだけノイズを加える
        const noise = 0.0001;
        for (let i = 0; i < channelData.length; i++) {
            channelData[i] += (Math.random() * 2 - 1) * noise;
        }
        return channelData;
    };
}
"""

def scrape_race_entry(page, race_url: str, max_retries=3) -> Dict[str, any]:
    """出走表ページから情報を取得する（リトライメカニズム付き）"""
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # リトライ時は待機時間を指数関数的に増加
            if retry_count > 0:
                wait_time = 5 * (2 ** (retry_count - 1)) * (0.5 + random.random())
                print(f"リトライ {retry_count}/{max_retries}: {race_url} - {wait_time:.2f}秒待機します")
                time.sleep(wait_time)
            
            # アクセス前にランダム待機
            pre_wait = random.uniform(3, 8)
            print(f"アクセス前に {pre_wait:.2f}秒待機します")
            time.sleep(pre_wait)
            
            # タイムアウト値を延長 (60秒)
            timeout = 60000
            print(f"レースURL: {race_url} にアクセスします（タイムアウト: {timeout/1000}秒）")
            
            # リファラーを設定
            referer = 'https://nar.netkeiba.com/top/race_list.html'
            
            # Cookieの確認 - 正しくpage.contextからcookiesを取得
            try:
                cookies = page.context.cookies()
                if cookies and len(cookies) > 0:
                    print(f"{len(cookies)}個のCookieが設定されています")
            except Exception as e:
                print(f"Cookie取得時にエラー: {str(e)}")
            
            # ヒューマンライクな動作を模倣（前のページでのマウス動作など）
            page.evaluate('''() => {
                // マウスを動かすようなランダムな動き
                const events = ['mousemove', 'mousedown', 'mouseup'];
                const randomEvent = events[Math.floor(Math.random() * events.length)];
                const x = Math.floor(Math.random() * window.innerWidth);
                const y = Math.floor(Math.random() * window.innerHeight);
                const event = new MouseEvent(randomEvent, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: x,
                    clientY: y
                });
                document.body.dispatchEvent(event);
            }''')
            
            # リファラーを指定してアクセス
            page.goto(race_url, wait_until='domcontentloaded', timeout=timeout, referer=referer)
            
            # ページ読み込み後のランダム待機
            wait_time = random.uniform(3, 5)
            page.wait_for_timeout(int(wait_time * 1000))
            
            # スクロール動作を模倣
            page.evaluate('''() => {
                const scrollHeight = Math.floor(Math.random() * 300);
                window.scrollTo({
                    top: scrollHeight,
                    left: 0,
                    behavior: 'smooth'
                });
                
                // 少し時間をかけて徐々にスクロール
                setTimeout(() => {
                    window.scrollTo({
                        top: scrollHeight + Math.floor(Math.random() * 200),
                        left: 0,
                        behavior: 'smooth'
                    });
                }, Math.floor(Math.random() * 1000) + 500);
            }''')
            
            # さらに待機
            page.wait_for_timeout(random.randint(1000, 2000))
            
            # race_idを取得（URLから）
            race_id = race_url.split('race_id=')[1].split('&')[0]
            
            entry_info = {
                'race_name': '',
                'race_number': '',
                'race_id': race_id,  # dateの代わりにrace_idを使用
                'venue_name': '',
                'start_time': '',
                'course_info': '',
                'race_details': '',
                'entries': []  # 出走馬情報（results → entries に変更）
            }
            
            # レース名と番号を取得
            race_name_elem = page.query_selector('.RaceList_Item02 .RaceName')
            if race_name_elem:
                entry_info['race_name'] = race_name_elem.inner_text().strip()
            
            race_number_elem = page.query_selector('.Race_Num')
            if race_number_elem:
                entry_info['race_number'] = race_number_elem.inner_text().replace('R', '').strip()
            
            # 開催場所
            venue_elem = page.query_selector('.RaceData02 span:nth-child(2)')
            if venue_elem:
                entry_info['venue_name'] = venue_elem.inner_text().strip()
            
            # 発走時刻
            time_elem = page.query_selector('.RaceData01')
            if time_elem:
                time_text = time_elem.inner_text().split('発走')[0].strip()
                entry_info['start_time'] = time_text
            
            # コース情報
            course_elem = page.query_selector('.RaceData01 span')
            if course_elem:
                entry_info['course_info'] = course_elem.inner_text().strip()
            
            # レース詳細情報を取得して余分なスペースを削除
            race_details_elem = page.query_selector('.Race_Data')
            if race_details_elem:
                # 改行を削除し、連続する空白を1つの空白に置換
                race_details = ' '.join([
                    part.strip()
                    for part in race_details_elem.inner_text().strip().split()
                    if part.strip()
                ])
                # 全角スペースも半角スペースに統一
                race_details = race_details.replace('　', ' ')
                # "C1" と "12頭" の間の余分なスペースを削除
                race_details = re.sub(r'([A-Z][0-9])\s+(\d+頭)', r'\1 \2', race_details)
                entry_info['race_details'] = race_details
            else:
                entry_info['race_details'] = ''
            
            # 出走馬情報を取得前にさらにスクロール
            page.evaluate('''() => {
                window.scrollTo({
                    top: 400,
                    left: 0,
                    behavior: 'smooth'
                });
            }''')
            
            # 少し待機
            page.wait_for_timeout(random.randint(1000, 2000))
            
            # 出走馬情報を取得
            horse_rows = page.query_selector_all('tr.HorseList')
            print(f"Found {len(horse_rows)} horse rows")
            
            # 各行を処理する前に、ランダムな待機を入れる
            row_delay = random.uniform(0.2, 0.5)
            
            for row in horse_rows:
                horse_data = {}
                
                # 馬番
                horse_number = row.query_selector('td.Umaban1, td.Umaban2, td.Umaban3, td.Umaban4, td.Umaban5, td.Umaban6, td.Umaban7, td.Umaban8')
                if horse_number:
                    horse_data['horse_number'] = horse_number.inner_text().strip()
                
                # 馬名
                horse_name = row.query_selector('.HorseName a')
                if horse_name:
                    horse_data['horse_name'] = horse_name.inner_text().strip()
                
                # 性齢
                sex_age = row.query_selector('.Age')
                if sex_age:
                    horse_data['sex_age'] = sex_age.inner_text().strip()
                
                # 斤量 - セレクタを修正
                weight = row.query_selector('td.Txt_C:nth-child(6)')  # 6番目のtd要素を指定
                if weight:
                    horse_data['weight'] = weight.inner_text().strip()
                
                # 騎手
                jockey = row.query_selector('.Jockey a')
                if jockey:
                    horse_data['jockey_name'] = jockey.inner_text().strip()
                
                # 調教師
                trainer = row.query_selector('.Trainer a:nth-child(2)')  # 2番目のaタグを選択
                if trainer:
                    horse_data['trainer_name'] = trainer.inner_text().strip()

                # オッズと人気を取得
                odds_td = row.query_selector('.Popular.Txt_R')
                if odds_td:
                    odds_text = odds_td.inner_text().strip()
                    if odds_text:
                        horse_data['odds'] = odds_text.split('\n')[0]

                # 人気
                popularity = row.query_selector('.Popular.Txt_C span')
                if popularity:
                    horse_data['popularity'] = popularity.inner_text().strip()

                print(f"Debug - Horse data: {horse_data}")
                entry_info['entries'].append(horse_data)
                
                # 各行の処理間に短いランダム待機（ボット検出回避）
                time.sleep(row_delay)
            
            # 出走馬情報が取得できていることを確認
            if len(entry_info['entries']) > 0:
                print(f"レースデータ取得成功: {entry_info['venue_name']} {entry_info['race_number']}R - 出走頭数: {len(entry_info['entries'])}")
                return entry_info
            else:
                # 出走馬情報が取得できていない場合はリトライ
                print(f"出走馬情報が取得できませんでした: {race_url} - リトライします")
                retry_count += 1
                continue
                
        except TimeoutError as e:
            print(f"タイムアウトエラー: {race_url} - {str(e)}")
            retry_count += 1
        except Exception as e:
            print(f"レース情報取得中にエラー: {str(e)}")
            retry_count += 1
    
    print(f"最大リトライ回数を超えました: {race_url}")
    return None

def save_to_csv(race_entry: Dict[str, any]):
    """レース情報をCSVに保存する（1レース1行）"""
    # 保存先ディレクトリの作成
    os.makedirs('data/race_entries', exist_ok=True)
    current_date = datetime.now().strftime('%Y%m%d')
    filename = f'data/race_entries/nar_race_entries_{current_date}.csv'
    
    # ファイルが存在しない場合は新規作成
    file_exists = os.path.isfile(filename)
    
    # レース詳細情報から余分なスペースと改行を削除
    race_details = ' '.join(race_entry['race_details'].split())
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # ヘッダーを書き込む（ファイルが新規の場合のみ）
        if not file_exists:
            writer.writerow([
                'race_id', 'race_name', 'race_number', 'venue_name', 
                'start_time', 'course_info', 'race_details', 'entries'
            ])
        
        # レース情報を1行で書き込む
        writer.writerow([
            race_entry['race_id'],
            race_entry['race_name'],
            race_entry['race_number'],
            race_entry['venue_name'],
            race_entry['start_time'],
            race_entry['course_info'],
            race_details,
            json.dumps(race_entry['entries'], ensure_ascii=False)  # 出走馬情報をJSON形式で保存
        ])

def get_race_urls_for_date(page, context, date_str: str, max_retries=3) -> List[str]:
    """指定日の全レースの出馬表URLを取得（リトライメカニズム付き）"""
    all_race_urls = []
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
            print(f"\n{date_str}のレース情報を取得中...")
            
            # リトライ時は待機時間を指数関数的に増加
            if retry_count > 0:
                wait_time = 10 * (2 ** (retry_count - 1)) * (0.5 + random.random())
                print(f"リトライ {retry_count}/{max_retries}: {date_str} - {wait_time:.2f}秒待機します")
                time.sleep(wait_time)
                
            # タイムアウト設定を延長
            timeout = 90000  # 90秒
            page.set_default_timeout(timeout)
            
            # サイトアクセス前にランダム待機
            pre_wait = random.uniform(10, 15)
            print(f"サイトアクセス前に{pre_wait:.2f}秒待機します...")
            time.sleep(pre_wait)
            
            # まずトップページにアクセス
            print("トップページにアクセスしています...")
            try:
                # Cookieの消去とブラウザキャッシュのクリア
                context.clear_cookies()
                
                # クッキー同意画面を回避するための設定
                page.goto("https://nar.netkeiba.com/", wait_until='domcontentloaded', timeout=timeout)
                
                # ヒューマンライクな遅延を模倣
                page.wait_for_timeout(random.randint(3000, 5000))
                
                # スクロールして人間らしい動きを模倣
                page.evaluate('''() => {
                    window.scrollTo(0, Math.floor(Math.random() * 100));
                    setTimeout(() => {
                        window.scrollTo(0, Math.floor(Math.random() * 300));
                    }, Math.floor(Math.random() * 1000) + 500);
                }''')
                
                page.wait_for_timeout(1000)
                
            except TimeoutError as e:
                print(f"トップページアクセスエラー (試行 {retry_count+1}/{max_retries+1}): {str(e)}")
                retry_count += 1
                continue
            
            # 次に目的のページに遷移
            print(f"レース一覧ページにアクセスしています: {url}")
            try:
                # URL変更前にランダムな動きを挿入
                page.evaluate('''() => {
                    // マウスを動かすようなランダムな動き
                    const events = ['mousemove', 'mousedown', 'mouseup'];
                    const randomEvent = events[Math.floor(Math.random() * events.length)];
                    const x = Math.floor(Math.random() * window.innerWidth);
                    const y = Math.floor(Math.random() * window.innerHeight);
                    const event = new MouseEvent(randomEvent, {
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        clientX: x,
                        clientY: y
                    });
                    document.body.dispatchEvent(event);
                }''')
                
                # リファラーを設定してページ遷移
                page.goto(url, wait_until='domcontentloaded', timeout=timeout, referer='https://nar.netkeiba.com/')
                page.wait_for_timeout(5000)
                
                # スクロールを模倣
                page.evaluate('''() => {
                    window.scrollTo({
                        top: 100,
                        left: 0,
                        behavior: 'smooth'
                    });
                }''')
                
            except TimeoutError:
                print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
            
            # JavaScriptを実行してページの準備ができているか確認
            is_ready = page.evaluate('''() => {
                return document.querySelector('.RaceList_ProvinceSelect') !== null;
            }''')
            
            if not is_ready:
                print("ページの準備ができていません。さらに待機します...")
                page.wait_for_timeout(5000)
                
                # 再度確認
                is_ready = page.evaluate('''() => {
                    return document.querySelector('.RaceList_ProvinceSelect') !== null;
                }''')
                
                if not is_ready:
                    print("ページの準備ができていません。リトライします")
                    retry_count += 1
                    continue
            
            venues = page.query_selector_all('.RaceList_ProvinceSelect li')
            print(f"開催場所数: {len(venues)}")
            
            if len(venues) == 0:
                print("開催場所が見つかりませんでした。リトライします")
                retry_count += 1
                continue
            
            for venue in venues:
                try:
                    venue_name = venue.inner_text().strip()
                    print(f"\n開催場所: {venue_name}")
                    
                    venue_link = venue.query_selector('a')
                    if venue_link:
                        href = venue_link.get_attribute('href')
                        venue_url = f"https://nar.netkeiba.com/top/race_list.html{href}"
                        print(f"開催場所URL: {venue_url}")
                        
                        # 各開催場所ページアクセス前にランダム待機
                        venue_wait = random.uniform(3, 6)
                        print(f"開催場所ページアクセス前に {venue_wait:.2f}秒待機します")
                        time.sleep(venue_wait)
                        
                        # 新しいページを作成
                        venue_page = context.new_page()
                        
                        try:
                            # ランダムなユーザーエージェントを選択
                            random_ua = random.choice(USER_AGENTS)
                            headers = HEADERS_TEMPLATE.copy()
                            headers['User-Agent'] = random_ua
                            
                            # ヘッダーを設定
                            venue_page.set_extra_http_headers(headers)
                            
                            # webdriver検出回避スクリプトを実行
                            venue_page.add_init_script(WEBDRIVER_DISABLE_SCRIPT)
                            venue_page.add_init_script(FINGERPRINT_PROTECT_SCRIPT)
                            
                            # リファラーを設定してページ遷移
                            venue_page.goto(venue_url, wait_until='domcontentloaded', timeout=timeout, referer=url)
                            
                            # ヒューマンライクな待機と動作
                            venue_page.wait_for_timeout(random.randint(2000, 4000))
                            
                            # スクロールを模倣
                            venue_page.evaluate('''() => {
                                window.scrollTo({
                                    top: Math.random() * 200,
                                    left: 0,
                                    behavior: 'smooth'
                                });
                            }''')
                            
                            venue_page.wait_for_timeout(1000)
                            
                            # レース情報を取得
                            races = venue_page.query_selector_all('dl.RaceList_DataList')
                            for race in races:
                                race_links = race.query_selector_all('a[href*="/race/shutuba.html"]')
                                for link in race_links:
                                    href = link.get_attribute('href')
                                    if href:
                                        race_url = f"https://nar.netkeiba.com{href.replace('..', '')}"
                                        all_race_urls.append(race_url)
                                        print(f"レースURL追加: {race_url}")
                                        
                        finally:
                            venue_page.close()
                            
                except Exception as e:
                    print(f"開催場所の処理中にエラー: {str(e)}")
                    continue
            
            # URLが取得できればループを抜ける    
            if len(all_race_urls) > 0:
                return all_race_urls
            else:
                print(f"レースURLが取得できませんでした: {date_str} - リトライします")
                retry_count += 1
                
        except Exception as e:
            print(f"レースURL取得中にエラー: {str(e)}")
            retry_count += 1
    
    print(f"最大リトライ回数を超えました: {date_str}")
    return all_race_urls

def get_race_info_for_next_three_days() -> List[Dict[str, any]]:
    """今日から3日分のレース情報を取得"""
    all_race_entries = []
    today = datetime.now()
    
    with sync_playwright() as p:
        # ブラウザの起動設定を強化
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--hide-scrollbars',
                '--mute-audio',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-component-extensions-with-background-pages',
                '--disable-extensions',
                '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                '--disable-ipc-flooding-protection',
                '--disable-renderer-backgrounding',
                '--enable-features=NetworkService,NetworkServiceInProcess',
                '--force-color-profile=srgb',
                '--metrics-recording-only',
            ]
        )
        
        # ランダムなユーザーエージェントを選択
        user_agent = random.choice(USER_AGENTS)
        print(f"使用するユーザーエージェント: {user_agent}")
        
        # HTTPヘッダーのコピーを作成し、User-Agentを設定
        headers = HEADERS_TEMPLATE.copy()
        headers['User-Agent'] = user_agent
        
        # 本物のブラウザに近いコンテキスト設定
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=user_agent,
            extra_http_headers=headers,
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            geolocation={'latitude': 35.6762, 'longitude': 139.6503},  # 東京
            permissions=['geolocation'],
            color_scheme='light',
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            java_script_enabled=True,
            bypass_csp=True
        )
        
        try:
            # webdriver検出回避スクリプトとフィンガープリント保護を追加
            page = context.new_page()
            page.add_init_script(WEBDRIVER_DISABLE_SCRIPT)
            page.add_init_script(FINGERPRINT_PROTECT_SCRIPT)
            
            for i in range(3):
                target_date = today + timedelta(days=i)
                date_str = target_date.strftime("%Y%m%d")
                print(f"\n{date_str}のレース情報の取得を開始します...")
                
                race_urls = get_race_urls_for_date(page, context, date_str)
                print(f"取得したレースURL数: {len(race_urls)}")
                
                # 各レースの情報を取得してすぐにCSVに保存
                for idx, race_url in enumerate(race_urls):
                    race_entry = scrape_race_entry(page, race_url)
                    if race_entry:
                        save_to_csv(race_entry)
                        print(f"レース情報保存: {race_entry['venue_name']} {race_entry['race_number']}R")
                    
                    # レース間のランダム待機（レート制限回避）
                    if idx < len(race_urls) - 1:  # 最後のレースでなければ
                        wait_time = random.uniform(5, 10)
                        print(f"次のレース取得まで {wait_time:.2f}秒待機します")
                        time.sleep(wait_time)
                
                # 日付間の待機
                if i < 2:  # 最後の日付でなければ
                    wait_time = random.uniform(15, 20)
                    print(f"次の日付の処理まで {wait_time:.2f}秒待機します")
                    time.sleep(wait_time)
                    
        finally:
            context.close()
            browser.close()
    
    return all_race_entries

if __name__ == '__main__':
    print("地方競馬出走表の取得を開始します...")
    
    # 3日分のレース情報を取得
    all_race_entries = get_race_info_for_next_three_days()
    
    # 全レース情報をCSVに保存
    if all_race_entries:
        print(f"\n取得したレース数: {len(all_race_entries)}")
        for race_entry in all_race_entries:
            save_to_csv(race_entry)