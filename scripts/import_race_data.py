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
            
            upsert_query = """
                INSERT INTO horses (id, name, sex, memo, updated_at, created_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name,
                    sex = EXCLUDED.sex,
                    memo = EXCLUDED.memo,
                    updated_at = NOW();
            """
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    conn.execute(text(upsert_query), 
                               [row['id'], row['name'], row['sex'], row['memo']])
                conn.commit()
            
            logging.info(f"馬情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"馬情報のインポートエラー: {e}")
            raise

    def import_jockeys(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/jockeys.csv')
            df = df.where(pd.notnull(df), None)
            
            upsert_query = """
                INSERT INTO jockeys (id, name)
                VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE 
                SET name = EXCLUDED.name;
            """
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    conn.execute(text(upsert_query), 
                               [row['id'], row['name']])
                conn.commit()
            
            logging.info(f"騎手情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"騎手情報のインポートエラー: {e}")
            raise

    def import_races(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/races.csv')
            df = df.where(pd.notnull(df), None)
            
            upsert_query = """
                INSERT INTO races (
                    race_id, race_name, race_date, post_time, 
                    kaisai_info, course_code, race_number, year,
                    grade, distance, track_type, track_direction,
                    weather, track_condition_turf, track_condition_dirt,
                    created_at, race_info
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $15,
                    $16, $17
                )
                ON CONFLICT (race_id) DO UPDATE 
                SET race_name = EXCLUDED.race_name,
                    updated_at = NOW();
            """
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    params = [
                        row['race_id'], row['race_name'], row['race_date'], 
                        row['post_time'], row['kaisai_info'], row['course_code'],
                        row['race_number'], row['year'], row['grade'],
                        row['distance'], row['track_type'], row['track_direction'],
                        row['weather'], row['track_condition_turf'],
                        row['track_condition_dirt'], row['created_at'],
                        row['race_info']
                    ]
                    conn.execute(text(upsert_query), params)
                conn.commit()
            
            logging.info(f"レース情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"レース情報のインポートエラー: {e}")
            raise

    def import_entries(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/entries.csv')
            df = df.where(pd.notnull(df), None)
            
            upsert_query = """
                INSERT INTO entries (
                    entry_id, race_id, horse_id, jockey_id, bracket_number,
                    odds, popularity, weight, weight_change, prize,
                    arrival_order, post_position, load_weight, finish_time,
                    margin, corner_position, last_3f
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17
                )
                ON CONFLICT (entry_id) DO UPDATE 
                SET arrival_order = EXCLUDED.arrival_order,
                    finish_time = EXCLUDED.finish_time,
                    updated_at = NOW();
            """
            
            with self.engine.connect() as conn:
                for _, row in df.iterrows():
                    params = [
                        row['entry_id'], row['race_id'], row['horse_id'],
                        row['jockey_id'], row['bracket_number'], row['odds'],
                        row['popularity'], row['weight'], row['weight_change'],
                        row['prize'], row['arrival_order'], row['post_position'],
                        row['load_weight'], row['finish_time'], row['margin'],
                        row['corner_position'], row['last_3f']
                    ]
                    conn.execute(text(upsert_query), params)
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