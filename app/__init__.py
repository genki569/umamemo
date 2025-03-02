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

app = Flask(__name__)
app.config.from_object(Config)

# アップロードフォルダの設定
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

# アップロードフォルダの作成
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# キャッシュの設定
cache = Cache(app, config={
    'CACHE_TYPE': 'simple'
})

db = SQLAlchemy(app)
migrate = Migrate(app, db)

login = LoginManager(app)
login.login_view = 'login'
login.login_message = 'このページにアクセスするにはログインが必要です。'

csrf = CSRFProtect(app)

@app.template_filter('nl2br')
def nl2br_filter(text):
    if not text:
        return ""
    return escape(text).replace('\n', '<br>')

from app import routes, models, payments

def create_app():
    app = Flask(__name__)
    
    # デバッグモードを有効化
    app.config['DEBUG'] = True
    
    # データベース設定
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/dbname'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
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
    
    db.init_app(app)
    
    # ルートの登録
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app
