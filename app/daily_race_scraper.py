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

def scrape_all_pages(base_url, session):
    all_race_urls = []
    page = 1
    consecutive_errors = 0
    
    while page <= 100:  # 100ページまでに制限
        if consecutive_errors >= 3:
            print("連続エラーが発生したため、スクレイピングを一時停止します（10分待機）")
            time.sleep(600)
            consecutive_errors = 0
        
        current_url = f"{base_url}&page={page}"
        print(f"ページ {page}/100 をスクレイピング中...")  # 表示も修正
        
        try:
            race_urls = scrape_race_list(current_url, session)
            
            if not race_urls:
                print(f"ページ {page} にレースデータがありません。スクレイピングを終了します。")
                break
            
            all_race_urls.extend(race_urls)
            consecutive_errors = 0
            
            print(f"現在の総URL数: {len(all_race_urls)}")
            page += 1
            
        except Exception as e:
            print(f"エラーが発生しました（ページ {page}）: {str(e)}")
            consecutive_errors += 1
    
    return all_race_urls

def main():
    # Pythonパスにscriptsディレクトリを追加
    import sys
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    sys.path.append(project_root)
    
    base_url = "https://db.netkeiba.com/?pid=race_list&word=&start_year=none&start_mon=none&end_year=none&end_mon=none&jyo%5B0%5D=01&jyo%5B1%5D=02&jyo%5B2%5D=03&jyo%5B3%5D=04&jyo%5B4%5D=05&jyo%5B5%5D=06&jyo%5B6%5D=07&jyo%5B7%5D=08&jyo%5B8%5D=09&jyo%5B9%5D=10&jyo%5B10%5D=30&jyo%5B11%5D=35&jyo%5B12%5D=36&jyo%5B13%5D=42&jyo%5B14%5D=43&jyo%5B15%5D=44&jyo%5B16%5D=45&jyo%5B17%5D=46&jyo%5B18%5D=47&jyo%5B19%5D=48&jyo%5B20%5D=50&jyo%5B21%5D=51&jyo%5B22%5D=54&jyo%5B23%5D=55&jyo%5B24%5D=65&kyori_min=&kyori_max=&sort=date&list=100"
    
    session = requests_retry_session()
    
    try:
        print("中央競馬のスクレイピングを開始します...")
        race_urls = scrape_all_pages(base_url, session)
        
        if not race_urls:
            print("レースリンクが見つかりません。")
            return
            
        print(f"全URLを取得しました。総レース数: {len(race_urls)}")
        
        all_race_data = []
        
        # URLごとの処理
        for i, race_url in enumerate(race_urls, 1):
            print(f"レース {i}/{len(race_urls)} をスクレイピング中...")
            race_data = scrape_race_details(race_url, session)
            
            if race_data is not None:
                all_race_data.append(race_data)
            else:
                print(f"レース {i} のデータ取得をスキップしました")
        
        current_date = datetime.now().strftime('%Y%m%d')
        temp_csv_path = f'netkeiba_daily_races_{current_date}.csv'
        
        if all_race_data:
            df = pd.DataFrame(all_race_data)
            df.to_csv(temp_csv_path, index=False, encoding='utf-8-sig')
            print(f"データを {temp_csv_path} に保存しました")
            print(f"取得したレース数: {len(all_race_data)}")
            
            print("CSVの分割処理を開始します...")
            from scripts.csv_splitter import split_race_csv
            split_race_csv(temp_csv_path)
            
            os.remove(temp_csv_path)
            print("全ての処理が完了しました")
        else:
            print("レースデータを取得できませんでした")
            
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
    finally:
        session.close()

if __name__ == '__main__':
    main()
