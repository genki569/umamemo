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
            # ヘッダーなしでCSVを読み込む
            df = pd.read_csv(f'{self.input_dir}/jockeys.csv', header=None)
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
                        "id": row[0],    # 1列目: ID
                        "name": row[1]    # 2列目: 名前
                    }
                    conn.execute(stmt, parameters=params)
                conn.commit()
            
            logging.info(f"騎手情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"騎手情報のインポートエラー: {e}")
            raise

    def import_races(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/races.csv')
            df = df.where(pd.notnull(df), None)
            
            with self.engine.begin() as conn:
                for _, row in df.iterrows():
                    stmt = text("""
                        INSERT INTO races (
                            race_id, race_name, race_date, post_time, 
                            kaisai_info, course_code, race_number, year,
                            grade, distance, track_type, track_direction,
                            weather, track_condition_turf, track_condition_dirt,
                            created_at, race_info
                        ) VALUES (
                            :race_id, :race_name, :race_date, :post_time,
                            :kaisai_info, :course_code, :race_number, :year,
                            :grade, :distance, :track_type, :track_direction,
                            :weather, :track_condition_turf, :track_condition_dirt,
                            :created_at, :race_info
                        )
                        ON CONFLICT (race_id) DO UPDATE 
                        SET race_name = EXCLUDED.race_name,
                            updated_at = NOW();
                    """)
                    conn.execute(stmt, dict(row))
            
            logging.info(f"レース情報のインポート成功: {len(df)}件")
        except Exception as e:
            logging.error(f"レース情報のインポートエラー: {e}")
            raise

    def import_entries(self):
        try:
            df = pd.read_csv(f'{self.input_dir}/entries.csv')
            df = df.where(pd.notnull(df), None)
            
            with self.engine.begin() as conn:
                for _, row in df.iterrows():
                    stmt = text("""
                        INSERT INTO entries (
                            entry_id, race_id, horse_id, jockey_id, bracket_number,
                            odds, popularity, weight, weight_change, prize,
                            arrival_order, post_position, load_weight, finish_time,
                            margin, corner_position, last_3f
                        ) VALUES (
                            :entry_id, :race_id, :horse_id, :jockey_id, :bracket_number,
                            :odds, :popularity, :weight, :weight_change, :prize,
                            :arrival_order, :post_position, :load_weight, :finish_time,
                            :margin, :corner_position, :last_3f
                        )
                        ON CONFLICT (entry_id) DO UPDATE 
                        SET arrival_order = EXCLUDED.arrival_order,
                            finish_time = EXCLUDED.finish_time,
                            updated_at = NOW();
                    """)
                    conn.execute(stmt, dict(row))
            
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