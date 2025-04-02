#!/bin/bash

# 出走表データを更新するスクリプト
# 地方競馬の出走表をスクレイピングしてデータベースに保存します

# 設定
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$APP_DIR/logs"
LOCK_FILE="/tmp/update_race_entry.lock"
DATE_FORMAT="%Y-%m-%d %H:%M:%S"
TIMEOUT=3600  # タイムアウト（秒）

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
    # ロックファイルを削除
    rm -f "$LOCK_FILE"
    exit 1
}

# クリーンアップ関数
cleanup() {
    log "スクリプトが中断されました"
    rm -f "$LOCK_FILE"
    exit 1
}

# シグナルハンドラの設定
trap cleanup SIGHUP SIGINT SIGTERM

# ロックファイルの確認
if [ -f "$LOCK_FILE" ]; then
    # ロックファイルが存在する場合、プロセスが実行中かチェック
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null; then
        log "別のプロセスが実行中です (PID: $PID)"
        exit 0
    else
        log "古いロックファイルを削除します"
        rm -f "$LOCK_FILE"
    fi
fi

# ロックファイルの作成
echo $$ > "$LOCK_FILE"

# 開始ログ
log "出走表データ更新を開始します"

# タイムアウト設定
(
    sleep $TIMEOUT
    if [ -f "$LOCK_FILE" ]; then
        PID=$(cat "$LOCK_FILE")
        if ps -p "$PID" > /dev/null; then
            log "タイムアウトしました。プロセスを終了します (PID: $PID)"
            kill -9 "$PID"
        fi
    fi
) &
TIMEOUT_PID=$!

# スクレイピングの実行
log "スクレイピングを開始します..."
cd "$APP_DIR" || handle_error "アプリケーションディレクトリに移動できません"

# 仮想環境がある場合はアクティベート
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
fi

# スクレイピングスクリプトを実行
python -m app.scraping.nar_entry_scraper

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

# タイムアウトプロセスを終了
kill $TIMEOUT_PID 2>/dev/null

# ロックファイルを削除
rm -f "$LOCK_FILE"

log "データベースへの保存が完了しました"
log "出走表データの更新が完了しました"
exit 0 