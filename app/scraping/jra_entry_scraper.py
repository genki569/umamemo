#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中央競馬（JRA）の出馬表をスクレイピングするスクリプト
netkeiba.comから中央競馬の出馬表データを取得し、CSVファイルに保存します。
"""

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
    """開催場所から3桁のコードを生成（中央競馬用）"""
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
        '小倉': '110'
    }
    return venue_codes.get(venue_name, '199')  # 不明な場合は199を返す

def generate_entry_id(race_id, horse_number):
    """
    エントリーIDの生成（17桁）
    レースID(15桁) + 馬番(2桁)の形式
    例: レースID=202501010101, 馬番=7 の場合
    → 20250101010107
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
        # User-Agentとリファラーを設定してアクセス
        page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
            'Referer': 'https://race.netkeiba.com/top/'
        })
        
        page.goto(race_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
        # race_idを取得（URLから）
        race_id = race_url.split('race_id=')[1].split('&')[0]
        
        entry_info = {
            'race_name': '',
            'race_number': '',
            'race_id': race_id,
            'venue_name': '',
            'start_time': '',
            'course_info': '',
            'race_details': '',
            'entries': []
        }
        
        # レース名を取得
        race_name_elem = page.query_selector('.RaceName')
        if race_name_elem:
            entry_info['race_name'] = race_name_elem.inner_text().strip()
        
        # レース番号を取得
        race_number_elem = page.query_selector('.RaceNum')
        if race_number_elem:
            race_number_text = race_number_elem.inner_text().strip()
            entry_info['race_number'] = race_number_text.replace('R', '').strip()
        
        # 開催場所を取得
        venue_elem = page.query_selector('.RaceData01 span:first-child')
        if venue_elem:
            venue_text = venue_elem.inner_text().strip()
            # 例: "東京11R" から "東京" を抽出
            venue_match = re.match(r'([^\d]+)', venue_text)
            if venue_match:
                entry_info['venue_name'] = venue_match.group(1).strip()
        
        # 発走時刻を取得
        start_time_elem = page.query_selector('.RaceData01 span.Race_Date')
        if start_time_elem:
            start_time_text = start_time_elem.inner_text().strip()
            # 例: "15:35発走" から "15:35" を抽出
            time_match = re.match(r'(\d+:\d+)発走', start_time_text)
            if time_match:
                entry_info['start_time'] = time_match.group(1)
        
        # コース情報を取得
        course_elem = page.query_selector('.RaceData01')
        if course_elem:
            course_text = course_elem.inner_text().strip()
            # コース情報を整形（例: "芝1200m 右 外" → "芝1200m 右 外"）
            course_match = re.search(r'(芝|ダ)[^\d]*(\d+)m', course_text)
            if course_match:
                course_type = '芝' if course_match.group(1) == '芝' else 'ダート'
                distance = course_match.group(2)
                entry_info['course_info'] = f"{course_type}{distance}m"
                
                # 右回り・左回りの情報も追加
                if '右' in course_text:
                    entry_info['course_info'] += ' 右'
                elif '左' in course_text:
                    entry_info['course_info'] += ' 左'
        
        # レース詳細情報を取得
        race_details_elem = page.query_selector('.RaceData02')
        if race_details_elem:
            race_details = race_details_elem.inner_text().strip()
            # 余分なスペースを削除して整形
            race_details = ' '.join(race_details.split())
            entry_info['race_details'] = race_details
        
        # 出走馬情報を取得
        horse_rows = page.query_selector_all('table.Shutuba_Table tr.HorseList')
        print(f"Found {len(horse_rows)} horse rows")
        
        for row in horse_rows:
            horse_data = {}
            
            # 枠番と馬番
            bracket_elem = row.query_selector('td.Waku span')
            if bracket_elem:
                horse_data['bracket_number'] = bracket_elem.inner_text().strip()
            
            horse_number_elem = row.query_selector('td.Umaban')
            if horse_number_elem:
                horse_data['horse_number'] = horse_number_elem.inner_text().strip()
            
            # 馬名
            horse_name_elem = row.query_selector('td.HorseInfo div.Horse_Name a')
            if horse_name_elem:
                horse_data['horse_name'] = horse_name_elem.inner_text().strip()
            
            # 性齢
            sex_age_elem = row.query_selector('td.HorseInfo span.Barei')
            if sex_age_elem:
                horse_data['sex_age'] = sex_age_elem.inner_text().strip()
            
            # 斤量
            weight_elem = row.query_selector('td.Jockey span.JockeyWeight')
            if weight_elem:
                horse_data['weight'] = weight_elem.inner_text().strip().replace('kg', '')
            
            # 騎手
            jockey_elem = row.query_selector('td.Jockey a')
            if jockey_elem:
                horse_data['jockey_name'] = jockey_elem.inner_text().strip()
            
            # 調教師
            trainer_elem = row.query_selector('td.Trainer a')
            if trainer_elem:
                horse_data['trainer_name'] = trainer_elem.inner_text().strip()
            
            # オッズと人気
            odds_elem = row.query_selector('td.Odds.Txt_R')
            if odds_elem:
                odds_text = odds_elem.inner_text().strip()
                if odds_text:
                    horse_data['odds'] = odds_text
            
            popularity_elem = row.query_selector('td.Popularity')
            if popularity_elem:
                horse_data['popularity'] = popularity_elem.inner_text().strip()
            
            # 馬体重
            weight_elem = row.query_selector('td.Weight')
            if weight_elem:
                weight_text = weight_elem.inner_text().strip()
                horse_data['horse_weight'] = weight_text
            
            print(f"Debug - Horse data: {horse_data}")
            entry_info['entries'].append(horse_data)
        
        return entry_info
        
    except Exception as e:
        print(f"レース情報取得中にエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def save_to_csv(race_entry: Dict[str, any], filename: str = None):
    """レース情報をCSVに保存する"""
    try:
        os.makedirs('data/race_entries', exist_ok=True)
        
        if filename is None:
            current_date = datetime.now().strftime('%Y%m%d')
            filename = f'data/race_entries/jra_race_entries_{current_date}.csv'
        else:
            filename = f'data/race_entries/{filename}'
        
        # ファイルが存在しない場合は新規作成
        file_exists = os.path.isfile(filename)
        
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
                race_entry['race_details'],
                json.dumps(race_entry['entries'], ensure_ascii=False)  # 出走馬情報をJSON形式で保存
            ])
            
        print(f"CSVに保存しました: {filename}")
            
    except Exception as e:
        print(f"CSV保存エラー: {str(e)}")
        import traceback
        traceback.print_exc()

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得"""
    all_race_urls = set()  # セットを使用して重複を防止
    try:
        url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        print(f"\n{date_str}のレース情報を取得中...")
        
        # タイムアウトを設定
        page.set_default_timeout(60000)  # 60秒
        
        # まずトップページにアクセス
        print("トップページにアクセスしています...")
        page.goto("https://race.netkeiba.com/", wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # 次に目的のページに遷移
        print(f"レース一覧ページにアクセスしています: {url}")
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except TimeoutError:
            print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
        
        page.wait_for_timeout(5000)
        
        # JavaScriptを実行してページの準備ができているか確認
        is_ready = page.evaluate('''() => {
            return document.readyState === 'complete';
        }''')
        
        if not is_ready:
            print("ページの準備ができていません。さらに待機します...")
            page.wait_for_timeout(5000)
        
        # 出馬表へのリンクを取得
        race_links = page.query_selector_all('a[href*="/race/shutuba.html"]')
        print(f"直接リンクから取得したリンク数: {len(race_links)}")
        
        # リンクが見つからない場合は、race_idを含むリンクを探して変換
        if len(race_links) == 0:
            race_links = page.query_selector_all('a[href*="race_id="]')
            print(f"race_idを含むリンク数: {len(race_links)}")
        
        for link in race_links:
            href = link.get_attribute('href')
            if href:
                # race_idを抽出してshutuba.htmlのURLに変換
                if 'race_id=' in href:
                    race_id_match = re.search(r'race_id=(\d+)', href)
                    if race_id_match:
                        race_id = race_id_match.group(1)
                        race_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                        all_race_urls.add(race_url)
                        print(f"race_idから変換: {race_url}")
                # 直接shutuba.htmlへのリンクの場合
                elif '/race/shutuba.html' in href:
                    # 相対パスを絶対URLに変換
                    if href.startswith('/'):
                        race_url = f"https://race.netkeiba.com{href}"
                    else:
                        race_url = href
                    all_race_urls.add(race_url)
                    print(f"直接リンク: {race_url}")
        
        # HTMLから直接race_idを抽出してバックアップとして使用
        html_content = page.content()
        race_id_pattern = re.compile(r'race_id=(\d+)')
        race_ids = race_id_pattern.findall(html_content)
        
        for race_id in race_ids:
            if len(race_id) == 12:  # 有効なレースIDは12桁
                race_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                all_race_urls.add(race_url)
                print(f"HTMLから抽出: {race_url}")
        
        # URLが一つも取得できなかった場合のバックアップ（日付から動的に生成）
        if len(all_race_urls) == 0:
            print("URLを取得できなかったため、標準パターンから生成します")
            
            # 年と月を取得
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # 土日かどうか判定
            target_date = datetime.strptime(date_str, '%Y%m%d')
            is_weekend = target_date.weekday() >= 5
            
            # 主要競馬場
            main_venues = ["05", "06", "09"] if is_weekend else ["01", "02", "03"]
            
            # 回次と日目（簡易推定）
            week_num = (int(day) - 1) // 7 + 1
            kai_code = f"{(int(month) % 6) + 1:02d}"
            day_code = f"{week_num:02d}"
            
            for venue in main_venues:
                for race_num in range(1, 13):
                    race_id = f"{year}{venue}{kai_code}{day_code}{race_num:02d}"
                    race_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                    all_race_urls.add(race_url)
                    print(f"パターンから生成: {race_url}")
        
        print(f"合計で{len(all_race_urls)}件のレースURLを取得しました")
        
    except Exception as e:
        print(f"レースURL取得中にエラー: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return list(all_race_urls)  # セットをリストに変換して返す

def get_race_info_for_next_three_days():
    """今日から3日分のレース情報を取得"""
    try:
        with sync_playwright() as p:
            # シンプルにブラウザを起動
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            
            try:
                page = context.new_page()
                
                for i in range(3):
                    target_date = datetime.now() + timedelta(days=i)
                    date_str = target_date.strftime("%Y%m%d")
                    filename = f"jra_race_entries_{date_str}.csv"
                    
                    print(f"\n{target_date.strftime('%Y年%m月%d日')}({date_str})の処理を開始します...")
                    
                    try:
                        # URLを取得
                        race_urls = get_race_urls_for_date(page, context, date_str)
                        print(f"{date_str}のレースURL数: {len(race_urls)}")
                        
                        if race_urls:  # レースURLが存在する場合のみ処理
                            success_count = 0
                            for idx, race_url in enumerate(race_urls, 1):
                                try:
                                    print(f"処理中: ({idx}/{len(race_urls)}) {race_url}")
                                    race_entry = scrape_race_entry(page, race_url)
                                    if race_entry and race_entry.get('entries') and len(race_entry['entries']) > 0:
                                        save_to_csv(race_entry, filename)
                                        success_count += 1
                                        print(f"保存完了: {race_entry.get('venue_name', '不明')} {race_entry.get('race_number', '?')}R（成功: {success_count}/{idx}）")
                                        # アクセス間隔を空ける（サーバー負荷軽減のため）
                                        time.sleep(2)
                                    else:
                                        print(f"レースデータなし: {race_url}")
                                except Exception as e:
                                    print(f"レース情報取得エラー: {str(e)}")
                                    traceback.print_exc()
                            print(f"{date_str}の処理が完了しました（成功: {success_count}/{len(race_urls)}）")
                        else:
                            print(f"{date_str}のレースはありません")
                    except Exception as e:
                        print(f"{date_str}の処理中にエラーが発生しました: {str(e)}")
                        traceback.print_exc()
                
            finally:
                try:
                    context.close()
                    browser.close()
                    print("ブラウザを正常に閉じました")
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
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        )
        page = context.new_page()
        
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
    print("中央競馬出走表の取得を開始します...")
    success = get_race_info_for_next_three_days()
    if success:
        print("スクレイピングが正常に完了しました")
        sys.exit(0)
    else:
        print("スクレイピングに失敗しました")
        sys.exit(1) 