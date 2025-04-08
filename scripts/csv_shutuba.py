import pandas as pd
import json
import os
import re
import csv
from datetime import datetime
from typing import Dict, List
from app import app, db
from app.models import Race, Horse, Jockey, ShutubaEntry
import argparse
import traceback

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
    """
    レースIDから日付を抽出
    地方競馬のレースID形式: YYYY + 会場コード(2桁) + 月日(4桁) + レース番号(2桁)
    例: 202545040801 -> 2025年4月8日の川崎競馬場(45)の1レース
    """
    race_id_str = str(race_id)
    year = race_id_str[:4]  # 年
    month = race_id_str[6:8]  # 月
    day = race_id_str[8:10]  # 日
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
    """データベースに保存する"""
    try:
        # Flaskアプリケーションコンテキスト内で実行
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
        print(f"データベース保存エラー: {str(e)}")
        traceback.print_exc()
        # Flaskアプリケーションコンテキスト内でロールバック
        with app.app_context():
            db.session.rollback()

def process_shutuba_data(input_path):
    """CSVファイルからデータを読み込み、データベースに保存する"""
    try:
        with app.app_context():
            print(f"CSVファイル {input_path} を読み込んでいます...")
            df = pd.read_csv(input_path)
            print(f"読み込んだレース数: {len(df)}")
            
            # 処理したデータのカウント
            races_count = 0
            
            for _, row in df.iterrows():
                try:
                    # entriesカラムをJSONとしてパース
                    entries_json = row['entries']
                    
                    # 文字列の場合はJSONとしてパース
                    if isinstance(entries_json, str):
                        try:
                            entries = json.loads(entries_json)
                        except json.JSONDecodeError:
                            print(f"警告: JSONデコードエラー: {entries_json[:100]}...")
                            continue
                    else:
                        entries = entries_json
                    
                    # レースIDを取得
                    try:
                        race_id = int(row['race_id'])
                    except (ValueError, TypeError):
                        print(f"警告: 無効なレースID: {row['race_id']}")
                        continue
                    
                    # レースが既に存在するか確認
                    existing_race = Race.query.get(race_id)
                    
                    if not existing_race:
                        # venue_nameをvenueとして使用
                        venue_name = row['venue_name']
                        
                        # 日付情報を取得
                        race_date = datetime.now().date()  # デフォルト値
                        if 'date' in row and pd.notna(row['date']):
                            try:
                                race_date = datetime.strptime(str(row['date']), '%Y-%m-%d').date()
                            except ValueError:
                                pass
                        
                        # レース年を取得
                        race_year = race_date.year if race_date else datetime.now().year
                        
                        # コース情報を解析
                        course_info = row.get('course_info', '')
                        distance = None
                        track_type = None
                        direction = None
                        
                        # コース情報から距離とコース種別を抽出
                        if course_info:
                            # 例: "ダート1200m"
                            distance_match = re.search(r'(\d+)m', course_info)
                            if distance_match:
                                distance = int(distance_match.group(1))
                            
                            if 'ダート' in course_info:
                                track_type = 'ダート'
                            elif '芝' in course_info:
                                track_type = '芝'
                            
                            if '右' in course_info:
                                direction = '右'
                            elif '左' in course_info:
                                direction = '左'
                        
                        # レース情報を保存
                        race = Race(
                            id=race_id,
                            name=row['race_name'],
                            race_number=int(row['race_number']) if pd.notna(row['race_number']) else None,
                            venue=venue_name,
                            venue_id=generate_venue_code(venue_name),
                            date=race_date,
                            start_time=row['start_time'] if 'start_time' in row else None,
                            details=row.get('race_details', '') or row.get('course_info', ''),
                            race_year=race_year,
                            kai=row.get('kai', ''),
                            nichi=row.get('nichi', ''),
                            race_class=row.get('race_class', ''),
                            distance=distance,
                            track_type=track_type,
                            direction=direction,
                            weather=row.get('weather', ''),
                            track_condition=row.get('track_condition', '')
                        )
                        db.session.add(race)
                        db.session.commit()  # レースを先にコミット
                    
                    # 出走表情報を更新
                    update_race_entry(race_id, entries)
                    
                    races_count += 1
                    
                    # 10レースごとに進捗を表示
                    if races_count % 10 == 0:
                        print(f"{races_count}レース処理完了")
                
                except Exception as e:
                    print(f"レース処理中にエラー: {str(e)}")
                    traceback.print_exc()
            
            print(f"処理完了: {races_count}レース")
    
    except Exception as e:
        print(f"データ処理中にエラー: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def calculate_bracket(horse_number):
    """馬番から枠番を計算"""
    if not horse_number:
        return None
    
    horse_number = int(horse_number)
    if horse_number <= 8:
        return horse_number
    elif horse_number <= 16:
        return (horse_number - 1) % 8 + 1
    else:
        return None

def update_race_entry(race_id, entries):
    """レースの出走表情報を更新する"""
    try:
        # 既存のエントリーを削除（オプション）
        # ShutubaEntry.query.filter_by(race_id=race_id).delete()
        
        for entry in entries:
            try:
                # 馬情報の取得または作成
                horse_name = entry.get('horse_name')
                if not horse_name:
                    continue
                    
                horse = Horse.query.filter_by(name=horse_name).first()
                if not horse:
                    horse_id = generate_horse_id(horse_name)
                    sex_age = entry.get('sex_age', '')
                    sex = sex_age[0] if sex_age else None
                    
                    horse = Horse(
                        id=horse_id,
                        name=horse_name,
                        sex=sex
                    )
                    db.session.add(horse)
                    db.session.flush()  # IDを取得するためにflush
                
                # 騎手情報の取得または作成
                jockey_name = entry.get('jockey_name')
                jockey_id = None
                
                if jockey_name:
                    jockey = Jockey.query.filter_by(name=jockey_name).first()
                    if not jockey:
                        jockey_id = generate_jockey_id(jockey_name)
                        jockey = Jockey(
                            id=jockey_id,
                            name=jockey_name
                        )
                        db.session.add(jockey)
                        db.session.flush()
                    else:
                        jockey_id = jockey.id
                
                # 馬番の取得
                horse_number = entry.get('horse_number')
                if horse_number:
                    try:
                        horse_number = int(horse_number)
                    except (ValueError, TypeError):
                        horse_number = None
                
                # 枠番の計算
                bracket_number = calculate_bracket(horse_number) if horse_number else None
                
                # オッズと人気の取得
                odds = entry.get('odds')
                if odds:
                    try:
                        odds = float(odds)
                    except (ValueError, TypeError):
                        odds = None
                
                popularity = entry.get('popularity')
                if popularity:
                    try:
                        popularity = int(popularity)
                    except (ValueError, TypeError):
                        popularity = None
                
                # 斤量の取得
                weight_carry = entry.get('weight')
                if weight_carry:
                    try:
                        weight_carry = float(weight_carry)
                    except (ValueError, TypeError):
                        weight_carry = None
                
                # エントリーIDの生成
                entry_id = generate_entry_id(race_id, horse_number) if horse_number else None
                
                # 既存のエントリーを確認
                existing_entry = ShutubaEntry.query.filter_by(
                    race_id=race_id,
                    horse_id=horse.id
                ).first()
                
                if existing_entry:
                    # 既存のエントリーを更新
                    if jockey_id:
                        existing_entry.jockey_id = jockey_id
                    if bracket_number:
                        existing_entry.bracket_number = bracket_number
                    if horse_number:
                        existing_entry.horse_number = horse_number
                    if weight_carry:
                        existing_entry.weight_carry = weight_carry
                    if odds:
                        existing_entry.odds = odds
                    if popularity:
                        existing_entry.popularity = popularity
                else:
                    # 新しいエントリーを作成
                    shutuba_entry = ShutubaEntry(
                        id=entry_id,
                        race_id=race_id,
                        horse_id=horse.id,
                        jockey_id=jockey_id,
                        bracket_number=bracket_number,
                        horse_number=horse_number,
                        weight_carry=weight_carry,
                        odds=odds,
                        popularity=popularity
                    )
                    db.session.add(shutuba_entry)
                
            except Exception as e:
                print(f"エントリー処理中にエラー: {str(e)}")
                traceback.print_exc()
                continue
        
        # 変更をコミット
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"出走表更新中にエラー: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='CSVファイルからレース出走表をデータベースに保存する')
    parser.add_argument('input_file', type=str, help='入力CSVファイルのパス')
    args = parser.parse_args()
    
    # 入力ファイルの存在確認
    if not os.path.exists(args.input_file):
        print(f"エラー: ファイル {args.input_file} が見つかりません")
        return 1
    
    # データ処理の実行
    success = process_shutuba_data(args.input_file)
    
    if success:
        print("データベースへの保存が完了しました")
        return 0
    else:
        print("データベースへの保存中にエラーが発生しました")
        return 1

if __name__ == "__main__":
    exit(main())