#!/bin/bash

# 出走表データを更新するスクリプト
# 使用方法: ./update_race_entry.sh [日付(YYYYMMDD)]

# 設定
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$SCRIPT_DIR")"
TEMP_DIR="$APP_DIR/tmp"
LOG_DIR="$APP_DIR/logs"
DATE_FORMAT="%Y-%m-%d %H:%M:%S"

# 日付の設定（引数がなければ今日の日付）
if [ -z "$1" ]; then
    TARGET_DATE=$(date +%Y%m%d)
else
    TARGET_DATE=$1
fi

# ディレクトリの作成
mkdir -p "$TEMP_DIR"
mkdir -p "$LOG_DIR"

# ログファイル
LOG_FILE="$LOG_DIR/update_race_entry_${TARGET_DATE}.log"

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
log "出走表データ更新を開始します（対象日: $TARGET_DATE）"

# CSVファイルのパス
CSV_FILE="$TEMP_DIR/race_entries_${TARGET_DATE}.csv"

# 1. スクレイピングの実行
log "スクレイピングを開始します..."
cd "$APP_DIR" || handle_error "アプリケーションディレクトリに移動できません"

# Pythonの仮想環境がある場合はアクティベート
if [ -f "$APP_DIR/venv/bin/activate" ]; then
    source "$APP_DIR/venv/bin/activate"
fi

# スクレイピングの実行
python -m app.scraping.nar_entry_scraper --date "$TARGET_DATE" --output "$CSV_FILE"
if [ $? -ne 0 ]; then
    handle_error "スクレイピングに失敗しました"
fi

log "スクレイピングが完了しました: $CSV_FILE"

# CSVファイルが存在するか確認
if [ ! -f "$CSV_FILE" ]; then
    handle_error "CSVファイルが生成されませんでした: $CSV_FILE"
fi

# 2. CSVからデータベースへの保存
log "データベースへの保存を開始します..."
python -m scripts.csv_shutuba "$CSV_FILE"
if [ $? -ne 0 ]; then
    handle_error "データベースへの保存に失敗しました"
fi

log "データベースへの保存が完了しました"

# 3. 一時ファイルの削除（オプション）
# rm "$CSV_FILE"
# log "一時ファイルを削除しました: $CSV_FILE"

log "出走表データの更新が完了しました"
exit 0 