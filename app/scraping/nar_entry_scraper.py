from playwright.sync_api import sync_playwright, TimeoutError
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import os
import csv
import re
import json
from app import app, db
from app.models import Race, Horse, Jockey, ShutubaEntry
import traceback
import sys
import random

# ユーザーエージェントのリスト
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def generate_race_id(race_url: str) -> str:
    """レースURLからレースIDを生成（15桁）"""
    try:
        # URLからrace_idパラメータを抽出
        race_id = race_url.split('race_id=')[1].split('&')[0]
        return race_id
    except Exception as e:
        print(f"レースID生成エラー: {str(e)}")
        return None

def generate_venue_code(venue_name: str) -> str:
    """開催場所から3桁のコードを生成"""
    venue_codes = {
        '札幌': '101',
        '函館': '102',
        '福島': '103',
        '新潟': '104',
        '東京': '105',
        '中山': '106',
        '中京': '107',
        '京都': '108',
        '阪神': '109',
        '小倉': '110',
        '門別': '201',
        '帯広': '202',
        '盛岡': '203',
        '水沢': '204',
        '浦和': '205',
        '船橋': '206',
        '大井': '207',
        '川崎': '208',
        '金沢': '209',
        '笠松': '210',
        '名古屋': '211',
        '園田': '212',
        '姫路': '213',
        '高知': '214',
        '佐賀': '215'
    }
    return venue_codes.get(venue_name, '299')  # 不明な場合は299を返す

def generate_entry_id(race_id, horse_number):
    """
    エントリーIDの生成（17桁）
    レースID(15桁) + 馬番(2桁)の形式
    例: レースID=202401011010112, 馬番=7 の場合
    → 20240101101011207
    """
    try:
        return int(f"{race_id}{str(int(horse_number)).zfill(2)}")
    except:
        return None

def generate_horse_id(horse_name: str) -> str:
    """馬IDを生成（10桁）"""
    if not hasattr(generate_horse_id, 'used_ids'):
        generate_horse_id.used_ids = set()
        generate_horse_id.name_to_id = {}

    if horse_name in generate_horse_id.name_to_id:
        return generate_horse_id.name_to_id[horse_name]

    name_hash = 0
    for i, char in enumerate(horse_name):
        position_weight = (i + 1) * 100
        char_value = ord(char) * position_weight
        name_hash = (name_hash * 31 + char_value) & 0xFFFFFFFF

    base_id = int(f"1{abs(name_hash) % 999999999:09d}")

    while base_id in generate_horse_id.used_ids:
        base_id += 1
        if base_id % 1000000000 == 0:
            base_id = 1000000000

    generate_horse_id.used_ids.add(base_id)
    generate_horse_id.name_to_id[horse_name] = base_id

    return str(base_id)

def generate_jockey_id(jockey_name: str) -> str:
    """騎手IDを生成（10桁）"""
    if not hasattr(generate_jockey_id, 'used_ids'):
        generate_jockey_id.used_ids = set()
        generate_jockey_id.name_to_id = {}

    if jockey_name in generate_jockey_id.name_to_id:
        return generate_jockey_id.name_to_id[jockey_name]

    name_hash = sum(ord(c) for c in jockey_name)
    base_id = int(f"2{abs(name_hash) % 999999999:09d}")

    while base_id in generate_jockey_id.used_ids:
        base_id += 1
        if base_id % 1000000000 == 0:
            base_id = 2000000000

    generate_jockey_id.used_ids.add(base_id)
    generate_jockey_id.name_to_id[jockey_name] = base_id

    return str(base_id)

