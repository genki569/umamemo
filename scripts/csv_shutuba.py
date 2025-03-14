import pandas as pd
import json
import os
import re
import csv
from datetime import datetime
from typing import Dict, List
from app import app, db
from app.models import Race, Horse, Jockey, ShutubaEntry

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

    # 既に生成済みのIDがあばそれを返す
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

def name_to_number(name):
    """名前から数値を生成"""
    if not name:
        return 0
    # 名前の各文字のコードポイントを使用して数値を生成
    name_hash = 0
    for char in name:
        name_hash = (name_hash * 31 + ord(char)) & 0xFFFFFFFF
    return abs(name_hash) % 999999999

def extract_date_from_race_id(race_id):
    """レースIDから日付を抽出 (例: 202442112001 -> 2024-11-19)"""
    year = race_id[:4]
    month = race_id[4:6]
    day = race_id[6:8]
    return f"{year}-{month}-{day}"

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

def save_to_database(races_data, horses_data, jockeys_data, entries_data):
    """変換したデータをデータベースに保存"""
    try:
        with app.app_context():
            # バッチサイズを設定
            BATCH_SIZE = 100
            count = 0
            
            # レース情報の保存（バッチ処理）
            for race in races_data:
                count += 1
                race_obj = Race.query.get(race['id'])
                if not race_obj:
                    race_obj = Race(**race)
                    db.session.add(race_obj)
                else:
                    for key, value in race.items():
                        if hasattr(race_obj, key):
                            setattr(race_obj, key, value)
                
                # バッチサイズごとにコミット
                if count % BATCH_SIZE == 0:
                    db.session.commit()
                    print(f"Processed {count} items")
            
            # 馬情報の保存（バッチ処理）
            for horse in horses_data.values():
                count += 1
                horse_obj = Horse.query.get(horse['id'])
                if not horse_obj:
                    horse_obj = Horse(**horse)
                    db.session.add(horse_obj)
                else:
                    for key, value in horse.items():
                        if hasattr(horse_obj, key):
                            setattr(horse_obj, key, value)
                
                if count % BATCH_SIZE == 0:
                    db.session.commit()
                    print(f"Processed {count} items")
            
            # 騎手情報の保存（バッチ処理）
            for jockey in jockeys_data.values():
                count += 1
                jockey_obj = Jockey.query.get(jockey['id'])
                if not jockey_obj:
                    jockey_obj = Jockey(**jockey)
                    db.session.add(jockey_obj)
                else:
                    for key, value in jockey.items():
                        if hasattr(jockey_obj, key):
                            setattr(jockey_obj, key, value)
                
                if count % BATCH_SIZE == 0:
                    db.session.commit()
                    print(f"Processed {count} items")
            
            # 出走表エントリー情報の保存（バッチ処理）
            for entry in entries_data:
                count += 1
                entry_obj = ShutubaEntry.query.get(entry['id'])
                if not entry_obj:
                    entry_obj = ShutubaEntry(**entry)
                    db.session.add(entry_obj)
                else:
                    for key, value in entry.items():
                        if hasattr(entry_obj, key):
                            setattr(entry_obj, key, value)
                
                if count % BATCH_SIZE == 0:
                    db.session.commit()
                    print(f"Processed {count} items")
            
            # 残りのデータをコミット
            db.session.commit()
            print(f"Total processed: {count} items")
            print("データベースへの保存が完了しました")
            
    except Exception as e:
        db.session.rollback()
        print(f"データベース保存エラー: {str(e)}")
        raise

def process_shutuba_data(input_path: str) -> None:
    """出走表CSVを読み込んでデータベースに保存"""
    races_data = []
    horses_data = {}
    jockeys_data = {}
    entries_data = []
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            race_id = row['race_id']
            
            # レース情報を保存
            races_data.append({
                'id': race_id,
                'name': row['race_name'],
                'date': extract_date_from_race_id(race_id),
                'start_time': row['start_time'],
                'venue': row['venue_name'],
                'venue_id': generate_venue_code(row['venue_name']),
                'race_number': int(row['race_number']),
                'race_year': race_id[:4],
                'distance': re.search(r'(\d+)m', row['course_info']).group(1) if re.search(r'(\d+)m', row['course_info']) else None,
                'track_type': 'ダ' if 'ダ' in row['course_info'] else ('芝' if '芝' in row['course_info'] else None),
                'details': row['race_details']
            })
            
            # 出走馬情報をJSONから解析
            entries = json.loads(row['entries'])
            
            for entry in entries:
                horse_name = entry['horse_name']
                horse_id = generate_horse_id(horse_name)
                
                # 性別と年齢を分離
                sex_age = entry.get('sex_age', '')
                sex = sex_age[0] if sex_age else None
                birth_year = str(int(race_id[:4]) - int(sex_age[1:])) if sex_age and len(sex_age) > 1 else None
                
                # 馬情報を保存
                if horse_id not in horses_data:
                    horses_data[horse_id] = {
                        'id': horse_id,
                        'name': horse_name,
                        'birth_year': birth_year,
                        'sex': sex,
                        'trainer': entry.get('trainer_name'),
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                # 騎手情報を保存
                jockey_name = entry.get('jockey_name')
                jockey_id = generate_jockey_id(jockey_name) if jockey_name else None
                if jockey_id and jockey_id not in jockeys_data:
                    jockeys_data[jockey_id] = {
                        'id': jockey_id,
                        'name': jockey_name
                    }
                
                # 出走表エントリー情報を保存
                try:
                    horse_number = int(entry.get('horse_number', 0))
                    entries_data.append({
                        'id': generate_entry_id(race_id, horse_number),
                        'race_id': race_id,
                        'horse_id': horse_id,
                        'jockey_id': jockey_id,
                        'bracket_number': (horse_number - 1) // 2 + 1 if horse_number else None,
                        'horse_number': horse_number,
                        'weight_carry': float(entry.get('weight', 0)),
                        'odds': float(entry.get('odds', 0)),
                        'popularity': int(entry.get('popularity', 0))
                    })
                except (ValueError, TypeError):
                    continue
    
    # データベースに保存
    save_to_database(races_data, horses_data, jockeys_data, entries_data)
    print(f"処理完了: レース数={len(races_data)}, 馬={len(horses_data)}, 騎手={len(jockeys_data)}, エントリー={len(entries_data)}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python csv_shutuba.py <input_csv_path>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    process_shutuba_data(input_path)