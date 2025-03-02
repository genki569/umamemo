# import pymysql  # この行を削除または#でコメントアウト
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from markupsafe import escape
import os
import datetime
from flask_caching import Cache
import logging
from logging.handlers import RotatingFileHandler
import sys

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
csrf = CSRFProtect()
cache = Cache()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # アップロードフォルダの設定
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
    
    # アップロードフォルダの作成
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # 拡張機能の初期化
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)
    cache.init_app(app, config={'CACHE_TYPE': 'simple'})
    
    # ログイン設定
    login.login_view = 'login'
    login.login_message = 'このページにアクセスするにはログインが必要です。'
    
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
    
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        if not text:
            return ""
        return escape(text).replace('\n', '<br>')
    
    # ルートの登録
    from app import routes
    app.register_blueprint(routes.bp)
    
    app.logger.info('UmaMemo startup')
    return app
