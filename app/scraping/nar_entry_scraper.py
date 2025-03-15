from playwright.sync_api import sync_playwright, TimeoutError
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd
import os
import csv
import re
import json
from app import app, db
from app.models import Race, Horse, Jockey, ShutubaEntry
import traceback
import argparse

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
        # タイムアウト時間を延長し、リトライを追加
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                print(f"レースURL: {race_url} にアクセス中... (試行 {retry_count + 1}/{max_retries})")
                page.goto(race_url, wait_until='domcontentloaded', timeout=60000)  # タイムアウトを60秒に延長
                page.wait_for_timeout(5000)  # 待機時間を増やす
                break  # 成功したらループを抜ける
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise  # 最大リトライ回数に達したら例外を投げる
                print(f"アクセス失敗、{retry_count}/{max_retries}回目のリトライ: {str(e)}")
                page.wait_for_timeout(10000)  # リトライ前に10秒待機
        
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

def save_to_csv(race_entries: List[Dict[str, Any]], filename: str = None):
    """レース情報をCSVに保存する"""
    if not race_entries:
        print("保存するレース情報がありません")
        return None
    
    # ファイル名が指定されていない場合は日付から生成
    if not filename:
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"race_entries_{date_str}.csv"
    
    try:
        # DataFrameに変換
        df = pd.DataFrame(race_entries)
        
        # entriesカラムをJSON文字列に変換
        df['entries'] = df['entries'].apply(lambda x: json.dumps(x, ensure_ascii=False))
        
        # CSVに保存
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"レース情報をCSVに保存しました: {filename}")
        return filename
    except Exception as e:
        print(f"CSV保存エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得（重複なし）"""
    all_race_urls = set()  # セットを使用して重複を防ぐ
    
    try:
        url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        print(f"\n{date_str}のレース情報を取得中...")
        
        # タイムアウトを設定
        page.set_default_timeout(60000)
        
        # まずトップページにアクセス
        print("トップページにアクセスしています...")
        page.goto("https://nar.netkeiba.com/", wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # 次に目的のページに遷移
        print(f"レース一覧ページにアクセスしています: {url}")
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except TimeoutError:
            print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
        
        page.wait_for_timeout(5000)
        
        # 日付ページから直接すべてのレースリンクを取得
        print("すべてのレースリンクを取得しています...")
        race_links = page.query_selector_all('a[href*="/race/shutuba.html"]')
        print(f"レースリンク数: {len(race_links)}")
        
        for link in race_links:
            href = link.get_attribute('href')
            if href:
                # 相対パスを絶対パスに変換
                if href.startswith('/'):
                    race_url = f"https://nar.netkeiba.com{href}"
                else:
                    race_url = f"https://nar.netkeiba.com{href.replace('..', '')}"
                
                # セットに追加（自動的に重複排除）
                all_race_urls.add(race_url)
        
        print(f"重複排除後のレースURL数: {len(all_race_urls)}")
                
    except Exception as e:
        print(f"レースURL取得中にエラー: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return list(all_race_urls)  # セットをリストに変換して返す

def get_race_info_for_next_three_days():
    """今日から3日分のレース情報を取得"""
    try:
        with sync_playwright() as p:
            # 並列処理のために複数のブラウザを起動
            browser_options = {
                'headless': True,
                'args': ['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox']
            }
            browser = p.chromium.launch(**browser_options)
            
            # 日付ごとに並列処理
            contexts = []
            pages = []
            
            # 各日付用のコンテキストとページを作成
            for i in range(3):
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                contexts.append(context)
                pages.append(context.new_page())
            
            # 各日付の処理を開始
            for i in range(3):
                target_date = datetime.now() + timedelta(days=i)
                date_str = target_date.strftime("%Y%m%d")
                filename = f"nar_race_entries_{date_str}.csv"
                
                print(f"\n{date_str}の処理を開始します...")
                
                # 待機時間を短縮
                pages[i].set_default_timeout(30000)
                race_urls = get_race_urls_for_date(pages[i], contexts[i], date_str)
                print(f"{date_str}のレースURL数: {len(race_urls)}")
                
                # 各レースの処理
                if race_urls:
                    for race_url in race_urls:
                        race_entry = scrape_race_entry(pages[i], race_url)
                        if race_entry:
                            save_to_csv([race_entry], filename)
                            print(f"保存完了: {race_entry['venue_name']} {race_entry['race_number']}R")
                        # 待機時間を短縮
                        pages[i].wait_for_timeout(1000)
            
            # クリーンアップ
            for context in contexts:
                context.close()
            browser.close()
                
    except Exception as e:
        print(f"処理エラー: {str(e)}")
        import traceback
        traceback.print_exc()

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
        page = browser.new_page()
        
        # NAR（地方競馬）のトップページにアクセス
        page.goto("https://www.keiba.go.jp/")
        
        # 日付選択
        # ... (日付選択の処理)
        
        # レース一覧を取得
        # ... (レース一覧の取得処理)
        
        # 各レースの出走表を取得
        for race_url in race_urls:
            try:
                entry_info = scrape_race_entry(page, race_url)
                if entry_info and entry_info['race_id']:
                    race_entries.append(entry_info)
                    print(f"レース情報を取得しました: {entry_info['race_name']}")
            except Exception as e:
                print(f"レース情報の取得中にエラー: {str(e)}")
        
        browser.close()
    
    print(f"{len(race_entries)}件のレース情報を取得しました")
    return race_entries

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='地方競馬の出走表をスクレイピングする')
    parser.add_argument('--date', type=str, help='対象日付（YYYYMMDD形式）')
    parser.add_argument('--output', type=str, help='出力CSVファイルのパス')
    args = parser.parse_args()
    
    # スクレイピングの実行
    race_entries = scrape_race_entries(args.date)
    
    # CSVに保存
    if race_entries:
        save_to_csv(race_entries, args.output)
    else:
        print("保存するレース情報がありません")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())