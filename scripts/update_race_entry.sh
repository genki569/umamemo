#!/bin/bash

# 出走表データを更新するスクリプト
# 地方競馬の出走表をスクレイピングしてデータベースに保存します

# 設定
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$APP_DIR/logs"
DATE_FORMAT="%Y-%m-%d %H:%M:%S"

# ディレクトリの作成
mkdir -p "$LOG_DIR"

# 現在の日時を取得
CURRENT_DATE=$(date +%Y%m%d)

# ログファイル
LOG_FILE="$LOG_DIR/update_race_entry_${CURRENT_DATE}.log"

# ログ関数
log() {
    echo "[$(date +"$DATE_FORMAT")] $1" | tee -a "$LOG_FILE"
}

# エラーハンドリング
handle_error() {
    log "エラー: $1"
    exit 1
}

# 開始ログ
log "出走表データ更新を開始します"

# 1. スクレイピングの実行
log "スクレイピングを開始します..."
cd "$APP_DIR" || handle_error "アプリケーションディレクトリに移動できません"

# Pythonの仮想環境がある場合はアクティベート
if [ -f "$APP_DIR/venv/bin/activate" ]; then
    source "$APP_DIR/venv/bin/activate"
fi

# スクレイピングスクリプトを実行
python -c "
from app.scraping.nar_entry_scraper import *
import time

# スクレイピングを実行
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    # レースURLを取得（既存の関数を使用）
    race_urls = get_race_urls(page, context)
    print(f'{len(race_urls)}件のレースURLを取得しました')
    
    # 各レースの出走表を取得
    race_entries = []
    for race_url in race_urls:
        try:
            entry_info = scrape_race_entry(page, race_url)
            if entry_info:
                race_entries.append(entry_info)
                # CSVに保存
                save_to_csv(entry_info)
                print(f'レース情報を取得しました: {entry_info.get(\"race_name\", \"不明\")}')
                time.sleep(1)  # サーバー負荷軽減のため
        except Exception as e:
            print(f'レース情報取得エラー: {str(e)}')
    
    browser.close()

print(f'{len(race_entries)}件のレース情報を取得しました')
"

if [ $? -ne 0 ]; then
    handle_error "スクレイピングに失敗しました"
fi

log "スクレイピングが完了しました"

# CSVファイルの存在確認
CSV_DIR="$APP_DIR/data/race_entries"
CSV_FILE="$CSV_DIR/nar_race_entries_${CURRENT_DATE}.csv"

if [ ! -f "$CSV_FILE" ]; then
    log "警告: 今日のCSVファイルが見つかりません。最新のCSVファイルを探します..."
    # 最新のCSVファイルを探す
    LATEST_CSV=$(ls -t "$CSV_DIR"/nar_race_entries_*.csv 2>/dev/null | head -1)
    
    if [ -z "$LATEST_CSV" ]; then
        handle_error "CSVファイルが見つかりません"
    fi
    
    CSV_FILE="$LATEST_CSV"
    log "最新のCSVファイルを使用します: $CSV_FILE"
fi

# 2. CSVからデータベースへの保存
log "データベースへの保存を開始します... ($CSV_FILE)"
python -m scripts.csv_shutuba "$CSV_FILE"
if [ $? -ne 0 ]; then
    handle_error "データベースへの保存に失敗しました"
fi

log "データベースへの保存が完了しました"
log "出走表データの更新が完了しました"
exit 0 