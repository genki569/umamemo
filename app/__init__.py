from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

# アプリケーションの初期化
app = Flask(__name__)
app.config.from_object(Config)

# データベースの初期化
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ログイン管理の初期化
login = LoginManager(app)
login.login_view = 'login'

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

# モデルとルートのインポート
from app import models, routes

# ルートの登録確認
app.logger.info('Checking registered routes:')
for rule in app.url_map.iter_rules():
    app.logger.info(f'Route: {rule.endpoint} -> {rule.rule}')
