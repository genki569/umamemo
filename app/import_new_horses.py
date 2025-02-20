import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Horse
import csv

def import_new_horses(csv_file_path):
    app = create_app()
    
    # 統計用カウンター
    stats = {
        'processed': 0,
        'new_horses': 0,
        'updated_horses': 0,
        'skipped': 0,
        'errors': 0
    }
    
    with app.app_context():
        print(f"Opening file: {csv_file_path}")
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
                csv_reader = csv.DictReader(file)
                
                for row in csv_reader:
                    stats['processed'] += 1
                    try:
                        # 既存の馬をチェック
                        horse = Horse.query.filter_by(name=row['name']).first()
                        
                        # birth_yearの処理
                        birth_year = None
                        if row.get('birth_year'):
                            try:
                                birth_year = int(row['birth_year'])
                            except ValueError:
                                print(f"無効な生年: {row['name']}: {row['birth_year']}")
                        
                        # 血統情報などの付加情報を作成
                        pedigree_info = {
                            'father': row.get('father', ''),
                            'mother': row.get('mother', ''),
                            'owner': row.get('owner', '')
                        }
                        memo = f"Father: {pedigree_info['father']}, Mother: {pedigree_info['mother']}, Owner: {pedigree_info['owner']}"
                        
                        if horse:
                            # 既存の馬の情報を更新するかチェック
                            updated = False
                            if not horse.sex and row.get('sex'):
                                horse.sex = row['sex']
                                updated = True
                            if not horse.birth_year and birth_year:
                                horse.birth_year = birth_year
                                updated = True
                            if not horse.trainer and row.get('trainer'):
                                horse.trainer = row['trainer']
                                updated = True
                            if not horse.memo and any(pedigree_info.values()):
                                horse.memo = memo
                                updated = True
                            
                            if updated:
                                stats['updated_horses'] += 1
                                print(f"更新: {horse.name}")
                            else:
                                stats['skipped'] += 1
                                print(f"スキップ: {horse.name} (情報に更新なし)")
                        else:
                            # 新規馬を追加
                            new_horse = Horse(
                                name=row['name'],
                                sex=row.get('sex', ''),
                                birth_year=birth_year,
                                trainer=row.get('trainer', '')
                            )
                            db.session.add(new_horse)
                            stats['new_horses'] += 1
                            print(f"新規追加: {new_horse.name}")
                        
                        # 100件ごとにコミット
                        if len(db.session.new) >= 100:
                            db.session.commit()
                            print("バッチコミット完了")
                            
                    except Exception as e:
                        print(f"エラー発生 {row.get('name')}: {str(e)}")
                        stats['errors'] += 1
                        db.session.rollback()
                        continue
                
                # 残りのデータをコミット
                db.session.commit()
                print("最終コミット完了")
                
        except Exception as e:
            print(f"ファイル処理エラー: {str(e)}")
            return False
        
        # 結果の表示
        print("\n===== インポート結果 =====")
        print(f"処理した馬の数: {stats['processed']}")
        print(f"新規追加: {stats['new_horses']}")
        print(f"情報更���: {stats['updated_horses']}")
        print(f"スキップ: {stats['skipped']}")
        print(f"エラー: {stats['errors']}")
        
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("使用方法: python import_new_horses.py <馬データのCSVファイル>")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    if not os.path.exists(csv_file_path):
        print(f"エラー: ファイルが見つかりません: {csv_file_path}")
        sys.exit(1)
    
    print("馬データのインポートを開始...")
    success = import_new_horses(csv_file_path)
    if success:
        print("馬データのインポートが正常に完了しました！")
    else:
        print("馬データのインポートに失敗しました。")
        sys.exit(1) 