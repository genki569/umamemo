from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
# from flask_session import Session  # 不要なので無効化
from config import config_by_name
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_mail import Mail
from datetime import timedelta
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_babel import Babel

# 拡張機能のインスタンス作成
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'login'
csrf = CSRFProtect()
mail = Mail()
bootstrap = Bootstrap()
moment = Moment()
babel = Babel()
# sess = Session()  # 不要なので無効化

# アプリケーションのグローバルインスタンス
# 既存コードとの互換性のために維持
app = None

def create_app(config_name=None):
    """アプリケーションファクトリ関数 - 設定に基づいてアプリインスタンスを作成"""
    global app
    
    # .envファイルの読み込み
    try:
        from dotenv import load_dotenv
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
            print(f"環境変数を{dotenv_path}から読み込みました")
    except ImportError:
        print("python-dotenvがインストールされていません。pip install python-dotenvを実行してください")
    except Exception as e:
        print(f".envファイルの読み込みに失敗しました: {str(e)}")
    
    app = Flask(__name__)
    
    # デバッグモードとエラー処理設定
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.config['PROPAGATE_EXCEPTIONS'] = True  # エラーを伝播させる
    app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = True  # 例外発生時にコンテキストを保持
    
    # 環境に応じた設定を適用
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    # 設定を取得して適用
    app.config.from_object(config_by_name[config_name])
    
    # 重要: シークレットキーを最優先で設定（セッション初期化の前に必要）
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '3110Genki=')
    print(f"【重要】SECRET_KEY設定: {'設定済み' if app.config.get('SECRET_KEY') else '未設定！'}")
    print(f"SECRET_KEY長さ: {len(app.config.get('SECRET_KEY', ''))}文字")
    
    # PostgreSQL接続文字列を明示的に設定（パスワード認証の問題を解決）
    # 環境変数から取得、なければ設定ファイルから、それもなければデフォルト値
    db_user = os.environ.get('DB_USER') or app.config.get('DB_USER', 'umamemo')
    db_password = os.environ.get('DB_PASSWORD') or app.config.get('DB_PASSWORD', '3110Genki')
    db_host = os.environ.get('DB_HOST') or app.config.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME') or app.config.get('DB_NAME', 'umamemo')
    
    # 明示的に接続文字列を設定
    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}/{db_name}'
    
    print(f"【データベース設定】: DB_USER={db_user}, DB_PASSWORD={'*' * len(db_password)}, DB_HOST={db_host}, DB_NAME={db_name}")
    print(f"【接続文字列】: postgresql://{db_user}:{'*' * len(db_password)}@{db_host}/{db_name}")
    
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
    
    # CSRFトークン設定
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']
    
    # CSRFトークンが正しく動作するか確認
    from flask_wtf.csrf import generate_csrf
    try:
        test_token = generate_csrf()
        print(f"CSRFトークンテスト: 生成成功 (長さ: {len(test_token)} 文字)")
    except Exception as e:
        print(f"CSRFトークンテスト: 生成失敗 - {str(e)}")
    
    # セッション設定 - 標準のFlaskセッションを使用
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
    
    # Flask-Sessionは使用しない - 通常のFlaskセッションを使用
    # sess.init_app(app)
    
    # データベース接続のデバッグ情報を表示
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if 'postgresql' in db_uri:
        # パスワードを隠した接続情報を表示
        masked_uri = db_uri.replace(app.config['DB_PASSWORD'], '********') if app.config['DB_PASSWORD'] else db_uri
        print(f"データベース接続情報: {masked_uri}")
        print(f"DB_USER: {app.config['DB_USER']}")
        print(f"DB_HOST: {app.config['DB_HOST']}")
        print(f"DB_NAME: {app.config['DB_NAME']}")
    
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)
    
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
    
    # Blueprintの登録
    # エラーの原因となっているBlueprintをコメントアウト
    '''
    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    '''
    
    # 競馬ラボのBlueprintを使わない
    # 代わりにapp/routes.pyに直接ルートを定義
    
    return app

# アプリケーションインスタンスの作成
# 既存のコードとの互換性のために、グローバル変数appを初期化
app = create_app()
