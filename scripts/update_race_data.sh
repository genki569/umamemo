#!/bin/bash
# /var/www/umamemo/scripts/update_race_data.sh

# ベースディレクトリの設定
BASE_DIR="/var/www/umamemo"
cd "${BASE_DIR}"

# 仮想環境をアクティベート
source venv/bin/activate

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

# 仮想環境を非アクティベート
deactivate 