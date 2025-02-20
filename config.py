import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 現在の設定
    SECRET_KEY = os.environ.get('SECRET_KEY', '3110Genki=')  # 変更不要
    
    # データベース設定
    DB_USER = os.environ.get('DB_USER', '8ya4f_genki')      # 要変更
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '3110Genki=') # 変更不要
    DB_HOST = os.environ.get('DB_HOST', 'mysql49.onamae.ne.jp') # 要変更
    DB_NAME = os.environ.get('DB_NAME', '8ya4f_horced_db')   # 要変更
    
    # 以下は変更不要
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # セッション設定（変更不要）
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    # CSRF設定（変更不要）
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY', 'your-csrf-secret-key-here')
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Stripe設定（既存の値を維持）
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_live_51QLJ2oA32E3Y9pFMeVG7Ai1w729edGTgWxhOGXMXQW1Pjo9Nf3i6TtN0sktkUtGCzRRJi6YQRf49LY0FDWkS0NRG00BlyTVySS')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'ssk_live_51QLJ2oA32E3Y9pFMmbza3j4WjJkahQ1Zw4k4pzVVdic2x3IR07AM0voAigcmy0jxMOTUrGHVjTqB1KQ71qvLIRlm00tR6LlsSO')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'your_webhook_secret')
    
    # 管理者設定（変更不要）
    ADMIN_SECRET_TOKEN = os.environ.get('ADMIN_SECRET_TOKEN', 'your-very-long-and-complex-secret-token-here')
    
    # アップロード設定（変更不要）
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024