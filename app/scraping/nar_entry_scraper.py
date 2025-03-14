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
        page.goto(race_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
        # race_idを生成
        race_id = generate_race_id(race_url)
        if not race_id:
            return None
        
        entry_info = {
            'race_id': race_id,  # 生成したIDを使用
            'race_name': '',
            'race_number': '',
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

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """指定日の全レースの出馬表URLを取得"""
    all_race_urls = set()
    try:
        url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
        print(f"\n{date_str}のレース情報を取得中...")
        
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(5000)
        
        # 各開催場所のレースリンクを取得
        race_links = page.query_selector_all('a[href*="/race/shutuba.html"]')
        print(f"Found {len(race_links)} race links")
        
        for link in race_links:
            href = link.get_attribute('href')
            if href:
                race_url = f"https://nar.netkeiba.com{href.replace('..', '')}"
                all_race_urls.add(race_url)
                print(f"レースURL追加: {race_url}")
        
        return list(all_race_urls)
                
    except Exception as e:
        print(f"レースURL取得中にエラー: {str(e)}")
        return list(all_race_urls)

def save_to_database(races_data, horses_data, jockeys_data, entries_data):
    """スクレイピングしたデータをデータベースに保存"""
    try:
        count = 0
        BATCH_SIZE = 100
        
        print("データベースへの保存を開始します...")
        
        # レース情報の保存
        for race in races_data:
            count += 1
            race_id = race['id']
            existing_race = Race.query.get(race_id)
            
            if not existing_race:
                # 新規レース
                race_obj = Race(**race)
                db.session.add(race_obj)
                print(f"新規レース追加: {race['venue']} {race['race_number']}R")
            else:
                # 既存レース更新
                for key, value in race.items():
                    if hasattr(existing_race, key):
                        setattr(existing_race, key, value)
                print(f"既存レース更新: {race['venue']} {race['race_number']}R")
            
            if count % BATCH_SIZE == 0:
                db.session.commit()
                print(f"中間保存: {count}件処理済み")
        
        # 馬情報の保存
        for horse_id, horse in horses_data.items():
            count += 1
            existing_horse = Horse.query.get(horse_id)
            
            if not existing_horse:
                # 新規馬
                horse_obj = Horse(**horse)
                db.session.add(horse_obj)
                print(f"新規馬追加: {horse['name']}")
            else:
                # 既存馬更新
                for key, value in horse.items():
                    if hasattr(existing_horse, key):
                        setattr(existing_horse, key, value)
            
            if count % BATCH_SIZE == 0:
                db.session.commit()
                print(f"中間保存: {count}件処理済み")
        
        # 騎手情報の保存
        for jockey_id, jockey in jockeys_data.items():
            count += 1
            existing_jockey = Jockey.query.get(jockey_id)
            
            if not existing_jockey:
                # 新規騎手
                jockey_obj = Jockey(**jockey)
                db.session.add(jockey_obj)
                print(f"新規騎手追加: {jockey['name']}")
            else:
                # 既存騎手更新
                for key, value in jockey.items():
                    if hasattr(existing_jockey, key):
                        setattr(existing_jockey, key, value)
            
            if count % BATCH_SIZE == 0:
                db.session.commit()
                print(f"中間保存: {count}件処理済み")
        
        # 出走表エントリー情報の保存
        for entry in entries_data:
            count += 1
            
            # 既存エントリーを検索（race_id, horse_idの組み合わせで）
            existing_entry = ShutubaEntry.query.filter_by(
                race_id=entry['race_id'],
                horse_id=entry['horse_id']
            ).first()
            
            if not existing_entry:
                # 新規エントリー
                entry_obj = ShutubaEntry(**entry)
                db.session.add(entry_obj)
                print(f"新規出走表エントリー追加: 馬番{entry['horse_number']}")
            else:
                # 既存エントリー更新
                for key, value in entry.items():
                    if hasattr(existing_entry, key):
                        setattr(existing_entry, key, value)
                print(f"既存出走表エントリー更新: 馬番{entry['horse_number']}")
            
            if count % BATCH_SIZE == 0:
                db.session.commit()
                print(f"中間保存: {count}件処理済み")
        
        # 残りのデータをコミット
        db.session.commit()
        print(f"データベース保存完了: 合計{count}件処理")
        
        # 統計情報
        print("\n===== 保存結果 =====")
        print(f"レース数: {len(races_data)}")
        print(f"馬数: {len(horses_data)}")
        print(f"騎手数: {len(jockeys_data)}")
        print(f"出走表エントリー数: {len(entries_data)}")
        
    except Exception as e:
        db.session.rollback()
        print(f"データベース保存エラー: {str(e)}")
        traceback.print_exc()
        raise

def extract_date_from_race_id(race_id: str) -> str:
    """レースIDから日付を抽出する（例: 202543031407 -> 2025-03-14）"""
    try:
        year = race_id[:4]
        month = race_id[6:8]
        day = race_id[8:10]
        return f"{year}-{month}-{day}"
    except Exception:
        return None

def process_race_data(race_entry: Dict[str, any]):
    """スクレイピングしたデータをデータベース用に変換"""
    race_id = race_entry.get('race_id')
    if not race_id:
        return [], {}, {}, []
    
    venue_name = race_entry.get('venue_name', '')
    
    # レース情報
    race_data = {
        'id': race_id,
        'name': race_entry.get('race_name', ''),
        'date': extract_date_from_race_id(race_id),
        'venue': venue_name,
        'race_number': int(race_entry.get('race_number', 0)),
        'details': race_entry.get('race_details', '')
    }
    
    # 馬、騎手、エントリー情報
    horses_data = {}
    jockeys_data = {}
    entries_data = []
    
    for entry in race_entry.get('entries', []):
        horse_name = entry.get('horse_name', '')
        if not horse_name:
            continue
        
        # 馬情報
        horse_id = generate_horse_id(horse_name)
        if horse_id and horse_id not in horses_data:
            sex_age = entry.get('sex_age', '')
            sex = sex_age[0] if sex_age else ''
            
            horses_data[horse_id] = {
                'id': horse_id,
                'name': horse_name,
                'sex': sex
            }
        
        # 騎手情報
        jockey_name = entry.get('jockey_name', '')
        jockey_id = generate_jockey_id(jockey_name) if jockey_name else None
        if jockey_id and jockey_id not in jockeys_data:
            jockeys_data[jockey_id] = {
                'id': jockey_id,
                'name': jockey_name
            }
        
        # 出走表エントリー情報
        try:
            horse_number = int(entry.get('horse_number', 0))
            bracket_number = int(entry.get('bracket_number', 0)) if entry.get('bracket_number') else None
            
            # エントリーIDを生成
            entry_id = generate_entry_id(race_id, horse_number)
            
            # ShutubaEntryモデルのフィールド名に合わせる
            entry_data = {
                'id': entry_id,
                'race_id': race_id,
                'horse_id': horse_id,
                'jockey_id': jockey_id,
                'bracket_number': bracket_number,
                'horse_number': horse_number
            }
            entries_data.append(entry_data)
        except (ValueError, TypeError) as e:
            print(f"エントリー情報の変換エラー: {str(e)}")
            continue
    
    return [race_data], horses_data, jockeys_data, entries_data

def get_race_info_for_next_day():
    """今日のレース情報のみを取得（デバッグ用）"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            all_races_data = []
            all_horses_data = {}
            all_jockeys_data = {}
            all_entries_data = []
            
            # 今日の日付のみ処理
            target_date = datetime.now()
            date_str = target_date.strftime("%Y%m%d")
            print(f"\n{date_str}の処理を開始します...")
            
            race_urls = get_race_urls_for_date(page, context, date_str)
            print(f"{date_str}のレースURL数: {len(race_urls)}")
            
            if race_urls:
                # デバッグ用に最初の1レースのみ処理
                race_url = race_urls[0]
                print(f"処理するレースURL: {race_url}")
                
                race_entry = scrape_race_entry(page, race_url)
                if race_entry:
                    # データを変換
                    races, horses, jockeys, entries = process_race_data(race_entry)
                    
                    # 全体のデータに追加
                    all_races_data.extend(races)
                    all_horses_data.update(horses)
                    all_jockeys_data.update(jockeys)
                    all_entries_data.extend(entries)
                    
                    print(f"処理完了: {race_entry['venue_name']} {race_entry['race_number']}R")
                
                print(f"{date_str}の処理が完了しました")
            else:
                print(f"{date_str}のレースはありません")
            
            browser.close()
            
            # データベースに保存
            if all_races_data:
                print("データベースに保存します...")
                print(f"レース数: {len(all_races_data)}")
                print(f"馬数: {len(all_horses_data)}")
                print(f"騎手数: {len(all_jockeys_data)}")
                print(f"エントリー数: {len(all_entries_data)}")
                
                save_to_database(all_races_data, all_horses_data, all_jockeys_data, all_entries_data)
                print("\n全ての処理が完了しました")
            else:
                print("\n保存するデータがありません")
            
    except Exception as e:
        print(f"処理エラー: {str(e)}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    from app import app
    with app.app_context():
        print("地方競馬出走表の取得を開始します...")
        get_race_info_for_next_day()  # 1日分のみ処理