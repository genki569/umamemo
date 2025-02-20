#中央競馬
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
import pickle
import random

HEADERS = [
    '着順', '枠番', '馬番', '馬名', '性齢', '斤量', '騎手',
    'タイム', '着差', 'ﾀｲﾑ指数', '通過', '上り', '単勝',
    '人気', '馬体重', '調教ﾀｲﾑ', '厩舎ｺﾒﾝﾄ', '備考',
    '調教師', '馬主', '賞金(万円)'
]

def requests_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def scrape_race_list(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = session.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    race_table = soup.find('table', class_='race_table_01')
    race_urls = []
    
    if race_table is None:
        return []
    
    for row in race_table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) > 4:
            race_url = 'https://db.netkeiba.com' + cols[4].find('a')['href']
            race_urls.append(race_url)
    return race_urls

def extract_venue(venue_info):
    """競馬場名を抽出（地方・中央両方に対応）"""
    venue = ''
    if '回' in venue_info and '日目' in venue_info:
        # 中央馬の場合
        venue = venue_info.split('回')[1].split('日目')[0]
    else:
        # 地方競馬の場合
        venue = venue_info.split()[0] if venue_info else ''
    return venue.strip()

def scrape_race_details(url, session):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = session.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        race_data = {}  # 初期化
        
        # レース名の取得
        race_name_elem = soup.select_one('div.data_intro h1, .racedata h1')
        if not race_name_elem:
            print(f"レース名が見つかりません: {url}")
            return None
        
        race_name = race_name_elem.text.strip()
        race_name = race_name.replace('過去の', '').replace('\n', '')
        race_data['race_name'] = race_name

        # レース情報の取得を改善
        race_data_elem = soup.select_one('.data_intro')
        if race_data_elem:
            # レース番号の取得
            race_number = race_data_elem.select_one('dt').text.strip() if race_data_elem.select_one('dt') else ''
            race_data['race_number'] = race_number.replace('R', '').strip()
            
            # 開催情報の取得
            race_info = race_data_elem.select_one('.smalltxt')
            if race_info:
                info_text = race_info.text.strip()
                # 例: "2024年11月15日 9回川崎5日目" を分解
                date_parts = info_text.split()
                if len(date_parts) >= 2:
                    race_data['date'] = date_parts[0]
                    race_data['venue_details'] = ' '.join(date_parts[1:])

        # レース詳細情報の取得を改善
        diary_snap = race_data_elem.select_one('diary_snap_cut span')
        if diary_snap:
            details_text = diary_snap.text.strip()
            # 例: "ダ左900m / 天候 : 曇 / ダート : 稍重 / 発走 : 15:00"
            details_parts = details_text.split('/')
            for part in details_parts:
                if '発走' in part:
                    race_data['start_time'] = part.split(':')[1].strip() + ':' + part.split(':')[2].strip()

        # レース詳細情報の取得
        race_details = soup.select_one('diary_snap_cut span')
        if race_details:
            race_data['race_details'] = race_details.text.strip()
        else:
            details = soup.select_one('div.data_intro p')
            race_data['race_details'] = details.text.strip() if details else ''

        # レース結果テーブルの取得
        result_table = soup.find('table', class_='race_table_01')
        if not result_table:
            print(f"結果テーブルが見つかりません: {url}")
            return None

        results = []
        headers = result_table.find_all('th')
        if not headers:
            print(f"テーブルヘッダーが見つかりません: {url}")
            return None

        for row in result_table.find_all('tr')[1:]:  # ヘッダーをスキップ
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
                
            result = {}
            for header, cell in zip(HEADERS, cols):
                result[header] = cell.text.strip()
            results.append(result)

        race_data['results'] = results
        
        return race_data

    except Exception as e:
        print(f"レース詳細の取得中にエラー発生: {url}")
        print(f"エラー内容: {str(e)}")
        return None

def save_checkpoint(data, filename, current_index):
    """チェックポイントを保存"""
    try:
        with open(filename, 'wb') as f:
            pickle.dump({'data': data, 'index': current_index}, f)
        print(f"チェックポイントを保存しました: {filename}")
    except Exception as e:
        print(f"チェックポイントの保存に失敗: {str(e)}")

def load_checkpoint(filename):
    """チェックポイントを読み込み"""
    try:
        with open(filename, 'rb') as f:
            checkpoint = pickle.load(f)
            return checkpoint['data'], checkpoint['index']
    except FileNotFoundError:
        print("チェックポイントファイルが見つかりません")
        return [], 0
    except Exception as e:
        print(f"チェックポイントの読み込みに失敗: {str(e)}")
        return [], 0