def scrape_race_entry(page, race_url: str) -> Dict[str, any]:
    """出走表ページから情報を取得する"""
    try:
        # Cookieの確認を試みる
        try:
            cookies = page.context.cookies()
            if cookies and len(cookies) > 0:
                print(f"{len(cookies)}個のCookieが設定されています")
        except Exception as e:
            print(f"Cookie取得時にエラー: {str(e)}")
            
        page.goto(race_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
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
        else:
            race_details = ''
        
        # 出走馬情報を取得
        horse_rows = page.query_selector_all('tr.HorseList')
        print(f"Found {len(horse_rows)} horse rows")
        
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
        
        return entry_info
        
    except Exception as e:
        print(f"レース情報取得中にエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def save_to_csv(race_entry: Dict[str, any], filename: str = None):
    """
    レース情報をCSVに保存する
    
    Args:
        race_entry: 保存するレース情報
        filename: 保存するファイル名（指定がない場合は現在の日付を使用）
    """
    try:
        # データディレクトリの作成
        os.makedirs('data/race_entries', exist_ok=True)
        
        # ファイル名の処理
        if filename is None:
            # 指定がない場合は現在の日付を使用
            current_date = datetime.now().strftime('%Y%m%d')
            filepath = f'data/race_entries/nar_race_entries_{current_date}.csv'
        elif '/' in filename or '\\' in filename:
            # 既にパスが含まれている場合はそのまま使用
            filepath = filename
        else:
            # ファイル名のみの場合はパスを追加
            filepath = f'data/race_entries/{filename}'
        
        # ファイルが存在するか確認
        file_exists = os.path.isfile(filepath)
        
        # レース詳細情報から余分なスペースを削除
        race_details = ' '.join(race_entry.get('race_details', '').split())
        
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # ヘッダーを書き込む（ファイルが新規の場合のみ）
            if not file_exists:
                writer.writerow([
                    'race_id', 'race_name', 'race_number', 'venue_name', 
                    'start_time', 'course_info', 'race_details', 'entries'
                ])
            
            # レース情報を1行で書き込む
            writer.writerow([
                race_entry.get('race_id', ''),
                race_entry.get('race_name', ''),
                race_entry.get('race_number', ''),
                race_entry.get('venue_name', ''),
                race_entry.get('start_time', ''),
                race_entry.get('course_info', ''),
                race_details,
                json.dumps(race_entry.get('entries', []), ensure_ascii=False)  # 出走馬情報をJSON形式で保存
            ])
            
        print(f"CSVに保存しました: {filepath}")
            
    except Exception as e:
        print(f"CSV保存エラー: {str(e)}")
        import traceback
        traceback.print_exc()

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得"""
    all_race_urls = set()  # セットを使用して重複を防止
    try:
        url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        print(f"\n{date_str}のレース情報を取得中...")
        
        # タイムアウトを設定
        page.set_default_timeout(60000)  # 60秒
        
        # アクセス制限対策としてCookieをクリア
        context.clear_cookies()
        
        # サーバー負荷軽減のためより長い待機時間を設定
        initial_wait = random.randint(10000, 15000)  # 10-15秒の待機
        print(f"サイトアクセス前に{initial_wait/1000}秒待機します...")
        page.wait_for_timeout(initial_wait)
        
        # まずトップページにアクセス（再試行ロジック追加）
        print("トップページにアクセスしています...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                page.goto("https://nar.netkeiba.com/", wait_until='domcontentloaded', timeout=60000)
                break
            except Exception as e:
                print(f"トップページアクセスエラー (試行 {attempt+1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise
                # リトライ前に長めに待機（アクセス制限対策）
                retry_wait = random.randint(20000, 30000)  # 20-30秒
                print(f"再試行前に{retry_wait/1000}秒待機...")
                page.wait_for_timeout(retry_wait)
                
                # 新しいページを作成して再試行
                page.close()
                page = context.new_page()
        
        # 一定時間待機
        wait_time = random.randint(5000, 10000)  # 5-10秒
        print(f"トップページ読み込み後、{wait_time/1000}秒待機します...")
        page.wait_for_timeout(wait_time)
        
        # JavaScriptを実行してページの準備ができているか確認
        is_ready = page.evaluate('''() => {
            return document.querySelector('.RaceList_ProvinceSelect') !== null;
        }''')
        
        if not is_ready:
            print("ページの準備ができていません。さらに待機します...")
            page.wait_for_timeout(5000)
        
        # 直接メインページからすべてのレースURLを取得
        race_links = page.query_selector_all('a[href*="/race/shutuba.html"]')
        print(f"取得したリンク数: {len(race_links)}")
        
        for link in race_links:
            href = link.get_attribute('href')
            if href:
                race_url = f"https://nar.netkeiba.com{href.replace('..', '')}"
                all_race_urls.add(race_url)  # セットに追加
                print(f"レースURL追加: {race_url}")
        
        print(f"メインページから{len(all_race_urls)}件のレースURLを取得しました")
        
    except Exception as e:
        print(f"レースURL取得中にエラー: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return list(all_race_urls)  # セットをリストに変換して返す

def get_race_info_for_next_three_days():
    """今日から3日分のレース情報を取得"""
    try:
        with sync_playwright() as p:
            # プロキシ設定（必要に応じて値を設定）
            # proxy_host = os.environ.get('PROXY_HOST', None)
            # proxy_port = os.environ.get('PROXY_PORT', None)
            # プロキシ設定
            browser_options = {
                'headless': True,
                # 'proxy': {
                #     'server': f'http://{proxy_host}:{proxy_port}' if proxy_host and proxy_port else None
                # }
            }
            
            # ブラウザの起動
            browser = p.chromium.launch(**browser_options)
            
            # ランダムなユーザーエージェントを選択
            user_agent = random.choice(USER_AGENTS)
            
            # 追加されたカスタムヘッダー
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            )
            
            try:
                page = context.new_page()
                
                for i in range(3):
                    target_date = datetime.now() + timedelta(days=i)
                    date_str = target_date.strftime("%Y%m%d")
                    filename = f"nar_race_entries_{date_str}.csv"
                    
                    print(f"\n{date_str}の処理を開始します...")
                    
                    try:
                        race_urls = get_race_urls_for_date(page, context, date_str)
                        print(f"{date_str}のレースURL数: {len(race_urls)}")
                        
                        if race_urls:  # レースURLが存在する場合のみ処理
                            total_races = len(race_urls)
                            processed_races = 0
                            
                            for race_url in race_urls:
                                try:
                                    race_entry = scrape_race_entry(page, race_url)
                                    if race_entry and race_entry.get('entries') and len(race_entry.get('entries', [])) > 0:
                                        save_to_csv(race_entry, filename)
                                        processed_races += 1
                                        print(f"保存完了: {race_entry.get('venue_name', '不明')} {race_entry.get('race_number', '?')}R ({processed_races}/{total_races})")
                                    
                                    # アクセス間隔を開ける（サーバー負荷軽減）
                                    wait_time = random.uniform(3, 7)
                                    print(f"次のレース取得まで {wait_time:.2f}秒待機します")
                                    time.sleep(wait_time)
                                    
                                except Exception as e:
                                    print(f"レース情報取得エラー: {str(e)}")
                                    traceback.print_exc()
                                    
                            print(f"{date_str}の処理が完了しました - {processed_races}/{total_races}件のレース情報を保存")
                        else:
                            print(f"{date_str}のレースはありません")
                            
                        # 日付間の待機（最後の日付の場合は不要）
                        if i < 2:
                            wait_time = random.uniform(15, 25)
                            print(f"次の日付の処理まで {wait_time:.2f}秒待機します")
                            time.sleep(wait_time)
                            
                    except Exception as e:
                        print(f"{date_str}の処理中にエラーが発生しました: {str(e)}")
                        traceback.print_exc()
                
            finally:
                try:
                    context.close()
                    browser.close()
                except Exception as e:
                    print(f"ブラウザクローズ中にエラーが発生: {str(e)}")
                
    except Exception as e:
        print(f"処理エラー: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def scrape_race_entries(date_str=None):
    """指定された日付のレース出走表をスクレイピング"""
    # 日付が指定されていない場合は今日の日付を使用
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')
    
    # 日付の形式を確認
    try:
        target_date = datetime.strptime(date_str, '%Y%m%d')
        formatted_date = target_date.strftime('%Y年%m月%d日')
    except ValueError:
        print(f"エラー: 無効な日付形式です: {date_str}")
        return []
    
    print(f"{formatted_date}のレース出走表をスクレイピングします...")
    
    race_entries = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # ここを修正: get_race_urls → get_race_urls_for_date
        race_urls = get_race_urls_for_date(page, context, date_str)
        print(f"{len(race_urls)}件のレースURLを取得しました")
        
        # 各レースの出走表を取得
        for race_url in race_urls:
            try:
                entry_info = scrape_race_entry(page, race_url)
                if entry_info:
                    race_entries.append(entry_info)
                    print(f"レース情報を取得しました: {entry_info.get('race_name', '不明')}")
            except Exception as e:
                print(f"レース情報取得エラー: {str(e)}")
        
        browser.close()
    
    print(f"{len(race_entries)}件のレース情報を取得しました")
    return race_entries

if __name__ == '__main__':
    print("地方競馬出走表の取得を開始します...")
    success = get_race_info_for_next_three_days()
    if success:
        print("スクレイピングが正常に完了しました")
        sys.exit(0)
    else:
        print("スクレイピングに失敗しました")
        sys.exit(1)