##地方競馬スクレイピング
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime

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

def scrape_race_details(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = session.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    race_data = {}
    
    race_data['race_name'] = soup.select_one('div.data_intro h1').text.strip() if soup.select_one('div.data_intro h1') else ''
    
    race_details = soup.select_one('div.data_intro p').text.strip() if soup.select_one('div.data_intro p') else ''
    race_data['race_details'] = race_details
    
    date_info = soup.select_one('div.data_intro p.smalltxt')
    if date_info:
        date_text = date_info.text.strip()
        parts = date_text.split()
        if len(parts) >= 2:
            race_data['date'] = parts[0]  # 日付
            venue_info = parts[1]
            if '回' in venue_info and '日目' in venue_info:
                venue = venue_info.split('回')[1].split('日目')[0]
                race_data['venue'] = venue
            else:
                race_data['venue'] = ''
        else:
            race_data['date'] = ''
            race_data['venue'] = ''
    else:
        race_data['date'] = ''
        race_data['venue'] = ''
    
    start_time_info = soup.select_one('div.data_intro span')
    if start_time_info:
        start_time_text = start_time_info.text.strip()
        start_time_parts = start_time_text.split('発走 : ')
        if len(start_time_parts) > 1:
            race_data['start_time'] = start_time_parts[1]
        else:
            race_data['start_time'] = ''
    else:
        race_data['start_time'] = ''
    
    result_table = soup.find('table', class_='race_table_01 nk_tb_common')
    if result_table:
        headers = [th.text.strip() for th in result_table.find_all('th')]
        rows = []
        for row in result_table.find_all('tr')[1:]:
            rows.append([td.text.strip() for td in row.find_all('td')])
        race_data['results'] = pd.DataFrame(rows, columns=headers).to_dict('records')
    else:
        race_data['results'] = []
    
    return race_data

def save_checkpoint(data, filename, current_page):
    df = pd.DataFrame(data)
    checkpoint = {
        'data': df.to_dict('records'),
        'page': current_page
    }
    pd.to_pickle(checkpoint, filename)
    print(f"チェックポイントを保存しました: {filename}")

def load_checkpoint(filename):
    if os.path.exists(filename):
        checkpoint = pd.read_pickle(filename)
        return checkpoint['data'], checkpoint['page']
    return [], 0

def main():
    base_url = "https://db.netkeiba.com/?pid=race_list&word=&start_year=none&start_mon=none&end_year=none&end_mon=none&jyo%5B0%5D=01&jyo%5B1%5D=02&jyo%5B2%5D=03&jyo%5B3%5D=04&jyo%5B4%5D=05&jyo%5B5%5D=06&jyo%5B6%5D=07&jyo%5B7%5D=08&jyo%5B8%5D=09&jyo%5B9%5D=10&jyo%5B10%5D=30&jyo%5B11%5D=35&jyo%5B12%5D=36&jyo%5B13%5D=42&jyo%5B14%5D=43&jyo%5B15%5D=44&jyo%5B16%5D=45&jyo%5B17%5D=46&jyo%5B18%5D=47&jyo%5B19%5D=48&jyo%5B20%5D=50&jyo%5B21%5D=51&jyo%5B22%5D=54&jyo%5B23%5D=55&jyo%5B24%5D=65&kyori_min=&kyori_max=&sort=date&list=100"
    
    session = requests_retry_session()
    
    try:
        print("地方競馬のスクレイピングを開始します...")
        race_urls = scrape_all_pages(base_url, session, checkpoint_file='local_race_checkpoint.pkl')
        
        if not race_urls:
            print("レースリンクが見つかりません。")
            return
            
        print(f"全URLを取得しました。総レース数: {len(race_urls)}")
        
        # レースデータのチェックポイントを読み込み
        all_race_data, start_index = load_race_data_checkpoint('local_race_data_checkpoint.pkl')
        
        if start_index > 0:
            print(f"レースデータのチェックポイントから再開: インデックス {start_index}")
        
        for i, race_url in enumerate(race_urls[start_index:], start_index + 1):
            print(f"レース {i}/{len(race_urls)} をスクレイピング中...")
            race_data = scrape_race_details(race_url, session)
            
            if race_data is not None:
                all_race_data.append(race_data)
                
                if i % 50 == 0:
                    save_race_data_checkpoint(all_race_data, i, 'local_race_data_checkpoint.pkl')
            else:
                print(f"レース {i} のデータ取得をスキップしました")
        
        current_date = datetime.now().strftime('%Y%m%d')
        filename = f'netkeiba_local_race_details_{current_date}.csv'
        
        if all_race_data:
            df = pd.DataFrame(all_race_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"データを {filename} に保存しました")
            print(f"取得したレース数: {len(all_race_data)}")
        else:
            print("レースデータを取得できませんでした")
            
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        if 'i' in locals() and all_race_data:
            save_race_data_checkpoint(all_race_data, i, 'local_race_data_checkpoint.pkl')
    finally:
        session.close()

if __name__ == '__main__':
    main()
