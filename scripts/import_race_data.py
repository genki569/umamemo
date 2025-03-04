import pandas as pd
from sqlalchemy import create_engine, text
import logging
from datetime import datetime
import os
import sys

class RaceDataImporter:
    def __init__(self):
        # データベース接続情報
        self.db_user = os.environ.get('DB_USER', 'umamemo')
        self.db_password = os.environ.get('DB_PASSWORD', '3110Genki')
        self.db_host = os.environ.get('DB_HOST', 'localhost')
        self.db_name = os.environ.get('DB_NAME', 'umamemo')
        
        self.db_uri = f'postgresql://{self.db_user}:{self.db_password}@{self.db_host}/{self.db_name}'
        self.engine = create_engine(self.db_uri)
        
        self.input_dir = 'scripts/output'
        self.setup_logging()

    def setup_logging(self):
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        logging.basicConfig(
            filename=f'logs/db_import_{datetime.now().strftime("%Y%m%d")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)

    def import_horses(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/horses.csv')
            df = df.where(pd.notnull(df), None)
            
            stmt = text("""
                INSERT INTO horses (id, name, sex, memo, updated_at, created_at)
                VALUES (:id, :name, :sex, NULL, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name,
                    sex = EXCLUDED.sex,
                    updated_at = NOW();
            """)
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    params = {
                        "id": row.iloc[0],    # 1列目: ID
                        "name": row.iloc[1],   # 2列目: 名前
                        "sex": row.iloc[3]     # 4列目: 性別
                    }
                    conn.execute(stmt, parameters=params)
                conn.commit()
            
            logging.info(f"馬情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"馬情報のインポートエラー: {e}")
            raise

    def import_jockeys(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/jockeys.csv')
            df = df.where(pd.notnull(df), None)
            
            stmt = text("""
                INSERT INTO jockeys (id, name)
                VALUES (:id, :name)
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name;
            """)
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    params = {
                        "id": row.iloc[0],    # 1列目: ID
                        "name": row.iloc[1]    # 2列目: 名前
                    }
                    conn.execute(stmt, parameters=params)
                conn.commit()
            
            logging.info(f"騎手情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"騎手情報のインポートエラー: {e}")
            raise

    def import_races(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/races.csv', header=None)
            df = df.where(pd.notnull(df), None)
            
            stmt = text("""
                INSERT INTO races (
                    id, name, date, start_time,
                    venue, venue_id, race_number, race_year,
                    kai, nichi, race_class, distance,
                    track_type, direction, weather,
                    track_condition, memo, details,
                    created_at
                ) VALUES (
                    :id, :name, :date, :start_time,
                    :venue, :venue_id, :race_number, :race_year,
                    :kai, :nichi, :race_class, :distance,
                    :track_type, :direction, :weather,
                    :track_condition, :memo, :details,
                    NOW()
                )
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name;
            """)
            
            def safe_int(value):
                try:
                    if pd.isna(value) or str(value).lower() == 'nan':
                        return None
                    return int(float(value))
                except (ValueError, TypeError):
                    return None
            
            def safe_str(value):
                if pd.isna(value) or str(value).lower() == 'nan':
                    return None
                return str(value).strip()
            
            with self.engine.connect() as conn:
                for index, row in df.iterrows():
                    try:
                        params = {
                            "id": safe_str(row[0]),           # レースID
                            "name": safe_str(row[1]),         # レース名
                            "date": safe_str(row[2]),         # 開催日
                            "start_time": safe_str(row[3]),   # 発走時刻
                            "venue": safe_str(row[4]),        # 開催場所
                            "venue_id": safe_str(row[5]),     # 開催場所ID
                            "race_number": safe_int(row[6]),  # レース番号
                            "race_year": safe_int(row[7]),    # 開催年
                            "kai": safe_str(row[8]),          # 開催回
                            "nichi": safe_str(row[9]),        # 開催日目
                            "race_class": safe_str(row[10]),  # クラス
                            "distance": safe_int(row[11]),    # 距離
                            "track_type": safe_str(row[12]),  # トラック種別
                            "direction": safe_str(row[13]),   # 左右回り
                            "weather": safe_str(row[14]),     # 天候
                            "track_condition": safe_str(row[16]), # 馬場状態
                            "memo": None,                     # メモ（現時点では使用しない）
                            "details": None                   # 詳細（現時点では使用しない）
                        }
                        conn.execute(stmt, parameters=params)
                    except Exception as e:
                        print(f"Error on row {index}:", row.tolist())
                        print(f"Params:", params)
                        raise
                conn.commit()
            
            logging.info(f"レース情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"レース情報のインポートエラー: {e}")
            raise

    def safe_int(self, value):
        try:
            if pd.isna(value) or str(value).lower() == 'nan':
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def safe_float(self, value):
        try:
            if pd.isna(value) or str(value).lower() == 'nan':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_str(self, value):
        if pd.isna(value) or str(value).lower() == 'nan':
            return None
        return str(value)

    def generate_entry_id(self, race_id, horse_number):
        """
        レースIDと馬番から一意のエントリーIDを生成
        """
        return int(f"{race_id}{horse_number:02d}")

    def import_entries(self):
        try:
            print("\n=== インポート処理開始 ===")
            df = pd.read_csv(f'{self.input_dir}/entries.csv', header=None)
            print(f"デバッグ: 読み込んだ総行数: {len(df)}")
            df = df.where(pd.notnull(df), None)
            
            stmt = text("""
                INSERT INTO entries (
                    id, race_id, horse_id, jockey_id,
                    horse_number, odds, popularity, horse_weight,
                    weight_change, prize, position, frame_number,
                    weight, time, margin, passing, last_3f
                ) VALUES (
                    :id, :race_id, :horse_id, :jockey_id,
                    :horse_number, :odds, :popularity, :horse_weight,
                    :weight_change, :prize, :position, :frame_number,
                    :weight, :time, :margin, :passing, :last_3f
                )
                ON CONFLICT (id) DO UPDATE 
                SET 
                    horse_id = EXCLUDED.horse_id,
                    jockey_id = EXCLUDED.jockey_id,
                    horse_number = EXCLUDED.horse_number,
                    odds = EXCLUDED.odds,
                    popularity = EXCLUDED.popularity,
                    horse_weight = EXCLUDED.horse_weight,
                    weight_change = EXCLUDED.weight_change,
                    prize = EXCLUDED.prize,
                    position = EXCLUDED.position,
                    frame_number = EXCLUDED.frame_number,
                    weight = EXCLUDED.weight,
                    time = EXCLUDED.time,
                    margin = EXCLUDED.margin,
                    passing = EXCLUDED.passing,
                    last_3f = EXCLUDED.last_3f
                RETURNING id, horse_number, position, time;
            """)
            
            print("\n=== UPSERT実行 ===")
            with self.engine.begin() as conn:
                for index, row in df.iterrows():
                    entry_id = self.generate_entry_id(row[1], row[4])
                    params = {
                        "id": entry_id,
                        "race_id": self.safe_str(row[1]),
                        "horse_id": self.safe_int(row[2]),
                        "jockey_id": self.safe_int(row[3]),
                        "horse_number": self.safe_int(row[4]),
                        "odds": self.safe_float(row[5]),
                        "popularity": self.safe_int(row[6]),
                        "horse_weight": self.safe_int(row[7]),
                        "weight_change": self.safe_int(row[8]),
                        "prize": self.safe_float(row[9]),
                        "position": self.safe_int(row[10]),
                        "frame_number": self.safe_int(row[11]),
                        "weight": self.safe_float(row[12]),
                        "time": self.safe_str(row[13]),
                        "margin": self.safe_str(row[14]),
                        "passing": self.safe_str(row[15]),
                        "last_3f": self.safe_float(row[16])
                    }
                    
                    print(f"\n処理中: レースID {row[1]}, 馬番{row[4]}")
                    result = conn.execute(stmt, parameters=params)
            
            print("\n=== インポート処理完了 ===")
            
        except Exception as e:
            print(f"エラー発生: {str(e)}")
            raise

    def import_all(self):
        try:
            logging.info("データインポート開始")
            self.import_horses()
            self.import_jockeys()
            self.import_races()
            self.import_entries()
            logging.info("全データのインポート完了")
        except Exception as e:
            logging.error(f"インポート処理でエラーが発生: {e}")
            sys.exit(1)

def main():
    importer = RaceDataImporter()
    importer.import_all()

if __name__ == "__main__":
    main()