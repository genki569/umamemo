from app import app

# デバッグ用のログ
import logging
import os
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info('Starting application')

# シークレットキーが必ず設定されていることを確認
if 'SECRET_KEY' not in app.config or not app.config['SECRET_KEY']:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '3110Genki=')
    logger.info('SECRET_KEY was not set, setting it now')

logger.info(f"SECRET_KEY exists: {bool(app.config.get('SECRET_KEY'))}")
logger.info(f"SECRET_KEY length: {len(app.config.get('SECRET_KEY', ''))}")

if __name__ == "__main__":
    app.run() 