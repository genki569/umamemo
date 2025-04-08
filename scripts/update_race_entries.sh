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

# 3日分の日付を計算
DAY1=$(date -d "today" '+%Y%m%d')
DAY2=$(date -d "tomorrow" '+%Y%m%d')
DAY3=$(date -d "tomorrow + 1 day" '+%Y%m%d')

# スクレイピングの実行
echo "$(date '+%Y-%m-%d %H:%M:%S') 出馬表のスクレイピングを開始します..."
python3 app/scraping/nar_entry_scraper.py

# スクレイピング結果の確認
if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') スクレイピングが完了しました"
    
    # 3日分のCSVファイルを処理
    for DAY in $DAY1 $DAY2 $DAY3
    do
        CSV_FILE="data/race_entries/nar_race_entries_${DAY}.csv"
        
        # ファイルが存在するか確認
        if [ -f "$CSV_FILE" ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') ${DAY}のデータをデータベースに保存します..."
            python3 scripts/csv_shutuba.py "$CSV_FILE"
            
            if [ $? -eq 0 ]; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') ${DAY}のデータの保存が完了しました"
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') ${DAY}のデータの保存でエラーが発生しました"
            fi
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') ${DAY}のCSVファイルが見つかりません: $CSV_FILE"
        fi
    done
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') スクレイピングでエラーが発生しました"
    exit 1
fi

# 仮想環境を非アクティベート
deactivate

exit 0 