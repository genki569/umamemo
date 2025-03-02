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

# 最後にインポート
from app import routes, models

# ルートの登録確認
app.logger.info('Checking registered routes:')
for rule in app.url_map.iter_rules():
    app.logger.info(f'Route: {rule.endpoint} -> {rule.rule}')
