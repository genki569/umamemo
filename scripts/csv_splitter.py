import pandas as pd
import json
import os
import re
from datetime import datetime

def convert_japanese_date(date_str):
    """日本語の日付を'YYYY-MM-DD'形式に変換"""
    try:
        # '2024年1月1日' → '2024-01-01'
        pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
        match = re.match(pattern, date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
    except:
        return None
    return None

def generate_venue_code(venue_name):
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
    
    for key in venue_codes:
        if key in venue_name:
            return venue_codes[key]
    return '999'

def generate_race_id(row):
    """
    レースIDの生成（15桁）
    構成: YYYYMMDD + 開催場所コード(3桁) + 開催回(2桁) + レース番号(2桁)
    """
    try:
        # 日本語の日付を変換
        formatted_date = convert_japanese_date(row['date'])
        if not formatted_date:
            raise ValueError(f"Invalid date format: {row['date']}")
            
        # 日付を数値形式に変換 (YYYYMMDD)
        date_obj = datetime.strptime(formatted_date, '%Y-%m-%d')
        date_num = date_obj.strftime('%Y%m%d')
        
        # 開催場所コード（3桁）
        venue_code = generate_venue_code(row['venue_details'])
        
        # 開催回（2桁）- race_detailsから抽出
        kai_match = re.search(r'(\d+)回', str(row['race_details']))
        kai = kai_match.group(1).zfill(2) if kai_match else '01'
        
        # レース番号（2桁）- デフォルトは'01'
        try:
            race_num = str(int(row['race_number'])).zfill(2)
        except:
            race_num = '01'
        
        # IDを生成
        race_id = f"{date_num}{venue_code}{kai}{race_num}"
        return int(race_id)
    except Exception as e:
        print(f"Error generating ID for race: {row['race_name']} - {str(e)}")
        return None

def parse_race_details(details_str):
    """race_detailsから情報を抽出する関数"""
    if not isinstance(details_str, str):
        return {}
    
    info = {
        'distance': None,
        'track_type': None,
        'direction': None,
        'weather': None,
        'track_condition': None
    }
    
    # 距離を抽出 (例: "1200m" から "1200" を取得)
    distance_match = re.search(r'(\d+)m', details_str)
    if distance_match:
        info['distance'] = int(distance_match.group(1))
    
    # トラック種別を抽出 (芝、ダート)
    if '芝' in details_str:
        info['track_type'] = '芝'
    elif 'ダ' in details_str:
        info['track_type'] = 'ダート'
    
    # 回り方向を抽出
    if '右' in details_str:
        info['direction'] = '右'
    elif '左' in details_str:
        info['direction'] = '左'
    
    # 天候を抽出 (例: "天候 : 曇" から "曇" を取得)
    weather_match = re.search(r'天候\s*:\s*(\S+)', details_str)
    if weather_match:
        info['weather'] = weather_match.group(1)
    
    # トラック状態を抽出 (例: "ダート : 稍重" から "稍重" を取得)
    condition_match = re.search(r'(?:芝|ダート)\s*:\s*(\S+)', details_str)
    if condition_match:
        info['track_condition'] = condition_match.group(1)
    
    return info

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

def extract_race_details(details_str):
    """レース詳細文字列から各種情報を抽出"""
    weather = ''
    track_condition = ''
    
    # 天候の抽出
    weather_match = re.search(r'天候\s*:\s*(\S+)', details_str)
    if weather_match:
        weather = weather_match.group(1)
    
    # トラック状態の抽出
    track_match = re.search(r'ダート\s*:\s*(\S+)', details_str)
    if track_match:
        track_condition = track_match.group(1)
    
    return weather, track_condition

def name_to_number(name):
    """
    名前から数値を生成
    各文字のUnicodeコードポイントを利用
    """
    # 名前の各文字のUnicodeコードポイントを取得して結合
    code_points = [str(ord(c)).zfill(5) for c in name]
    return int(''.join(code_points)[-9:])  # 9桁に制限

def generate_horse_id(horse_name):
    """
    馬IDを生成（10桁）
    - より確実なハッシュ生成のために、馬名全体を使用
    - 文字の位置情報も考慮
    - 衝突を検出して回避
    """
    # 既存のIDをキャッシュ
    if not hasattr(generate_horse_id, 'used_ids'):
        generate_horse_id.used_ids = set()
        generate_horse_id.name_to_id = {}

    # 既に生成済みのIDがあればそれを返す
    if horse_name in generate_horse_id.name_to_id:
        return generate_horse_id.name_to_id[horse_name]

    # 馬名の各文字の位置も考慮したハッシュ生成
    name_hash = 0
    for i, char in enumerate(horse_name):
        # 文字のコードポイントと位置を組み合わせる
        position_weight = (i + 1) * 100  # 位置による重み付け
        char_value = ord(char) * position_weight
        name_hash = (name_hash * 31 + char_value) & 0xFFFFFFFF

    # 9桁の数値に変換（先頭に1を付けて10桁に）
    base_id = int(f"1{abs(name_hash) % 999999999:09d}")

    # 衝突が発生した場合、新しいIDを生成
    while base_id in generate_horse_id.used_ids:
        base_id += 1
        if base_id % 1000000000 == 0:  # 10桁を超えないようにする
            base_id = 1000000000

    # 生成したIDを記録
    generate_horse_id.used_ids.add(base_id)
    generate_horse_id.name_to_id[horse_name] = base_id

    return base_id

def generate_jockey_id(jockey_name):
    """
    騎手IDを生成（10桁）
    2 + 名前から生成した数値(9桁)
    """
    name_num = name_to_number(jockey_name)
    return int(f"2{name_num:09d}")

def split_race_csv(input_path):
    # 出力ディレクトリの作成
    output_dir = 'scripts/output'
    os.makedirs(output_dir, exist_ok=True)
    
    # メインのCSV読み込み
    print(f"Reading CSV from: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} rows")
    
    # race_detailsから追加情報を抽出
    details_info = df['race_details'].apply(parse_race_details)
    
    # races.csv の作成時にIDを生成
    print("Generating race IDs...")
    df['generated_id'] = df.apply(generate_race_id, axis=1)
    
    races_df = pd.DataFrame({
        'id': df['generated_id'],
        'name': df['race_name'],
        'date': df['date'].apply(convert_japanese_date),
        'start_time': df['start_time'],
        'venue': df['venue_details'],
        'venue_id': df['venue_details'].apply(generate_venue_code),
        'race_number': df['race_number'],
        'race_year': df['date'].apply(lambda x: int(x.split('年')[0]) if isinstance(x, str) else None),
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
    
    # データ格納用のリストを初期化
    horses_data = {}  # リストの代わりに辞書を使用
    jockeys_data = {}  # リストの代わりに辞書を使用
    entries_data = []
    
    # レース結果の処理
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
                # 馬情報
                if '馬名' in result and '性齢' in result:
                    horse_name = result['馬名']
                    horse_id = generate_horse_id(horse_name)
                    # 辞書のキーとしてhorse_idを使用して重複を防ぐ
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
                
                # 騎手情報
                if '騎手' in result:
                    jockey_name = result['騎手']
                    jockey_id = generate_jockey_id(jockey_name)
                    # 辞書のキーとしてjockey_idを使用して重複を防ぐ
                    if jockey_id not in jockeys_data:
                        jockeys_data[jockey_id] = {
                            'id': jockey_id,
                            'name': jockey_name
                        }
                
                # エントリー情報
                if '馬名' in result and '騎手' in result:
                    horse_number = result.get('馬番', '')
                    entry_id = generate_entry_id(race_id, horse_number) if horse_number else None
                    horse_id = generate_horse_id(result['馬名'])
                    jockey_id = generate_jockey_id(result['騎手'])
                    
                    # 馬体重の処理
                    horse_weight = None
                    weight_change = None
                    if '馬体重' in result and result['馬体重']:
                        try:
                            weight_parts = result['馬体重'].split('(')
                            if len(weight_parts) > 1:
                                horse_weight = int(weight_parts[0])
                                weight_change = int(weight_parts[1].rstrip(')'))
                        except:
                            pass

                    entries_data.append({
                        'id': entry_id,
                        'race_id': race_id,
                        'horse_id': horse_id,
                        'jockey_id': jockey_id,
                        'horse_number': horse_number,
                        'odds': result.get('単勝', None),
                        'popularity': int(result['人気']) if '人気' in result and result['人気'].isdigit() else None,
                        'horse_weight': horse_weight,
                        'weight_change': weight_change,
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

    # DataFrameの作成
    entries_df = pd.DataFrame({
        'id': [entry['id'] for entry in entries_data],
        'race_id': [entry['race_id'] for entry in entries_data],
        'horse_id': [entry.get('horse_id') for entry in entries_data],
        'jockey_id': [entry.get('jockey_id') for entry in entries_data],
        'horse_number': [entry.get('horse_number', None) for entry in entries_data],
        'odds': [entry.get('odds', None) for entry in entries_data],
        'popularity': [entry.get('popularity', None) for entry in entries_data],
        'horse_weight': [entry.get('horse_weight', None) for entry in entries_data],
        'weight_change': [entry.get('weight_change', None) for entry in entries_data],
        'prize': [entry.get('prize', None) for entry in entries_data],
        'position': [entry.get('position', None) for entry in entries_data],
        'frame_number': [entry.get('frame_number', None) for entry in entries_data],
        'weight': [entry.get('weight', None) for entry in entries_data],
        'time': [entry.get('time', None) for entry in entries_data],
        'margin': [entry.get('margin', None) for entry in entries_data],
        'passing': [entry.get('passing', None) for entry in entries_data],
        'last_3f': [entry.get('last_3f', None) for entry in entries_data]
    })

    # horsesのカラム定義を修正
    horses_df = pd.DataFrame(list(horses_data.values()))

    # jockeysのカラム定義を修正（シンプルなまま）
    jockeys_df = pd.DataFrame(list(jockeys_data.values()))

    # CSVファイルとして保存（NULLを直接出力）
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

def convert_prize(prize_str):
    """賞金文字列を浮動小数点数に変換"""
    if not prize_str or prize_str == '':
        return None
    try:
        # カンマを除去して変換
        return float(prize_str.replace(',', ''))
    except:
        return None

# 検証用の関数
def verify_horse_ids():
    """
    生成されたIDの一意性を検証
    """
    test_names = [
        'リンゲルブルーメ',
        'アグルーメ',
        'リンドウ',
        'ブルーメ',
        'アグル',
        # 似た名前のパターンをいくつか追加
    ]
    
    ids = {}
    for name in test_names:
        horse_id = generate_horse_id(name)
        if horse_id in ids.values():
            # 衝突を検出
            for n, i in ids.items():
                if i == horse_id:
                    print(f"Collision detected: {name} and {n} both got ID {horse_id}")
            return False
        ids[name] = horse_id
        print(f"{name}: {horse_id}")
    
    return True

if __name__ == "__main__":
    input_path = '/Users/aa/Downloads/umamemo.co/netkeiba_2023_race_details_20241117.csv'
    split_race_csv(input_path) 