import pymysql

try:
    connection = pymysql.connect(
        host='localhost',
        user='umamemo_user',
        password='3110Genki=',
        database='umamemo',
        charset='utf8mb4'
    )
    print('データベース接続成功!')
    
    # バージョン確認
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()')
        version = cursor.fetchone()
        print(f'MySQL version: {version[0]}')
        
    connection.close()
    
except Exception as e:
    print(f'エラーが発生しました: {e}')
