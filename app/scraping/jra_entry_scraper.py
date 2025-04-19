#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中央競馬（JRA）の出馬表をスクレイピングするスクリプト
netkeiba.comから中央競馬の出馬表データを取得し、CSVファイルに保存します。

主な機能:
- 指定された日付の全レースURLを取得
- 各レースの出走表情報（馬名、騎手名、斤量など）を抽出
- 抽出したデータをCSV形式で保存

制限事項:
- netkeiba.comの仕様変更によりスクレイピングが失敗する可能性があります
- 大量のリクエストを短時間に送ると制限される可能性があります

参考: 
- https://webscraper.blog/archives/307
"""

import os
import re
import csv
import time
import json
import traceback
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 依存関係の確認とインストール
try:
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError as e:
    print(f"必要なモジュールが見つかりません: {e}")
    print("必要なパッケージをインストールします...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "selenium", "lxml"])
        print("必要なパッケージのインストールが完了しました。スクリプトを再実行します。")
        # モジュールを再度インポート
        from bs4 import BeautifulSoup
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except Exception as install_error:
        print(f"パッケージのインストールに失敗しました: {install_error}")
        sys.exit(1)

# FLASKのインポートエラーを回避するために条件分岐を追加
try:
    from app import app, db
    from app.models import Race, Horse, Jockey, ShutubaEntry
except ImportError:
    print("警告: Flaskアプリケーションモジュールがインポートできません。スタンドアロンモードで実行します。")
    app = None
    db = None

# 定数
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DEBUG_DIR = 'debug'
CSV_DIR = 'data/race_entries'

def log(message):
    """
    ログメッセージを標準出力に出力する関数
    
    @param message: 出力するメッセージ
    """
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{time_str}] {message}")

def setup_driver() -> webdriver.Chrome:
    """
    Seleniumのドライバーを設定して返す関数
    
    @return: 設定済みのChromeドライバー
    """
    log("Chromeドライバーを設定中...")
    options = Options()
    options.add_argument('--headless')  # ヘッドレスモード
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={USER_AGENT}')
    
    # 環境変数からディスプレイ設定を取得
    display = os.environ.get('DISPLAY')
    if display:
        log(f"ディスプレイ設定を使用: {display}")
    else:
        log("ディスプレイ設定がありません。完全ヘッドレスモードで実行します。")
    
    # ディレクトリが存在することを確認
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1280, 1024)
        log("Chromeドライバーの設定が完了しました")
        return driver
    except Exception as e:
        log(f"ドライバー初期化エラー: {e}")
        raise

def get_kaisai_dates(year: int, month: int, driver: webdriver.Chrome) -> List[str]:
    """
    特定の年月の開催日一覧を取得する関数
    
    @param year: 取得対象年（整数）
    @param month: 取得対象月（整数）
    @param driver: Seleniumのドライバー
    @return: 開催日のリスト（YYYYMMDD形式）
    """
    url = f'https://race.netkeiba.com/top/calendar.html?year={year}&month={month}'
    log(f"カレンダーページにアクセス中: {url}")
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.Calendar_Table')))
        
        # デバッグ用にページを保存
        with open(f"{DEBUG_DIR}/calendar_{year}{month:02d}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # スクリーンショットの保存
        driver.save_screenshot(f"{DEBUG_DIR}/calendar_{year}{month:02d}.png")
        
        # BeautifulSoupでパース
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        kaisai_dates = []
        
        # カレンダーテーブルから開催日を探す（すべてのリンクをチェック）
        for a_tag in soup.select('.Calendar_Table td a'):
            href = a_tag.get('href', '')
            match = re.search(r'kaisai_date=(\d+)', href)
            if match:
                kaisai_date = match.group(1)
                kaisai_dates.append(kaisai_date)
        
        log(f"取得した開催日: {kaisai_dates}")
        return kaisai_dates
    
    except Exception as e:
        log(f"開催日取得エラー: {e}")
        traceback.print_exc()
        return []

def get_race_ids(kaisai_date: str, driver: webdriver.Chrome) -> List[str]:
    """
    特定の開催日のレースID一覧を取得する関数
    
    @param kaisai_date: 開催日（YYYYMMDD形式）
    @param driver: Seleniumのドライバー
    @return: レースIDのリスト
    """
    url = f'https://race.netkeiba.com/top/race_list.html?kaisai_date={kaisai_date}'
    log(f"レース一覧ページにアクセス中: {url}")
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        
        # ページの読み込みを待機（少し余分に待つ）
        time.sleep(3)
        
        # デバッグ用にページを保存
        with open(f"{DEBUG_DIR}/race_list_{kaisai_date}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # スクリーンショットも保存
        driver.save_screenshot(f"{DEBUG_DIR}/race_list_{kaisai_date}.png")
        
        # BeautifulSoupでパース
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        race_ids = []
        
        # 記事のセレクタを使用
        for a_tag in soup.select('.RaceList_DataItem > a:first-of-type'):
            href = a_tag.get('href', '')
            match = re.search(r'race_id=([^&]+)', href)
            if match:
                race_id = match.group(1)
                race_ids.append(race_id)
        
        # バックアップ方法：他のセレクタも試す
        if not race_ids:
            for a_tag in soup.select('a[href*="race_id="]'):
                href = a_tag.get('href', '')
                match = re.search(r'race_id=([^&]+)', href)
                if match:
                    race_id = match.group(1)
                    if race_id not in race_ids:
                        race_ids.append(race_id)
        
        log(f"取得したレースID数: {len(race_ids)}")
        if race_ids:
            for i, race_id in enumerate(race_ids[:3], 1):  # 最初の3件だけ表示
                log(f"レースID {i}: {race_id}")
        
        return race_ids
    
    except Exception as e:
        log(f"レースID取得エラー: {e}")
        traceback.print_exc()
        return []

def get_shutuba_data(race_id: str, driver: webdriver.Chrome) -> Dict:
    """
    特定のレースIDの出馬表データを取得する関数
    
    @param race_id: レースID
    @param driver: Seleniumのドライバー
    @return: 出馬表データを含む辞書
    """
    url = f'https://race.netkeiba.com/race/shutuba.html?race_id={race_id}'
    log(f"出馬表ページにアクセス中: {race_id} - {url}")
    
    race_info = {
        'race_id': race_id,
        'race_name': '',
        'race_date': '',
        'venue': '',
        'race_number': 0,
        'race_details': '',
        'entries': []
    }
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        
        # ページの読み込みを待機（少し余分に待つ）
        time.sleep(2)
        
        # デバッグ用にページを保存
        with open(f"{DEBUG_DIR}/shutuba_{race_id}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # スクリーンショットの保存
        driver.save_screenshot(f"{DEBUG_DIR}/shutuba_{race_id}.png")
        
        # BeautifulSoupでパース
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # レース名
        race_name_elem = soup.select_one('.RaceData_TitleName, .RaceMainMenu .RaceName')
        if race_name_elem:
            race_info['race_name'] = race_name_elem.text.strip()
        
        # レース番号
        race_num_elem = soup.select_one('.RaceData_Num, .RaceNum')
        if race_num_elem:
            race_number_text = race_num_elem.text.strip()
            match = re.search(r'(\d+)', race_number_text)
            if match:
                race_info['race_number'] = int(match.group(1))
        
        # 開催場所と日付
        race_data_elem = soup.select_one('.RaceData_Data')
        if race_data_elem:
            race_data_text = race_data_elem.text.strip()
            
            # 開催場所
            venue_match = re.search(r'(\d+回)([^\d]+)(\d+日)', race_data_text)
            if venue_match:
                race_info['venue'] = venue_match.group(2)
            
            # 日付
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', race_data_text)
            if date_match:
                year, month, day = date_match.groups()
                race_info['race_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # レース詳細情報
        race_info_elem = soup.select_one('.RaceData.fc')
        if race_info_elem:
            race_info['race_details'] = race_info_elem.text.strip()
        
        # 出走馬情報
        horse_rows = soup.select('table.Shutuba_Table tr.HorseList')
        
        for row in horse_rows:
            try:
                horse_data = {}
                
                # 馬番
                umaban_elem = row.select_one('.Umaban')
                if umaban_elem:
                    horse_data['horse_number'] = int(umaban_elem.text.strip())
                
                # 枠番
                waku_elem = row.select_one('.Waku')
                if waku_elem:
                    waku_class = waku_elem.get('class', [])
                    for cls in waku_class:
                        if cls.startswith('Waku'):
                            try:
                                horse_data['frame_number'] = int(cls[4:])
                                break
                            except ValueError:
                                pass
                
                # 馬名
                horse_name_elem = row.select_one('.HorseName a')
                if horse_name_elem:
                    horse_data['horse_name'] = horse_name_elem.text.strip()
                
                # 性齢
                horse_info_elem = row.select_one('.Barei')
                if horse_info_elem:
                    info_text = horse_info_elem.text.strip()
                    if info_text:
                        horse_data['gender'] = info_text[0]  # 最初の文字（牡/牝/セ）
                        try:
                            horse_data['age'] = int(info_text[1:])
                        except ValueError:
                            horse_data['age'] = 0
                
                # 斤量
                weight_elem = row.select_one('.Jockey .JockeyWeight')
                if weight_elem:
                    weight_text = weight_elem.text.strip()
                    weight_match = re.search(r'(\d+\.\d+)', weight_text)
                    if weight_match:
                        horse_data['weight'] = weight_match.group(1)
                
                # 騎手
                jockey_elem = row.select_one('.Jockey a')
                if jockey_elem:
                    horse_data['jockey_name'] = jockey_elem.text.strip()
                
                # 馬体重
                horse_weight_elem = row.select_one('.Weight')
                if horse_weight_elem:
                    weight_text = horse_weight_elem.text.strip()
                    weight_match = re.search(r'(\d+)\(([+-]?\d+)\)', weight_text)
                    if weight_match:
                        horse_data['horse_weight'] = int(weight_match.group(1))
                        horse_data['weight_diff'] = int(weight_match.group(2))
                
                # エントリーとして追加（最低限の情報が含まれていれば）
                if 'horse_name' in horse_data and 'jockey_name' in horse_data:
                    horse_data['entry_id'] = f"{race_id}{horse_data.get('horse_number', 0):02d}"
                    # シェルスクリプトとの互換性のために空フィールドを追加
                    horse_data['odds'] = 0.0
                    horse_data['popularity'] = 0
                    horse_data['trainer_name'] = ''
                    horse_data['race_id'] = race_id
                    
                    race_info['entries'].append(horse_data)
            
            except Exception as e:
                log(f"出走馬データ取得エラー: {e}")
                traceback.print_exc()
                continue
        
        log(f"取得した出走馬数: {len(race_info['entries'])}")
        return race_info
    
    except Exception as e:
        log(f"出馬表取得エラー: {e}")
        traceback.print_exc()
        return race_info

def save_to_csv(entries: List[Dict], date_str: str) -> bool:
    """
    取得したエントリー情報をCSVファイルに保存する関数
    
    @param entries: エントリー情報のリスト
    @param date_str: 日付文字列（YYYYMMDD形式）
    @return: 保存に成功したかどうかのブール値
    """
    if not entries:
        log(f"{date_str}: 保存するエントリーがありません")
        return False
    
    try:
        filepath = os.path.join(CSV_DIR, f'jra_race_entries_{date_str}.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            # フィールド名を定義（シェルスクリプトと互換性のある順序と名前）
            fieldnames = [
                'entry_id', 'race_id', 'horse_number', 'frame_number',
                'horse_name', 'gender', 'age', 'weight', 'jockey_name',
                'horse_weight', 'weight_diff', 'trainer_name', 'odds', 'popularity'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for entry in entries:
                # シェルスクリプトとの互換性のために馬番を整数から文字列に変換
                for key in ['horse_number', 'frame_number', 'age']:
                    if key in entry and entry[key] is not None:
                        entry[key] = str(entry[key])
                        
                # 必要なフィールドだけを含む辞書を作成して書き込む
                row = {field: entry.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        log(f"{date_str}: {len(entries)}件のエントリーを保存しました: {filepath}")
        
        # ファイルサイズを確認
        file_size = os.path.getsize(filepath)
        log(f"CSVファイルのサイズ: {file_size}バイト")
        
        return True
    
    except Exception as e:
        log(f"CSV保存エラー: {e}")
        traceback.print_exc()
        return False

def is_race_day(date_str: str, driver: webdriver.Chrome) -> bool:
    """
    指定された日付がレース開催日かどうかを確認する関数
    
    @param date_str: 確認する日付（YYYY-MM-DD形式）
    @param driver: Seleniumのドライバー
    @return: レース開催日ならTrue、そうでなければFalse
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    year = date_obj.year
    month = date_obj.month
    date_param = date_obj.strftime('%Y%m%d')
    
    # その月の開催日を取得
    kaisai_dates = get_kaisai_dates(year, month, driver)
    
    # 開催日リストに含まれているか確認
    if date_param in kaisai_dates:
        log(f"{date_str}はレース開催日です")
        return True
    
    # 土日の場合は開催されている可能性が高い（バックアップ）
    if date_obj.weekday() >= 5:  # 5=土曜日, 6=日曜日
        # 直接レース一覧ページにアクセスして確認
        url = f'https://race.netkeiba.com/top/race_list.html?kaisai_date={date_param}'
        try:
            driver.get(url)
            time.sleep(2)
            
            # スクリーンショットを保存
            driver.save_screenshot(f"{DEBUG_DIR}/race_check_{date_param}.png")
            
            # ページソースを保存
            with open(f"{DEBUG_DIR}/race_check_{date_param}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            # ページソースを確認
            if 'レース不在' not in driver.page_source and '開催されません' not in driver.page_source:
                # レースリンクの存在を確認
                race_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="race_id="]')
                if race_links:
                    log(f"{date_str}はレース開催日のようです（リンク検出）")
                    return True
        except Exception as e:
            log(f"レース開催確認中にエラー: {e}")
    
    log(f"{date_str}はレース開催日ではないようです")
    return False

