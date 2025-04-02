#!/bin/bash

# 出走表データを更新するスクリプト
# 地方競馬の出走表をスクレイピングしてデータベースに保存します

# 設定
APP_DIR="/var/www/umamemo"
LOCK_FILE="/tmp/update_race_entry.lock"
TIMEOUT=3600  # タイムアウト時間（秒）
CURRENT_DATE=$(date '+%Y%m%d')

# ログ関数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# エラーハンドリング関数
handle_error() {
    log "エラー: $1"
    # タイムアウトプロセスを終了
    kill $TIMEOUT_PID 2>/dev/null
    # ロックファイルを削除
    rm -f "$LOCK_FILE"
    exit 1
}

# 既に実行中かチェック
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p $PID > /dev/null; then
        log "既に別のプロセス（PID: $PID）が実行中です"
        exit 1
    else
        log "古いロックファイルを削除します"
        rm -f "$LOCK_FILE"
    fi
fi

# ロックファイルを作成
echo $$ > "$LOCK_FILE"

# タイムアウト処理
(
    sleep $TIMEOUT
    if [ -f "$LOCK_FILE" ]; then
        log "タイムアウトしました。処理を強制終了します"
        PID=$(cat "$LOCK_FILE")
        kill -9 $PID 2>/dev/null
        rm -f "$LOCK_FILE"
    fi
) &
TIMEOUT_PID=$!

# メイン処理
log "出走表データ更新を開始します"

# 1. スクレイピング
cd "$APP_DIR" || handle_error "アプリケーションディレクトリに移動できません"

# 仮想環境がある場合はアクティベート
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
fi

# Playwrightのブラウザが存在するか確認し、なければインストール
if ! python -c "from playwright.sync_api import sync_playwright; exit(0)" 2>/dev/null; then
    log "Playwrightのブラウザをインストールします..."
    python -m playwright install chromium
fi

log "スクレイピングを開始します..."
# スクレイピングスクリプトを実行
python -m app.scraping.nar_entry_scraper

if [ $? -ne 0 ]; then
    handle_error "スクレイピングに失敗しました"
fi

log "スクレイピングが完了しました"

# CSVファイルの存在確認
CSV_DIR="$APP_DIR/data/race_entries"
# スクレイピングで生成された最新のCSVファイルを使用
LATEST_CSV=$(ls -t "$CSV_DIR"/nar_race_entries_*.csv 2>/dev/null | head -1)

if [ -z "$LATEST_CSV" ]; then
    handle_error "CSVファイルが見つかりません"
fi

log "最新のCSVファイルを使用します: $LATEST_CSV"

# 2. CSVからデータベースへの保存
log "データベースへの保存を開始します... ($LATEST_CSV)"
python -m scripts.csv_shutuba "$LATEST_CSV"

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