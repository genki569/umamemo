from playwright.sync_api import sync_playwright, TimeoutError
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import os
import csv
import json

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得"""
    race_urls = []
    try:
        url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
        # 開催場所のリストを取得
        venue_links = page.query_selector_all('.RaceList_ProvinceSelect li')
        
        for venue_link in venue_links:
            venue_page = context.new_page()
            try:
                venue_url = venue_link.query_selector('a').get_attribute('href')
                venue_page.goto(f"https://nar.netkeiba.com{venue_url}", wait_until='domcontentloaded')
                venue_page.wait_for_timeout(2000)
                
                # レース一覧を取得
                race_links = venue_page.query_selector_all('dl.RaceList_DataList')
                for race_link in race_links:
                    shutuba_link = race_link.query_selector('a[href*="/race/shutuba.html"]')
                    if shutuba_link:
                        race_url = shutuba_link.get_attribute('href')
                        race_urls.append(f"https://nar.netkeiba.com{race_url}")
                
            finally:
                venue_page.close()
                
        return race_urls
        
    except Exception as e:
        print(f"レースURL取得エラー: {str(e)}")
        return race_urls

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
            'race_id': race_id,
            'venue_name': '',
            'start_time': '',
            'course_info': '',
            'race_details': '',
            'entries': []
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
        
        # レース詳細
        details_elem = page.query_selector('.Race_Data')
        if details_elem:
            entry_info['race_details'] = details_elem.inner_text().strip()
        
        # 出走馬情報を取得
        horse_rows = page.query_selector_all('tr.HorseList')
        
        for row in horse_rows:
            horse_data = {}
            
            # 馬番
            horse_number = row.query_selector('td.Umaban')
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
            
            # 斤量
            weight = row.query_selector('td:nth-child(6)')
            if weight:
                horse_data['weight'] = weight.inner_text().strip()
            
            # 騎手
            jockey = row.query_selector('.Jockey a')
            if jockey:
                horse_data['jockey_name'] = jockey.inner_text().strip()
            
            # 調教師
            trainer = row.query_selector('.Trainer a')
            if trainer:
                horse_data['trainer_name'] = trainer.inner_text().strip()
            
            entry_info['entries'].append(horse_data)
        
        return entry_info
        
    except Exception as e:
        print(f"レース情報取得エラー: {str(e)}")
        return None

def save_to_csv(race_entry: Dict[str, any], filename: str):
    """レース情報をCSVに保存する"""
    try:
        os.makedirs('data/race_entries', exist_ok=True)
        filepath = os.path.join('data/race_entries', filename)
        
        # ヘッダーの定義
        headers = ['race_id', 'race_name', 'race_number', 'venue_name', 
                  'start_time', 'course_info', 'race_details', 'entries']
        
        # ファイルが存在しない場合はヘッダーを書き込む
        file_exists = os.path.isfile(filepath)
        
        with open(filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            
            if not file_exists:
                writer.writeheader()
            
            # エントリー情報をJSON文字列に変換
            race_entry['entries'] = json.dumps(race_entry['entries'], ensure_ascii=False)
            writer.writerow(race_entry)
            
    except Exception as e:
        print(f"CSV保存エラー: {str(e)}")

def get_race_info_for_next_three_days():
    """今日から3日分のレース情報を取得"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            for i in range(3):
                target_date = datetime.now() + timedelta(days=i)
                date_str = target_date.strftime("%Y%m%d")
                filename = f"nar_race_entries_{date_str}.csv"
                
                race_urls = get_race_urls_for_date(page, context, date_str)
                print(f"{date_str}のレースURL数: {len(race_urls)}")
                
                for race_url in race_urls:
                    race_entry = scrape_race_entry(page, race_url)
                    if race_entry:
                        save_to_csv(race_entry, filename)
                        print(f"保存完了: {race_entry['venue_name']} {race_entry['race_number']}R")
            
            browser.close()
            
    except Exception as e:
        print(f"処理エラー: {str(e)}")

if __name__ == '__main__':
    print("地方競馬出走表の取得を開始します...")
    get_race_info_for_next_three_days()