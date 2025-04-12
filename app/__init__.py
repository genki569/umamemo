from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_mail import Mail
   # Flask-Mail のインスタンスを作成（ここに移動）
mail = Mail()
# アプリケーションの初期化
app = Flask(__name__)
app.config.from_object(Config)

# メール設定（ここに追加）
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # または別のSMTPサーバー
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # 実際のメールアドレスに変更
app.config['MAIL_PASSWORD'] = 'your-app-password'  # Gmailアプリパスワードに変更
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'  # 送信元アドレス

app.config['DEBUG'] = True
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')

# CSRF保護を最初に初期化
csrf = CSRFProtect()
csrf.init_app(app)

# データベースの初期化
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ログインマネージャーの初期化
login = LoginManager(app)
login.login_view = 'login'

# ベースディレクトリの設定
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(os.path.dirname(BASE_DIR), 'logs')

# ログディレクトリの作成（存在しない場合）
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ログファイルのパス
log_file = os.path.join(LOG_DIR, 'umamemo.log')

# ログハンドラの設定
file_handler = RotatingFileHandler(log_file, maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Umamemo startup')

# モデルを先にインポート
from app import models

# その後にルートをインポート
app.logger.info('About to import routes')
from app import routes

# ルートが登録されたことを確認
app.logger.info('Routes registered:')
for rule in app.url_map.iter_rules():
    app.logger.info(f'Route: {rule.endpoint} -> {rule.rule}')

# アップロードディレクトリの作成
upload_dir = app.config['UPLOAD_FOLDER']
profiles_dir = os.path.join(upload_dir, 'profiles')
if not os.path.exists(profiles_dir):
    os.makedirs(profiles_dir, exist_ok=True)

# アクセスログを記録するミドルウェア
@app.after_request
def log_request(response):
    if not request.path.startswith('/static/') and not request.path.startswith('/favicon.ico'):
        try:
            # ここでAccessLogをインポート
            from app.models import AccessLog
            
            user_id = current_user.id if current_user.is_authenticated else None
            
            access_log = AccessLog(
                user_id=user_id,
                ip_address=request.remote_addr,
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                user_agent=request.user_agent.string if request.user_agent else None
            )
            
            db.session.add(access_log)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Error logging request: {str(e)}")
            db.session.rollback()
            # エラーが発生しても処理を続行
    
    return response

# Jinja2 グローバル関数とフィルターの追加
app.jinja_env.globals.update(max=max, min=min)

# zipフィルターを追加
app.jinja_env.filters['zip'] = zip
