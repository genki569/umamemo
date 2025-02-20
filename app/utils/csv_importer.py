from app import db
from app.models import Race, RaceDetail
from datetime import datetime
import csv
import json
import re

def import_race_data(csv_file_path):
    """レース情報をCSVからインポートする"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                # レース詳細情報を解析
                track_info = parse_race_details(row['race_details'])
                
                # レース基本情報を作成
                race = Race(
                    name=row['race_name'],
                    race_number=int(row['race_number']),
                    date=format_date(row['date']),
                    start_time=row['start_time'],
                    track_type=track_info['track_type'],
                    distance=track_info['distance'],
                    direction=track_info['direction'],
                    weather=track_info['weather'],
                    track_condition=track_info['condition'],
                    venue=parse_venue(row['venue_details']),
                    memo=''  # 必要に応じて設定
                )
                db.session.add(race)
                db.session.flush()  # IDを取得するためにflush
                
                # レース詳細情報を作成
                race_detail = RaceDetail(
                    race_id=race.id,
                    details=row['results']
                )
                db.session.add(race_detail)
                
            db.session.commit()
            return True
            
    except Exception as e:
        print(f"インポートエラー: {str(e)}")
        db.session.rollback()
        return False

def parse_race_details(details_str):
    """レース詳細文字列からトラック情報を抽出"""
    # 例: "ダ左900m / 天候 : 曇 / ダート : 稍重 / 発走 : 15:00"
    info = {
        'track_type': None,
        'direction': None,
        'distance': None,
        'weather': None,
        'condition': None
    }
    
    try:
        # トラック種別と向き、距離を抽出
        track_match = re.match(r'(ダ|芝)(左|右)?(\d+)m', details_str)
        if track_match:
            info['track_type'] = '芝' if track_match.group(1) == '芝' else 'ダート'
            info['direction'] = track_match.group(2) if track_match.group(2) else ''
            info['distance'] = int(track_match.group(3))
        
        # 天候を抽出
        weather_match = re.search(r'天候\s*:\s*(\S+)', details_str)
        if weather_match:
            info['weather'] = weather_match.group(1)
        
        # トラック状態を抽出
        condition_match = re.search(r'(ダート|芝)\s*:\s*(\S+)', details_str)
        if condition_match:
            info['condition'] = condition_match.group(2)
            
    except Exception as e:
        print(f"レース詳細解析エラー: {str(e)}")
    
    return info

def parse_venue(venue_str):
    """開催場所情報を解析"""
    # 例: "9回川崎5日目"
    try:
        venue_match = re.search(r'[0-9]+回([^\d]+)', venue_str)
        if venue_match:
            return venue_match.group(1)
    except Exception as e:
        print(f"開催場所解析エラー: {str(e)}")
    return venue_str

def format_date(date_str):
    """日付文字列を整形"""
    # 例: "2024年11月15日" → "2024-11-15"
    try:
        date_obj = datetime.strptime(date_str, '%Y年%m月%d日')
        return date_obj.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"日付解析エラー: {str(e)}")
        return date_str
