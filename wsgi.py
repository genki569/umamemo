from app import app

# デバッグ用のログ
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info('Starting application')

if __name__ == "__main__":
    app.run() 