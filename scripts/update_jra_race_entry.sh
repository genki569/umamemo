#!/bin/bash

# 出走表データを更新するスクリプト
# 中央競馬(JRA)の出走表をスクレイピングしてデータベースに保存します

# 設定
APP_DIR="/var/www/umamemo"
LOCK_FILE="/tmp/update_jra_race_entry.lock"
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
log "中央競馬(JRA)出走表データ更新を開始します"

# 1. スクレイピング
cd "$APP_DIR" || handle_error "アプリケーションディレクトリに移動できません"
log "作業ディレクトリ: $(pwd)"

# 実行環境情報を出力
log "システム情報:"
uname -a
log "Pythonのバージョン:"
python --version
log "ディスク容量:"
df -h .

# Xvfb（仮想フレームバッファ）が存在するか確認し、必要に応じて設定
if command -v Xvfb >/dev/null 2>&1; then
    log "Xvfbが利用可能です"
    
    # 既存のXvfbプロセスがあれば終了
    pkill Xvfb 2>/dev/null
    
    # 仮想ディスプレイを開始
    log "仮想ディスプレイを開始します"
    Xvfb :99 -screen 0 1280x1024x24 &
    export DISPLAY=:99
    
    # Xvfbが正常に起動したか確認
    sleep 2
    if ! ps aux | grep -v grep | grep "Xvfb :99" > /dev/null; then
        log "警告: Xvfbの起動に失敗しました。ヘッドレスモードのみで動作します"
    else
        log "Xvfbが正常に起動しました (DISPLAY=$DISPLAY)"
    fi
else
    log "Xvfbが見つかりません。ヘッドレスモードのみで動作します"
fi

# 仮想環境がある場合はアクティベート
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
    log "仮想環境をアクティベートしました"
    python --version
fi

# Pythonのパスを設定
export PYTHONPATH="$APP_DIR:$PYTHONPATH"
log "PYTHONPATH: $PYTHONPATH"

# Playwrightのインストール状態を確認
if ! python -c "from playwright.sync_api import sync_playwright; print('Playwright is installed')" 2>/dev/null; then
    log "Playwrightがインストールされていません。インストールを試みます..."
    pip install playwright
    python -m playwright install
fi

# ブラウザのインストール状態を確認して再インストール
log "Playwrightブラウザを再インストールしています..."
python -m playwright install --force chromium
log "Chromiumブラウザが再インストールされました"

# 環境変数を設定
export PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# ブラウザのキャッシュディレクトリを確認
if [ -d "$HOME/.cache/ms-playwright" ]; then
    log "Playwrightのキャッシュディレクトリが存在します"
    du -sh "$HOME/.cache/ms-playwright" 2>/dev/null || log "キャッシュサイズを取得できません"
    # キャッシュディレクトリの権限を確認
    log "キャッシュディレクトリの権限:"
    ls -ld "$HOME/.cache/ms-playwright"
fi

log "スクレイピングを開始します..."
# スクレイピングスクリプトを実行（デバッグモードで）
PYTHONUNBUFFERED=1 python -m app.scraping.jra_entry_scraper

SCRAPING_RESULT=$?
if [ $SCRAPING_RESULT -ne 0 ]; then
    log "スクレイピングがエラーコード $SCRAPING_RESULT で終了しました"
    
    # 再試行（システムモードでのブラウザインストール）
    log "システムモードでブラウザを再インストールして再試行します..."
    PLAYWRIGHT_BROWSERS_PATH=/usr/local/ms-playwright python -m playwright install --force chromium
    PLAYWRIGHT_BROWSERS_PATH=/usr/local/ms-playwright PYTHONUNBUFFERED=1 python -m app.scraping.jra_entry_scraper
    
    if [ $? -ne 0 ]; then
        handle_error "スクレイピングに失敗しました"
    fi
fi

log "スクレイピングが完了しました"

# CSVファイルの存在確認
CSV_DIR="$APP_DIR/data/race_entries"
log "CSVディレクトリ: $CSV_DIR"

# CSV保存ディレクトリが存在しない場合は作成
if [ ! -d "$CSV_DIR" ]; then
    mkdir -p "$CSV_DIR"
    log "CSVディレクトリを作成しました: $CSV_DIR"
fi

# CSVファイルの一覧を表示
log "生成されたCSVファイル一覧:"
ls -la "$CSV_DIR/"

# 3日分の日付を計算（今日、明日、明後日）
TODAY=$(date '+%Y%m%d')
TOMORROW=$(date -d "tomorrow" '+%Y%m%d' 2>/dev/null || date -v+1d '+%Y%m%d')
DAY_AFTER_TOMORROW=$(date -d "tomorrow + 1 day" '+%Y%m%d' 2>/dev/null || date -v+2d '+%Y%m%d')

log "処理対象日: 今日=${TODAY}, 明日=${TOMORROW}, 明後日=${DAY_AFTER_TOMORROW}"

# 3日分のCSVファイルを処理
for DATE in $TODAY $TOMORROW $DAY_AFTER_TOMORROW
do
    CSV_FILE="$CSV_DIR/jra_race_entries_${DATE}.csv"
    log "CSVファイルのパス: $CSV_FILE"
    
    # ファイルが存在するか確認
    if [ -f "$CSV_FILE" ]; then
        # ファイルのサイズをチェック
        FILE_SIZE=$(stat -c%s "$CSV_FILE" 2>/dev/null || stat -f%z "$CSV_FILE")
        log "CSVファイルのサイズ: ${FILE_SIZE}バイト"
        
        if [ "$FILE_SIZE" -gt 100 ]; then  # 100バイト以上あれば処理する
            log "${DATE}のJRAデータ（${FILE_SIZE}バイト）をデータベースに保存します..."
            python -m scripts.csv_jra_shutuba "$CSV_FILE"
            
            if [ $? -eq 0 ]; then
                log "${DATE}のJRAデータの保存が完了しました"
            else
                log "${DATE}のJRAデータの保存でエラーが発生しました"
            fi
        else
            log "${DATE}のJRA CSVファイルは空か破損しています: $CSV_FILE（${FILE_SIZE}バイト）"
            # ファイルの中身を表示（デバッグ用）
            head -n 10 "$CSV_FILE" 2>/dev/null || log "ファイル内容を表示できません"
        fi
    else
        log "${DATE}のJRA CSVファイルが見つかりません: $CSV_FILE"
    fi
done

# Xvfbを終了（起動している場合）
if [ -n "$DISPLAY" ] && [ "$DISPLAY" = ":99" ]; then
    log "仮想ディスプレイを終了します"
    pkill Xvfb
fi

# タイムアウトプロセスを終了
kill $TIMEOUT_PID 2>/dev/null

# ロックファイルを削除
rm -f "$LOCK_FILE"

log "中央競馬(JRA)出走表データの更新が完了しました"
exit 0 