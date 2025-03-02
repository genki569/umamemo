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
                    race_id, race_name, race_date, post_time,
                    kaisai_info, course_code, race_number, year,
                    grade, distance, track_type, track_direction,
                    weather, track_condition, created_at
                ) VALUES (
                    :race_id, :race_name, :race_date, :post_time,
                    :kaisai_info, :course_code, :race_number, :year,
                    :grade, :distance, :track_type, :track_direction,
                    :weather, :track_condition, NOW()
                )
                ON CONFLICT (race_id) DO UPDATE 
                SET race_name = EXCLUDED.race_name,
                    updated_at = NOW();
            """)
            
            with self.engine.connect() as conn:
                for index, row in df.iterrows():
                    try:
                        params = {
                            "race_id": str(row[0]),
                            "race_name": str(row[1]),
                            "race_date": str(row[2]),
                            "post_time": str(row[3]),
                            "kaisai_info": str(row[4]),
                            "course_code": int(row[5]) if pd.notnull(row[5]) else None,
                            "race_number": int(row[6]) if pd.notnull(row[6]) else None,
                            "year": int(row[7]) if pd.notnull(row[7]) else None,
                            "grade": None,  # gradeは常にNULL
                            "distance": int(row[11]) if pd.notnull(row[11]) else None,
                            "track_type": str(row[12]) if pd.notnull(row[12]) else None,
                            "track_direction": str(row[13]) if pd.notnull(row[13]) else None,
                            "weather": str(row[14]) if pd.notnull(row[14]) else None,
                            "track_condition": str(row[16]) if pd.notnull(row[16]) and row[16] != 'nan' else None
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

    def import_entries(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/entries.csv', header=None)
            df = df.where(pd.notnull(df), None)
            
            stmt = text("""
                INSERT INTO entries (
                    id, race_id, horse_id, jockey_id, bracket_number,
                    odds, popularity, weight, weight_change,
                    arrival_order, finish_time
                ) VALUES (
                    :id, :race_id, :horse_id, :jockey_id, :bracket_number,
                    :odds, :popularity, :weight, :weight_change,
                    :arrival_order, :finish_time
                )
                ON CONFLICT (id) DO UPDATE 
                SET arrival_order = EXCLUDED.arrival_order,
                    finish_time = EXCLUDED.finish_time,
                    updated_at = NOW();
            """)
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    params = {
                        "id": row[0],
                        "race_id": row[1],
                        "horse_id": row[2],
                        "jockey_id": row[3],
                        "bracket_number": row[4],
                        "odds": row[5],
                        "popularity": row[6],
                        "weight": row[7],
                        "weight_change": row[8],
                        "arrival_order": row[9],
                        "finish_time": row[10]
                    }
                    conn.execute(stmt, parameters=params)
                conn.commit()
            
            logging.info(f"出走情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"出走情報のインポートエラー: {e}")
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