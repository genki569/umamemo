def generate_sql_from_csv(csv_file_path, output_sql_path):
    """CSVからSQLファイルを生成"""
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            with open(output_sql_path, 'w', encoding='utf-8') as sql_file:
                # トランザクション開始
                sql_file.write('START TRANSACTION;\n\n')
                
                for row in reader:
                    if not row['results'] or row['results'] == '[]':
                        continue
                    
                    results = json.loads(row['results'].replace("'", '"'))
                    
                    # レース情報のINSERT文
                    race_sql = generate_race_sql(row)
                    sql_file.write(race_sql + '\n')
                    
                    # 馬、騎手、エントリー情報のINSERT文
                    for result in results:
                        horse_sql = generate_horse_sql(result)
                        jockey_sql = generate_jockey_sql(result)
                        entry_sql = generate_entry_sql(row, result)
                        
                        sql_file.write(horse_sql + '\n')
                        sql_file.write(jockey_sql + '\n')
                        sql_file.write(entry_sql + '\n')
                
                # トランザクション終了
                sql_file.write('\nCOMMIT;')
                
    except Exception as e:
        print(f"エラー: {str(e)}")

def generate_race_sql(row):
    """レース情報のINSERT文を生成"""
    date = datetime.strptime(row['date'], '%Y年%m月%d日').date()
    return f"""
    INSERT IGNORE INTO races (name, date, venue, start_time, race_details)
    VALUES (
        '{escape_sql(row['race_name'])}',
        '{date}',
        '{escape_sql(row['venue'])}',
        '{row['start_time']}',
        '{escape_sql(row['race_details'])}'
    );
    """

def generate_horse_sql(result):
    """馬情報のINSERT文を生成"""
    return f"""
    INSERT IGNORE INTO horses (name)
    VALUES ('{escape_sql(result['馬名'])}');
    """

def generate_jockey_sql(result):
    """騎手情報のINSERT文を生成"""
    return f"""
    INSERT IGNORE INTO jockeys (name)
    VALUES ('{escape_sql(result['騎手'])}');
    """

def escape_sql(text):
    """SQLインジェクション対策"""
    if text is None:
        return ''
    return text.replace("'", "''") 