def get_jra_race_info_for_dates(dates_list: List[str]) -> Dict[str, List[Dict]]:
    """
    指定された日付リストのJRAレース情報を取得する関数
    
    @param dates_list: 日付文字列のリスト (YYYY-MM-DD形式)
    @return: 日付ごとのエントリー情報を含む辞書
    """
    result = {}
    driver = None
    
    try:
        # Seleniumドライバーを設定
        driver = setup_driver()
        
        # 各日付の処理
        for date_str in dates_list:
            try:
                log(f"\n==== {date_str} の処理を開始 ====")
                
                # 日付をYYYYMMDD形式に変換
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                date_param = date_obj.strftime('%Y%m%d')
                
                # レース開催日かどうか確認
                if not is_race_day(date_str, driver):
                    log(f"{date_str}はレース開催日ではありません")
                    continue
                
                # レースIDを取得
                race_ids = get_race_ids(date_param, driver)
                
                if not race_ids:
                    log(f"{date_str}のレースIDが取得できませんでした")
                    continue
                
                entries = []
                
                # 各レースの処理
                for race_id in race_ids:
                    try:
                        # 出馬表データの取得
                        race_data = get_shutuba_data(race_id, driver)
                        
                        if race_data and race_data['entries']:
                            entries.extend(race_data['entries'])
                            log(f"レースID {race_id}: {len(race_data['entries'])}頭の出走馬情報を取得")
                        else:
                            log(f"レースID {race_id}: 出走馬情報なし")
                        
                        # アクセス間隔を空ける
                        time.sleep(2)
                    
                    except Exception as e:
                        log(f"レース {race_id} の処理中にエラー: {e}")
                        continue
                
                # 結果を保存
                if entries:
                    result[date_param] = entries
                    # CSVに保存
                    save_to_csv(entries, date_param)
                    log(f"{date_str}: 合計 {len(entries)}頭の出走馬情報を取得")
                else:
                    log(f"{date_str}: 出走馬情報なし")
            
            except Exception as e:
                log(f"{date_str}の処理中にエラー: {e}")
                traceback.print_exc()
                continue
        
    except Exception as e:
        log(f"全体処理エラー: {e}")
        traceback.print_exc()
        return result
    finally:
        # ドライバーを閉じる
        if driver:
            try:
                driver.quit()
                log("Chromeドライバーを終了しました")
            except:
                pass
    
    return result

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='JRAの出走表情報をスクレイピングするツール')
    parser.add_argument('--date', type=str, help='スクレイピングする日付（YYYY-MM-DD形式）')
    parser.add_argument('--debug', action='store_true', help='デバッグモードを有効にする')
    args = parser.parse_args()
    
    # デバッグディレクトリの作成
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    
    log("JRA出走表スクレイピングを開始します")
    
    # 開始時刻を記録
    start_time = datetime.now()
    log(f"開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        if args.date:
            try:
                # 日付形式の検証
                target_date = datetime.strptime(args.date, '%Y-%m-%d').strftime('%Y-%m-%d')
                log(f"指定された日付 {target_date} の出走表情報を取得します")
                
                # 指定された日付のレース情報を取得
                result = get_jra_race_info_for_dates([target_date])
                if not result:
                    log(f"{target_date}の出走表情報が取得できませんでした")
                    sys.exit(1)
                
            except ValueError:
                log("日付の形式が不正です。YYYY-MM-DD形式で指定してください")
                sys.exit(1)
        else:
            # 今日から3日間のデータを取得
            log("今日から3日間の出走表情報を取得します")
            
            # 今日から3日間の日付を生成
            today = datetime.now()
            dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
            log(f"処理対象日: {', '.join(dates)}")
            
            # 3日分のレース情報を取得
            result = get_jra_race_info_for_dates(dates)
            if not result:
                log("出走表情報が取得できませんでした")
                sys.exit(1)
        
        # 終了時刻を記録
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        log(f"処理時間: {processing_time:.2f}秒")
        
        log("\nすべての処理が完了しました")
        log(f"CSVファイルは {CSV_DIR} ディレクトリに保存されています")
        log("ファイル名形式: jra_race_entries_YYYYMMDD.csv")
        
        return 0  # 正常終了
        
    except Exception as e:
        log(f"予期しないエラーが発生しました: {e}")
        traceback.print_exc()
        return 1  # エラー終了

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code) 