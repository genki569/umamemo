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
