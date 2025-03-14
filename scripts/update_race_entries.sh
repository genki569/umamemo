#!/bin/bash
# /var/www/umamemo/scripts/update_race_entries.sh

# ベースディレクトリの設定
BASE_DIR="/var/www/umamemo"
cd "${BASE_DIR}"

# PYTHONPATHを設定
export PYTHONPATH="${BASE_DIR}:${PYTHONPATH}"

# 仮想環境をアクティベート
source venv/bin/activate

# 現在の日付を取得
CURRENT_DATE=$(date '+%Y%m%d')

# スクレイピングの実行
echo "$(date '+%Y-%m-%d %H:%M:%S') 出馬表のスクレイピングを開始します..."
python3 app/scraping/nar_entry_scraper.py

# スクレイピング結果の確認
if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') スクレイピングが完了しました"
    
    # データベースへの保存を実行
    echo "$(date '+%Y-%m-%d %H:%M:%S') データベースへの保存を開始します..."
    python3 scripts/csv_shutuba.py "data/race_entries/nar_race_entries_${CURRENT_DATE}.csv"
    
    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') データベースへの保存が完了しました"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') データベースへの保存でエラーが発生しました"
        exit 1
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') スクレイピングでエラーが発生しました"
    exit 1
fi

# 仮想環境を非アクティベート
deactivate

exit 0 