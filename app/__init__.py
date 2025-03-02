from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

# データベースとアプリケーションの初期化を分離
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 拡張機能の初期化
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    # ログ設定
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/umamemo.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('UmaMemo startup')

    with app.app_context():
        # ルートの登録
        from app import routes
        app.logger.info('Routes registered')
        
        # 登録されたルートの確認
        for rule in app.url_map.iter_rules():
            app.logger.info(f'Route registered: {rule.endpoint} -> {rule.rule}')

    return app

# アプリケーションのインスタンスを作成
app = create_app()
