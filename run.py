#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
アプリケーション起動スクリプト

アプリケーションの実行エントリーポイントとなるスクリプト。
環境変数を読み込み、アプリケーションサーバーを起動します。
"""

import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境設定
env = os.environ.get('FLASK_ENV', 'development')

# ここでアプリケーションをインポート
# load_dotenvの後に行うことで、環境変数がロードされた状態でアプリが初期化される
from app import app

if __name__ == '__main__':
    # アプリケーションの設定
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.environ.get('FLASK_HOST', '0.0.0.0') 
    port = int(os.environ.get('FLASK_PORT', 5000))
    
    # 起動メッセージ
    print(f"Running application in {env} mode")
    print(f"Debug: {debug}, Host: {host}, Port: {port}")
    
    # アプリケーションの実行
    app.run(host=host, port=port, debug=debug) 