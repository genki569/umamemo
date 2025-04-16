import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 環境変数から設定を読み込むように変更
    # 開発/本番環境の違いを明確に
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('FLASK_TESTING', 'False').lower() == 'true'
    ENV = os.environ.get('FLASK_ENV', 'production')
    
    # 機密情報は環境変数から取得
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
    
    # データベース設定
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '3110Genki')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'umamemo')
    
    # データベースURI
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # セッション設定
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', 30)))
    # 本番環境ではセキュアクッキーを使用
    SESSION_COOKIE_SECURE = ENV == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF設定
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY', SECRET_KEY)
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('CSRF_TIME_LIMIT', 3600))
    # 本番環境ではSSL制限を適用
    WTF_CSRF_SSL_STRICT = ENV == 'production'
    # DELETEリクエストを含む全リクエストでCSRFチェックを有効化
    WTF_CSRF_CHECK_DEFAULT = True
    
    # Stripe設定
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    # 管理者設定
    ADMIN_SECRET_TOKEN = os.environ.get('ADMIN_SECRET_TOKEN', '')
    
    # アップロード設定
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # データベースプール設定
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 3600)),
        'pool_pre_ping': True
    }

    # メール設定
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@umamemo.co')

class DevelopmentConfig(Config):
    """開発環境用の設定"""
    DEBUG = True
    ENV = 'development'
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False

class ProductionConfig(Config):
    """本番環境用の設定"""
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True

class TestingConfig(Config):
    """テスト環境用の設定"""
    TESTING = True
    DEBUG = True
    # テスト用データベース
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # CSRFを無効化（テスト用）
    WTF_CSRF_ENABLED = False

# 環境に応じた設定を選択
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# アプリ起動時に使用する設定を決定
def get_config():
    env = os.environ.get('FLASK_ENV', 'default')
    return config_by_name[env]