import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Race, Horse, Entry, Jockey
from datetime import datetime
import pandas as pd

def generate_race_id(date_str, venue, race_number):
    """
    レースIDを生成
    例: 20240321 + 05(東京) + 11(レース番号) = 2024032105011
    """
    # 日付をYYYYMMDD形式に変換
    date = datetime.strptime(date_str, '%Y/%m/%d')
    date_str = date.strftime('%Y%m%d')
    
    # 競馬場コード (2桁)
    venue_codes = {
        # 中央競馬
        '札幌': '01', '函館': '02', '福島': '03', '新潟': '04',
        '東京': '05', '中山': '06', '中京': '07', '京都': '08',
        '阪神': '09', '小倉': '10',
        # 地方競馬
        '門別': '30', '盛岡': '35', '水沢': '36', '浦和': '42',
        '船橋': '43', '大井': '44', '川崎': '45', '金沢': '46',
        '笠松': '47', '名古屋': '48', '園田': '50', '姫路': '51',
        '高知': '54', '佐賀': '55', '中津': '65'
    }
    venue_code = venue_codes.get(venue, '99')
    
    # レース番号を3桁に
    race_num = str(race_number).zfill(3)
    
    return int(f"{date_str}{venue_code}{race_num}")

def parse_race_details(details_text):
    """レース詳細テキストからレース情報を抽出"""
    info = {
        'track_type': None,
        'distance': None,
        'weather': None,
        'track_condition': None
    }
    
    if not details_text:
        return info
        
    parts = details_text.split('/')
    for part in parts:
        part = part.strip()
        if '芝' in part or 'ダ' in part:
            info['track_type'] = '芝' if '芝' in part else 'ダート'
            try:
                info['distance'] = int(''.join(filter(str.isdigit, part)))
            except ValueError:
                pass
        elif '天候' in part:
            info['weather'] = part.replace('天候:', '').strip()
        elif '馬場' in part:
            info['track_condition'] = part.replace('馬場:', '').strip()
            
    return info

def import_race_data(csv_file_path):
    """レースデータをCSVからインポート"""
    app = create_app()
    
    stats = {
        'processed': 0,
        'new_races': 0,
        'new_horses': 0,
        'new_jockeys': 0,
        'skipped_races': 0,
        'errors': 0
    }
    
    with app.app_context():
        try:
            df = pd.read_csv(csv_file_path)
            
            for _, row in df.iterrows():
                try:
                    stats['processed'] += 1
                    
                    # レース番号を抽出
                    race_number = int(''.join(filter(str.isdigit, row['race_name'].split('R')[0])))
                    race_id = generate_race_id(row['date'], row['venue'], race_number)
                    
                    # 既存レースチェック
                    existing_race = Race.query.get(race_id)
                    if existing_race:
                        print(f"スキップ: レースID {race_id} ({row['date']} {row['venue']} {row['race_name']}) は既に存在します")
                        stats['skipped_races'] += 1
                        continue
                    
                    # 新規レースの処理
                    race_info = parse_race_details(row['race_details'])
                    race = Race(
                        id=race_id,
                        name=row['race_name'],
                        date=datetime.strptime(row['date'], '%Y/%m/%d').date(),
                        venue=row['venue'],
                        start_time=row['start_time'],
                        track_type=race_info['track_type'],
                        distance=race_info['distance'],
                        weather=race_info['weather'],
                        track_condition=race_info['track_condition'],
                        details=row['race_details']
                    )
                    db.session.add(race)
                    stats['new_races'] += 1
                    
                    # 出走馬情報の処理
                    results = eval(row['results'])
                    process_race_results(results, race_id, stats)
                    
                    # 100レースごとにコミット
                    if stats['processed'] % 100 == 0:
                        db.session.commit()
                        print(f"中間保存: {stats['processed']}レース処理済み")
                    
                except Exception as e:
                    print(f"エラー: レースID {race_id} の処理中 - {str(e)}")
                    stats['errors'] += 1
                    db.session.rollback()
                    continue
            
            # 残りのデータをコミット
            db.session.commit()
            
            # 結果表示
            print("\n===== インポート結果 =====")
            print(f"処理したレース数: {stats['processed']}")
            print(f"新規レース: {stats['new_races']}")
            print(f"スキップしたレース: {stats['skipped_races']}")
            print(f"新規馬: {stats['new_horses']}")
            print(f"新規騎手: {stats['new_jockeys']}")
            print(f"エラー: {stats['errors']}")
            
            return True
            
        except Exception as e:
            print(f"致命的なエラー: {str(e)}")
            db.session.rollback()
            return False

