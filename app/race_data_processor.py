import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
import json
import re

# スクレイピング用の定数
HEADERS = [
    '着順', '枠番', '馬番', '馬名', '性齢', '斤量', '騎手',
    'タイム', '着差', 'ﾀｲﾑ指数', '通過', '上り', '単勝',
    '人気', '馬体重', '調教ﾀｲﾑ', '厩舎ｺﾒﾝﾄ', '備考',
    '調教師', '馬主', '賞金(万円)'
]

def requests_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def scrape_race_list(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = session.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        race_links = []
        for link in soup.select('a[href*="/race/"]'):
            href = link.get('href', '')
            if '/race/20' in href and href not in race_links:
                race_links.append(href)
        
        return race_links
    except Exception as e:
        print(f"レース一覧の取得中にエラー発生: {str(e)}")
        return []

def scrape_race_details(url, session):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        if not url.startswith('http'):
            url = f"https://db.netkeiba.com{url}"
            
        response = session.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        race_data = {
            'race_name': '',
            'race_details': '',
            'date': '',
            'venue': '',
            'venue_details': '',
            'start_time': '',
            'results': []
        }
        
        # レース名の取得
        race_name_elem = soup.select_one('div.data_intro h1, .racedata h1')
        race_data['race_name'] = race_name_elem.text.strip() if race_name_elem else ''
        
        # レース詳細の取得
        race_details_elem = soup.select_one('div.data_intro p, .racedata p')
        race_data['race_details'] = race_details_elem.text.strip() if race_details_elem else ''
        
        # 日付、会場、発走時刻の取得
        race_info = soup.select_one('div.data dl.racedata')
        if race_info:
            race_data['date'] = race_info.select_one('dt').text.strip() if race_info.select_one('dt') else ''
            venue_elem = race_info.select_one('dd')
            if venue_elem:
                race_data['venue'] = venue_elem.text.strip()
                race_data['venue_details'] = venue_elem.text.strip()
            start_time_elem = race_info.select_one('dd span')
            if start_time_elem:
                race_data['start_time'] = start_time_elem.text.strip()
        
        # レース結果の取得
        result_table = soup.select_one('table.race_table_01')
        if result_table:
            results = []
            for row in result_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue
                    
                result = {}
                for header, cell in zip(HEADERS, cols):
                    result[header] = cell.text.strip()
                results.append(result)
            
            race_data['results'] = results
        
        return race_data
        
    except Exception as e:
        print(f"レース詳細の取得中にエラー発生: {url}")
        print(f"エラー内容: {str(e)}")
        return None

def convert_japanese_date(date_str):
    try:
        pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
        match = re.match(pattern, str(date_str))
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    except:
        return None
    return None

def generate_venue_code(venue_name):
    venue_codes = {
        '札幌': '101', '函館': '102', '福島': '103', '新潟': '104',
        '東京': '105', '中山': '106', '中京': '107', '京都': '108',
        '阪神': '109', '小倉': '110', '門別': '201', '帯広': '202',
        '盛岡': '203', '水沢': '204', '浦和': '205', '船橋': '206',
        '大井': '207', '川崎': '208', '金沢': '209', '笠松': '210',
        '名古屋': '211', '園田': '212', '姫路': '213', '高知': '214',
        '佐賀': '215'
    }
    
    for key in venue_codes:
        if key in str(venue_name):
            return venue_codes[key]
    return '999'

def generate_race_id(row):
    try:
        if pd.isna(row['date']):
            return None
            
        formatted_date = convert_japanese_date(str(row['date']))
        if not formatted_date:
            return None
            
        date_obj = datetime.strptime(formatted_date, '%Y-%m-%d')
        date_num = date_obj.strftime('%Y%m%d')
        
        venue_code = generate_venue_code(row['venue_details'])
        
        kai_match = re.search(r'(\d+)回', str(row['race_details']))
        kai = kai_match.group(1).zfill(2) if kai_match else '01'
        
        try:
            race_num = str(int(row['race_number'])).zfill(2)
        except:
            race_num = '01'
        
        race_id = f"{date_num}{venue_code}{kai}{race_num}"
        return int(race_id)
    except Exception as e:
        print(f"Error generating ID for race: {row.get('race_name', 'Unknown')} - {str(e)}")
        return None

def parse_race_details(details_str):
    if not isinstance(details_str, str):
        return {}
    
    info = {
        'distance': None,
        'track_type': None,
        'direction': None,
        'weather': None,
        'track_condition': None
    }
    
    try:
        distance_match = re.search(r'(\d+)m', details_str)
        if distance_match:
            info['distance'] = int(distance_match.group(1))
        
        if '芝' in details_str:
            info['track_type'] = '芝'
        elif 'ダ' in details_str:
            info['track_type'] = 'ダート'
        
        if '右' in details_str:
            info['direction'] = '右'
        elif '左' in details_str:
            info['direction'] = '左'
        
        weather_match = re.search(r'天候:(\w+)', details_str)
        if weather_match:
            info['weather'] = weather_match.group(1)
        
        condition_match = re.search(r'馬場:(\w+)', details_str)
        if condition_match:
            info['track_condition'] = condition_match.group(1)
            
    except Exception as e:
        print(f"Error parsing race details: {str(e)}")
        
    return info

def generate_horse_id(horse_name):
    if not horse_name:
        return None
    return abs(hash(horse_name)) % (10 ** 8)

def generate_jockey_id(jockey_name):
    if not jockey_name:
        return None
    return abs(hash(jockey_name)) % (10 ** 8)

def generate_entry_id(race_id, horse_number):
    if not race_id or not horse_number:
        return None
    entry_id_str = f"{race_id}{str(horse_number).zfill(2)}"
    return int(entry_id_str)

def convert_prize(prize_str):
    if not prize_str or prize_str == '':
        return None
    try:
        return float(prize_str.replace(',', ''))
    except:
        return None

def process_race_data():
    base_url = "https://db.netkeiba.com/?pid=race_list&word=&start_year=none&start_mon=none&end_year=none&end_mon=none&jyo%5B0%5D=01&jyo%5B1%5D=02&jyo%5B2%5D=03&jyo%5B3%5D=04&jyo%5B4%5D=05&jyo%5B5%5D=06&jyo%5B6%5D=07&jyo%5B7%5D=08&jyo%5B8%5D=09&jyo%5B9%5D=10&jyo%5B10%5D=30&jyo%5B11%5D=35&jyo%5B12%5D=36&jyo%5B13%5D=42&jyo%5B14%5D=43&jyo%5B15%5D=44&jyo%5B16%5D=45&jyo%5B17%5D=46&jyo%5B18%5D=47&jyo%5B19%5D=48&jyo%5B20%5D=50&jyo%5B21%5D=51&jyo%5B22%5D=54&jyo%5B23%5D=55&jyo%5B24%5D=65&kyori_min=&kyori_max=&sort=date&list=100"
    
    session = requests_retry_session()
    all_race_data = []
    
    try:
        print("1. スクレイピングを開始します...")
        
        for page in range(1, 4):
            current_url = f"{base_url}&page={page}"
            print(f"ページ {page}/3 をスクレイピング中...")
            
            race_urls = scrape_race_list(current_url, session)
            if not race_urls:
                print(f"ページ {page} にレースデータがありません。")
                break
            
            for i, race_url in enumerate(race_urls, 1):
                print(f"レース {i}/{len(race_urls)} をスクレイピング中...")
                race_data = scrape_race_details(race_url, session)
                
                if race_data is not None:
                    race_data['venue_details'] = race_data.get('venue', '')
                    all_race_data.append(race_data)
                    print(f"レース {i} のデータを取得しました")
                else:
                    print(f"レース {i} のデータ取得をスキップしました")

        # スクレイピングしたデータをCSVとして保存
        current_date = datetime.now().strftime('%Y%m%d')
        temp_csv_path = f'netkeiba_daily_races_{current_date}.csv'
        
        if all_race_data:
            df = pd.DataFrame(all_race_data)
            # 必要なカラムが存在することを確認
            required_columns = ['venue', 'venue_details', 'race_name', 'race_details', 'date', 'results']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''  # 欠落しているカラムを空文字で初期化
            
            df.to_csv(temp_csv_path, index=False, encoding='utf-8-sig')
            print(f"2. スクレイピングしたデータを {temp_csv_path} に保存しました")
            
            # CSV分割処理の実行
            print("3. データの分割処理を開始します...")
            split_race_csv(temp_csv_path)
            
            # 一時ファイルの削除
            os.remove(temp_csv_path)
            print("4. 処理が完了しました")
        else:
            print("レースデータを取得できませんでした")
            
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        import traceback
        print(traceback.format_exc())  # スタックトレースを出力
    finally:
        session.close()

def split_race_csv(input_path):
    """CSVファイルを分割して処理する関数"""
    # 出力ディレクトリの作成
    output_dir = 'scripts/output'
    os.makedirs(output_dir, exist_ok=True)

    # メインのCSVファイルの読み込み
    print(f"Reading CSV from: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} rows")

    # 必要なカラムの存在確認
    required_columns = ['venue', 'venue_details', 'race_name', 'race_details', 'date']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    df['venue_details'] = df['venue']
    df['race_number'] = df['race_name'].apply(lambda x: re.search(r'(\d+)R', str(x)).group(1) if re.search(r'(\d+)R', str(x)) else '1')
    
    details_info = df['race_details'].apply(parse_race_details)
    
    print("Generating race IDs...")
    df['generated_id'] = df.apply(lambda row: generate_race_id(row) if pd.notna(row['date']) else None, axis=1)
    
    races_df = pd.DataFrame({
        'id': df['generated_id'],
        'name': df['race_name'],
        'date': df['date'].apply(lambda x: convert_japanese_date(str(x)) if pd.notna(x) else None),
        'start_time': df['start_time'],
        'venue': df['venue_details'],
        'venue_id': df['venue_details'].apply(generate_venue_code),
        'race_number': df['race_number'],
        'race_year': df['date'].apply(lambda x: int(str(x).split('年')[0]) if pd.notna(x) and '年' in str(x) else None),
        'kai': df['race_details'].apply(lambda x: re.search(r'(\d+)回', str(x)).group(1) if re.search(r'(\d+)回', str(x)) else None),
        'nichi': None,
        'race_class': None,
        'distance': details_info.apply(lambda x: x.get('distance')),
        'track_type': details_info.apply(lambda x: x.get('track_type')),
        'direction': details_info.apply(lambda x: x.get('direction')),
        'weather': details_info.apply(lambda x: x.get('weather')),
        'memo': None,
        'track_condition': details_info.apply(lambda x: x.get('track_condition')),
        'created_at': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * len(df),
        'details': df['race_details']
    })
    
    horses_data = {}
    jockeys_data = {}
    entries_data = []
    
    print("Processing race results...")
    for index, row in df.iterrows():
        race_id = row['generated_id']
        results_str = row['results']
        if not isinstance(results_str, str):
            continue
            
        try:
            results_str = results_str.replace("'", '"')
            results = json.loads(results_str)
            
            for result in results:
                horse_name = result['馬名']
                horse_id = generate_horse_id(horse_name)
                
                if horse_id not in horses_data:
                    horses_data[horse_id] = {
                        'id': horse_id,
                        'name': horse_name,
                        'birth_year': None,
                        'sex': result['性齢'][0] if len(result['性齢']) > 0 else None,
                        'trainer': None,
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'memo': None,
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                jockey_name = result['騎手']
                jockey_id = generate_jockey_id(jockey_name)
                
                if jockey_id and jockey_id not in jockeys_data:
                    jockeys_data[jockey_id] = {
                        'id': jockey_id,
                        'name': jockey_name
                    }
                
                horse_number = int(result['馬番']) if result['馬番'].isdigit() else None
                entry_id = generate_entry_id(race_id, horse_number)
                
                entries_data.append({
                    'id': entry_id,
                    'race_id': race_id,
                    'horse_id': horse_id,
                    'jockey_id': jockey_id,
                    'horse_number': horse_number,
                    'odds': float(result['単勝']) if result['単勝'].replace('.', '').isdigit() else None,
                    'popularity': int(result['人気']) if result['人気'].isdigit() else None,
                    'horse_weight': None,
                    'weight_change': None,
                    'prize': convert_prize(result.get('賞金(万円)')),
                    'position': int(result['着順']) if '着順' in result and result['着順'].isdigit() else None,
                    'frame_number': int(result['枠番']) if '枠番' in result and result['枠番'].isdigit() else None,
                    'weight': float(result['斤量']) if '斤量' in result else None,
                    'time': result.get('タイム', None),
                    'margin': result.get('着差', None),
                    'passing': result.get('通過', None),
                    'last_3f': float(result['上り']) if '上り' in result and result['上り'] else None
                })
                
        except json.JSONDecodeError as e:
            print(f"Error parsing results for race {index + 1}")
            continue
    
    horses_df = pd.DataFrame(list(horses_data.values()))
    jockeys_df = pd.DataFrame(list(jockeys_data.values()))
    entries_df = pd.DataFrame(entries_data)
    
    races_df.to_csv(os.path.join(output_dir, 'races.csv'), 
                   index=False, 
                   header=False,
                   encoding='utf-8',
                   na_rep='NULL')
    
    horses_df.to_csv(os.path.join(output_dir, 'horses.csv'), 
                    index=False, 
                    header=False,
                    encoding='utf-8',
                    na_rep='NULL')
    
    jockeys_df.to_csv(os.path.join(output_dir, 'jockeys.csv'), 
                     index=False, 
                     header=False,
                     encoding='utf-8',
                     na_rep='NULL')
    
    entries_df.to_csv(os.path.join(output_dir, 'entries.csv'), 
                     index=False, 
                     header=False,
                     encoding='utf-8',
                     na_rep='NULL')
    
    print(f"Saved races.csv with {len(races_df)} rows")
    print(f"Saved horses.csv with {len(horses_df)} rows")
    print(f"Saved jockeys.csv with {len(jockeys_df)} rows")
    print(f"Saved entries.csv with {len(entries_df)} rows")

if __name__ == '__main__':
    process_race_data()