def scrape_all_pages(base_url, session, checkpoint_file='race_checkpoint_2023.pkl'):
    all_race_urls = []
    
    # チェックポイントの読み込み
    saved_urls, start_page = load_checkpoint(checkpoint_file)
    if saved_urls:
        all_race_urls = saved_urls
        page = start_page
        print(f"チェックポイントから再開: ページ {page}")
    else:
        page = 1
    
    consecutive_errors = 0
    
    while True:
        if consecutive_errors >= 3:
            print("連続エラーが発生したため、スクレイピングを一時停止します（10分待機）")
            time.sleep(600)
            consecutive_errors = 0
        
        current_url = f"{base_url}&page={page}"
        print(f"ページ {page} をスクレイピング中...")
        
        try:
            race_urls = scrape_race_list(current_url, session)
            
            if not race_urls:
                print(f"ページ {page} にレースデータがありません。スクレイピングを終了します。")
                break
            
            all_race_urls.extend(race_urls)
            consecutive_errors = 0
            
            # 10ページごとにチェックポイントを保存
            if page % 10 == 0:
                save_checkpoint(all_race_urls, checkpoint_file, page)
            
            print(f"現在の総URL数: {len(all_race_urls)}")
            page += 1
            
        except Exception as e:
            print(f"エラーが発生しました（ページ {page}）: {str(e)}")
            consecutive_errors += 1
            save_checkpoint(all_race_urls, checkpoint_file, page)
    
    return all_race_urls

def save_race_data_checkpoint(data, current_index, filename='race_data_checkpoint_2023.pkl'):
    """レース詳細データのチェックポイントを保存"""
    try:
        with open(filename, 'wb') as f:
            pickle.dump({'data': data, 'index': current_index}, f)
        print(f"レースデータのチェックポイントを保存しました: {filename}")
    except Exception as e:
        print(f"レースデータのチェックポイント保存に失敗: {str(e)}")

def load_race_data_checkpoint(filename='race_data_checkpoint_2023.pkl'):
    """レース詳細データのチェックポイントを読み込み"""
    try:
        with open(filename, 'rb') as f:
            checkpoint = pickle.load(f)
            return checkpoint['data'], checkpoint['index']
    except FileNotFoundError:
        print("レースデータのチェックポイントファイルが見つかりません")
        return [], 0
    except Exception as e:
        print(f"レースデータのチェックポイント読み込みに失敗: {str(e)}")
        return [], 0

def main():
    base_url = "https://db.netkeiba.com/?pid=race_list&word=&start_year=2023&start_mon=none&end_year=2023&end_mon=none&jyo%5B%5D=01&jyo%5B%5D=02&jyo%5B%5D=03&jyo%5B%5D=04&jyo%5B%5D=05&jyo%5B%5D=06&jyo%5B%5D=07&jyo%5B%5D=08&jyo%5B%5D=09&jyo%5B%5D=10&jyo%5B%5D=30&jyo%5B%5D=35&jyo%5B%5D=36&jyo%5B%5D=42&jyo%5B%5D=43&jyo%5B%5D=44&jyo%5B%5D=45&jyo%5B%5D=46&jyo%5B%5D=47&jyo%5B%5D=48&jyo%5B%5D=50&jyo%5B%5D=51&jyo%5B%5D=54&jyo%5B%5D=55&jyo%5B%5D=65&kyori_min=&kyori_max=&sort=date&list=100"
    
    session = requests_retry_session()
    
    try:
        print("中央競馬のスクレイピングを開始します...")
        race_urls = scrape_all_pages(base_url, session)
        
        if not race_urls:
            print("レースリンクが見つかりません。")
            return
            
        print(f"全URLを取得しました。総レース数: {len(race_urls)}")
        
        # レースデータのチェックポイントを読み込み
        all_race_data, start_index = load_race_data_checkpoint()
        
        if start_index > 0:
            print(f"レースデータのチェックポイントから再開: インデックス {start_index}")
        
        # start_indexから処理を再開
        for i, race_url in enumerate(race_urls[start_index:], start_index + 1):
            print(f"レース {i}/{len(race_urls)} をスクレイピング中...")
            race_data = scrape_race_details(race_url, session)
            
            if race_data is not None:
                all_race_data.append(race_data)
                
                # 50レースごとにチェックポイントを保存
                if i % 50 == 0:
                    save_race_data_checkpoint(all_race_data, i)
            else:
                print(f"レース {i} のデータ取得をスキップしました")
            
        
        # CSVファイル名を2023年用に変更
        current_date = datetime.now().strftime('%Y%m%d')
        filename = f'netkeiba_2023_race_details_{current_date}.csv'
        
        if all_race_data:
            df = pd.DataFrame(all_race_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"データを {filename} に保存しました")
            print(f"取得したレース数: {len(all_race_data)}")
        else:
            print("レースデータを取得できませんでした")
            
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        # エラー時にも現在までのデータを保存
        if 'i' in locals() and all_race_data:
            save_race_data_checkpoint(all_race_data, i)
    finally:
        session.close()

if __name__ == '__main__':
    main()
