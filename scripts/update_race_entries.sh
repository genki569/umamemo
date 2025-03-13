#!/bin/bash
# /var/www/umamemo/scripts/update_race_entries.sh

# ベースディレクトリの設定
BASE_DIR="/var/www/umamemo"
cd "${BASE_DIR}"

# PYTHONPATHを設定
export PYTHONPATH="${BASE_DIR}:${PYTHONPATH}"

# 仮想環境をアクティベート
source venv/bin/activate

# スクレイピングの実行
python3 app/scraping/nar_entry_scraper.py

# 実行結果をログに記録
if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') 出馬表の取得が完了しました"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') 出馬表の取得でエラーが発生しました"
    exit 1
fi

# 仮想環境を非アクティベート
deactivate 