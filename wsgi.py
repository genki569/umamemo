from app import app, db  # dbをインポート
from flask_migrate import Migrate  # 追加

# Migrateの初期化
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run() 