def process_race_results(results, race_id, stats):
    """レース結果の処理（統計情報を更新）"""
    print(f"処理開始: レースID {race_id}")  # デバッグ追加
    print(f"取得した結果数: {len(results)}")  # デバッグ追加
    
    for result in results:
        try:
            print(f"処理中の馬: {result.get('馬名', 'unknown')}")  # デバッグ追加
            print(f"データ内容: {result}")  # デバッグ追加
            
            # 馬の処理
            horse = Horse.query.filter_by(name=result['馬名']).first()
            if not horse:
                horse = Horse(name=result['馬名'])
                db.session.add(horse)
                stats['new_horses'] += 1
                db.session.flush()  # IDを生成するためにflush
            
            # 騎手の処理
            jockey = Jockey.query.filter_by(name=result['騎手']).first()
            if not jockey:
                jockey = Jockey(name=result['騎手'])
                db.session.add(jockey)
                stats['new_jockeys'] += 1
                db.session.flush()  # IDを生成するためにflush
            
            # エントリーの作成
            entry = Entry(
                race_id=race_id,
                horse_id=horse.id,
                jockey_id=jockey.id,
                frame_number=int(result.get('枠番', 0)) if result.get('枠番', '').isdigit() else None,
                horse_number=int(result.get('馬番', 0)) if result.get('馬番', '').isdigit() else None,
                weight=float(result.get('斤量', 0)) if result.get('斤量', '').replace('.', '').isdigit() else None,
                position=int(result.get('着順', 0)) if result.get('着順', '').isdigit() else None
            )
            print(f"エントリー作成: {entry.horse_number}")  # デバッグ追加
            db.session.add(entry)
            
        except Exception as e:
            print(f"警告: 出走馬データの処理中にエラー - {str(e)}")
            print(f"レースID: {race_id}, 馬名: {result.get('馬名', 'unknown')}")
            continue

# データベース接続テスト部分を追加
def test_db_connection():
    """データベース接続をテスト"""
    app = create_app()
    with app.app_context():
        try:
            # テスト用のクエリを実行
            result = db.session.execute('SELECT 1').scalar()
            print("データベース接続成功!")
            return True
        except Exception as e:
            print(f"データベース接続エラー: {str(e)}")
            return False

# CSVデータの構造を確認
def validate_csv_structure(csv_file_path):
    """CSVファイルの構造を検証"""
    try:
        df = pd.read_csv(csv_file_path)
        required_columns = ['race_name', 'date', 'venue', 'race_details', 'results']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"CSVファイルに必要なカラムがありません: {missing_columns}")
            return False
            
        print("CSVファイルの構造は正常です")
        print("カラム一覧:", df.columns.tolist())
        print("データ件数:", len(df))
        return True
    except Exception as e:
        print(f"CSVファイル検証エラー: {str(e)}")
        return False

# メイン処理を修正
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("使用方法: python import_race_data.py <レースデータのCSVファイル>")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    if not os.path.exists(csv_file_path):
        print(f"エラー: ファイルが見つかりません: {csv_file_path}")
        sys.exit(1)
    
    print("前処理チェックを開始...")
    
    # データベース接続テスト
    if not test_db_connection():
        print("データベース接続に失敗しました。処理を中止します。")
        sys.exit(1)
    
    # CSVファイルの構造チェック
    if not validate_csv_structure(csv_file_path):
        print("CSVファイルの検証に失敗しました。処理を中止します。")
        sys.exit(1)
    
    print("\nレースデータのインポートを開始...")
    success = import_race_data(csv_file_path)
    if success:
        print("レースデータのインポートが正常に完了しました！")
    else:
        print("レースデータのインポートに失敗しました。")
        sys.exit(1)