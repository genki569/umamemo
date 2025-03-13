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
from app.models import Race, Horse, Jockey, ShutubaEntry
from app.extensions import db

def scrape_race_entry(page, race_url: str) -> Dict[str, any]:
    """出走表ページから情報を取得する"""
    try:
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

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得"""
    all_race_urls = []
    try:
        url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        print(f"\n{date_str}のレース情報を取得中...")
        
        # タイムアウトを設定
        page.set_default_timeout(60000)  # 60秒
        
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
        
        # JavaScriptを実行してページの準備ができているか確認
        is_ready = page.evaluate('''() => {
            return document.querySelector('.RaceList_ProvinceSelect') !== null;
        }''')
        
        if not is_ready:
            print("ページの準備ができていません。さらに待機します...")
            page.wait_for_timeout(5000)
        
        venues = page.query_selector_all('.RaceList_ProvinceSelect li')
        print(f"開催場所数: {len(venues)}")
        
        for venue in venues:
            try:
                venue_name = venue.inner_text().strip()
                print(f"\n開催場所: {venue_name}")
                
                venue_link = venue.query_selector('a')
                if venue_link:
                    href = venue_link.get_attribute('href')
                    venue_url = f"https://nar.netkeiba.com/top/race_list.html{href}"
                    print(f"開催場所URL: {venue_url}")
                    
                    venue_page = context.new_page()
                    try:
                        venue_page.goto(venue_url, wait_until='domcontentloaded', timeout=30000)
                        venue_page.wait_for_timeout(3000)
                        
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
                
    except Exception as e:
        print(f"レースURL取得中にエラー: {str(e)}")
    
    return all_race_urls

def get_race_info_for_next_three_days():
    """今日から3日分のレース情報を取得"""
    try:
        all_race_entries = []
        today = datetime.now()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            
            try:
                page = context.new_page()
                
                for i in range(3):
                    target_date = today + timedelta(days=i)
                    date_str = target_date.strftime("%Y%m%d")
                    print(f"\n{date_str}のレース情報の取得を開始します...")
                    
                    race_urls = get_race_urls_for_date(page, context, date_str)
                    print(f"取得したレースURL数: {len(race_urls)}")
                    
                    # 各レースの情報を取得してすぐにCSVに保存
                    for race_url in race_urls:
                        # レース情報のスクレイピング
                        race_entry = scrape_race_entry(page, race_url)
                        if race_entry:
                            # CSVに生データを保存
                            save_to_csv(race_entry)
                            
                            # データを変換
                            converted_data = convert_entry_data(race_entry)
                            if converted_data:
                                # 変換したデータをDBに保存
                                save_converted_data(converted_data)
                                
            finally:
                context.close()
                browser.close()
        
        return all_race_entries
        
    except Exception as e:
        print(f"処理エラー: {str(e)}")

def convert_race_id(url: str) -> str:
    """URLからレースIDを抽出"""
    match = re.search(r'race_id=(\d+)', url)
    return match.group(1) if match else None

def get_or_create_horse(name: str) -> Horse:
    """馬名から馬を取得または作成"""
    horse = Horse.query.filter_by(name=name).first()
    if not horse:
        horse = Horse(name=name)
        db.session.add(horse)
        db.session.flush()
    return horse

def get_or_create_jockey(name: str) -> Jockey:
    """騎手名から騎手を取得または作成"""
    jockey = Jockey.query.filter_by(name=name).first()
    if not jockey:
        jockey = Jockey(name=name)
        db.session.add(jockey)
        db.session.flush()
    return jockey

def convert_entry_data(race_entry: Dict[str, any]) -> Dict[str, any]:
    """スクレイピングしたデータを適切な形式に変換"""
    try:
        # レース基本情報の変換
        converted_data = {
            'race_id': convert_race_id(race_entry['race_id']),
            'race_name': race_entry['race_name'],
            'race_number': int(race_entry['race_number']),
            'venue_name': race_entry['venue_name'],
            'start_time': datetime.strptime(race_entry['start_time'], '%H:%M').time(),
            'course_info': race_entry['course_info'],
            'race_details': race_entry['race_details'],
            'entries': []
        }

        # 出走馬情報の変換
        for entry in race_entry['entries']:
            # 馬情報の取得/作成
            horse = get_or_create_horse(entry['horse_name'])
            
            # 騎手情報の取得/作成
            jockey = get_or_create_jockey(entry['jockey_name'])
            
            # 調教師情報の取得/作成（必要な場合）
            trainer = get_or_create_trainer(entry['trainer_name'])
            
            converted_entry = {
                'horse_id': horse.id,
                'jockey_id': jockey.id,
                'trainer_id': trainer.id,
                'horse_number': int(entry['horse_number']),
                'weight': float(entry['weight']) if entry.get('weight') else None,
                'odds': float(entry['odds']) if entry.get('odds') else None,
                'popularity': int(entry['popularity']) if entry.get('popularity') else None
            }
            
            converted_data['entries'].append(converted_entry)
            
        return converted_data
        
    except Exception as e:
        print(f"データ変換エラー: {str(e)}")
        return None

def save_converted_data(converted_data: Dict[str, any]):
    """変換したデータをデータベースに保存"""
    try:
        # レース情報の保存/更新
        race = Race.query.get(converted_data['race_id'])
        if not race:
            race = Race(
                id=converted_data['race_id'],
                name=converted_data['race_name'],
                race_number=converted_data['race_number'],
                venue_name=converted_data['venue_name'],
                start_time=converted_data['start_time'],
                course_info=converted_data['course_info'],
                race_details=converted_data['race_details']
            )
            db.session.add(race)
        
        # 出走登録情報の保存
        for entry_data in converted_data['entries']:
            entry = ShutubaEntry.query.filter_by(
                race_id=race.id,
                horse_id=entry_data['horse_id']
            ).first()
            
            if not entry:
                entry = ShutubaEntry(
                    race_id=race.id,
                    horse_id=entry_data['horse_id'],
                    jockey_id=entry_data['jockey_id'],
                    trainer_id=entry_data['trainer_id'],
                    horse_number=entry_data['horse_number'],
                    weight=entry_data['weight'],
                    odds=entry_data['odds'],
                    popularity=entry_data['popularity']
                )
                db.session.add(entry)
        
        db.session.commit()
        print(f"保存完了: {converted_data['venue_name']} {converted_data['race_number']}R")
        
    except Exception as e:
        db.session.rollback()
        print(f"データベース保存エラー: {str(e)}")
        raise

if __name__ == '__main__':
    print("地方競馬出走表の取得を開始します...")
    
    # 3日分のレース情報を取得
    all_race_entries = get_race_info_for_next_three_days()
    
    # 全レース情報をCSVに保存
    if all_race_entries:
        today = datetime.now().strftime('%Y%m%d')
        filename = f"nar_race_entries_{today}.csv"
        for race_entry in all_race_entries:
            save_to_csv(race_entry, filename)
        print(f"\n取得したレース数: {len(all_race_entries)}")