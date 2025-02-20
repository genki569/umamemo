from datetime import datetime
import json
import re

class RaceDataConverter:
    @staticmethod
    def parse_race_details(details_str):
        """レース詳細文字列からトラック情報などを抽出"""
        # 例: "ダ左1400m / 天候 : 曇 / ダート : 稍重 / 発走 : 15:30"
        track_info = {}
        
        if not details_str:
            return track_info
            
        parts = details_str.split('/')
        
        # トラック種別と距離を抽出
        if parts and len(parts) > 0:
            track_match = re.match(r'(ダ|芝)(左|右)?(\d+)m', parts[0].strip())
            if track_match:
                track_info['track_type'] = '芝' if track_match.group(1) == '芝' else 'ダート'
                track_info['direction'] = track_match.group(2) if track_match.group(2) else None
                track_info['distance'] = int(track_match.group(3))
        
        # 天候と馬場状態を抽出
        for part in parts:
            if '天候' in part:
                track_info['weather'] = part.split(':')[1].strip()
            elif 'ダート' in part or '芝' in part:
                track_info['track_condition'] = part.split(':')[1].strip()
                
        return track_info

    @staticmethod
    def parse_results(results_str):
        """レース結果文字列をパースしてエントリー情報を抽出"""
        try:
            results = json.loads(results_str)
            entries = []
            
            for result in results:
                entry = {
                    'order_of_finish': result.get('着順'),
                    'post_position': result.get('枠番'),
                    'horse_number': result.get('馬番'),
                    'horse_name': result.get('馬名'),
                    'sex_age': result.get('性齢'),
                    'weight_carried': result.get('斤量'),
                    'jockey_name': result.get('騎手'),
                    'finish_time': result.get('タイム'),
                    'margin': result.get('着差'),
                    'passing_order': result.get('通過'),
                    'last_3f': result.get('上り'),
                    'odds': result.get('単勝'),
                    'popularity': result.get('人気'),
                    'horse_weight': result.get('馬体重'),
                    'trainer': result.get('調教師'),
                    'owner': result.get('馬主'),
                    'prize': result.get('賞金(万円)')
                }
                entries.append(entry)
                
            return entries
        except json.JSONDecodeError:
            return []

    @staticmethod
    def extract_horse_info(entry_data):
        """エントリーデータから馬の情報を抽出"""
        sex_age = entry_data.get('sex_age', '')
        sex = sex_age[0] if sex_age else None
        age = sex_age[1] if len(sex_age) > 1 else None
        
        return {
            'name': entry_data.get('horse_name'),
            'sex': sex,
            'age': age,
            'trainer': entry_data.get('trainer'),
            'owner': entry_data.get('owner')
        }

    @staticmethod
    def extract_jockey_info(entry_data):
        """エントリーデータから騎手の情報を抽出"""
        return {
            'name': entry_data.get('jockey_name')
        }