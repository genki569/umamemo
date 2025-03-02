from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

# 基本的な初期化のみを行う
app = Flask(__name__)
app.config.from_object(Config)

# CSRF保護を追加
csrf = CSRFProtect(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
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

# モデルを先にインポート
from app import models

# その後にルートをインポート
from app import routes

app.logger.info('All routes loaded')

# ルートの登録確認
app.logger.info('Checking registered routes:')
for rule in app.url_map.iter_rules():
    app.logger.info(f'Route: {rule.endpoint} -> {rule.rule}')
