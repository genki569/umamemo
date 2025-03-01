#!/bin/bash
# /Users/aa/Downloads/umamemo.co/scripts/update_race_data.sh

# ベースディレクトリの設定
BASE_DIR="/Users/aa/Downloads/umamemo.co"
cd "${BASE_DIR}"

# スクレイピングの実行
python3 app/daily_race_scraper.py

# スクレイピング成功時のみインポートを実行
if [ $? -eq 0 ]; then
    python3 scripts/import_race_data.py
    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') データの更新が完了しました"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') インポート処理でエラーが発生しました"
        exit 1
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') スクレイピング処理でエラーが発生しました"
    exit 1
fi 