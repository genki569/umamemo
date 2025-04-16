from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from config import config_by_name
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_mail import Mail

# 拡張機能のインスタンス作成
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'login'
csrf = CSRFProtect()
mail = Mail()

# アプリケーションのグローバルインスタンス
# 既存コードとの互換性のために維持
app = None

def create_app(config_name=None):
    """アプリケーションファクトリ関数 - 設定に基づいてアプリインスタンスを作成"""
    global app
    
    app = Flask(__name__)
    
    # 環境に応じた設定を適用
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    # 設定を取得して適用
    app.config.from_object(config_by_name[config_name])
    
    # メール設定の初期化（環境変数から取得）
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', app.config.get('MAIL_SERVER'))
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', app.config.get('MAIL_PORT')))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', str(app.config.get('MAIL_USE_TLS'))).lower() in ['true', 'on', '1']
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', str(app.config.get('MAIL_USE_SSL'))).lower() in ['true', 'on', '1']
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', app.config.get('MAIL_USERNAME'))
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', app.config.get('MAIL_PASSWORD'))
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_DEFAULT_SENDER'))
    
    # アップロードディレクトリの設定
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    
    # 各種拡張機能の初期化
    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    
    # ログインメッセージを日本語に変更
    login.login_message = 'このページにアクセスするにはログインが必要です。'
    login.login_message_category = 'info'
    
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
    
    return app

# アプリケーションインスタンスの作成
# 既存のコードとの互換性のために、グローバル変数appを初期化
app = create_app()
