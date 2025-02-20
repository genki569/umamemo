from playwright.sync_api import sync_playwright, TimeoutError
import time
from bs4 import BeautifulSoup

def get_race_info(date_str: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-web-security'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        try:
            # タイムアウトを設定
            page.set_default_timeout(60000)  # 60秒
            
            # まずトップページにアクセス
            print("トップページにアクセスしています...")
            page.goto("https://nar.netkeiba.com/", wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # 次に目的のページに遷移
            url = f"https://nar.netkeiba.com/top/race_list.html?kaisai_date={date_str}"
            print(f"レース一覧ページにアクセスしています: {url}")
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
            except TimeoutError:
                print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
            
            # 明示的に待機
            page.wait_for_timeout(5000)
            
            print("ページの読み込みが完了しました")
            
            # JavaScriptを実行してページの準備ができているか確認
            is_ready = page.evaluate('''() => {
                return document.querySelector('.RaceList_ProvinceSelect') !== null;
            }''')
            
            if not is_ready:
                print("ページの準備ができていません。さらに待機します...")
                page.wait_for_timeout(5000)
            
            # 開催場所タブを取得
            venues = page.query_selector_all('.RaceList_ProvinceSelect li')
            print(f"開催場所数: {len(venues)}")
            
            for venue in venues:
                # 開催場所名を取得
                venue_name = venue.inner_text().strip()
                print(f"\n開催場所: {venue_name}")
                
                # 開催場所のリンクを取得してクリック
                venue_link = venue.query_selector('a')
                if venue_link:
                    href = venue_link.get_attribute('href')
                    full_url = f"https://nar.netkeiba.com/top/race_list.html{href}"
                    print(f"開催場所URL: {full_url}")
                    
                    # 新しいページで開く
                    new_page = context.new_page()
                    try:
                        new_page.goto(full_url, wait_until='domcontentloaded', timeout=30000)
                        new_page.wait_for_timeout(3000)
                        
                        # レース情報を取得
                        races = new_page.query_selector_all('dl.RaceList_DataList')
                        for race in races:
                            race_links = race.query_selector_all('a[href*="/race/shutuba.html"]')
                            for link in race_links:
                                href = link.get_attribute('href')
                                
                                race_time_elem = link.query_selector('.Race_Time')
                                race_time = race_time_elem.inner_text().strip() if race_time_elem else ''
                                
                                race_num_elem = link.query_selector('.Race_Num')
                                race_number = race_num_elem.inner_text().strip() if race_num_elem else ''
                                
                                race_name_elem = link.query_selector('.Race_Name')
                                race_name = race_name_elem.inner_text().strip() if race_name_elem else ''
                                
                                race_url = f"https://nar.netkeiba.com{href}"
                                print(f"レース番号: {race_number}")
                                print(f"レース名: {race_name}")
                                print(f"発走時刻: {race_time}")
                                print(f"URL: {race_url}")
                                print("---")
                    finally:
                        new_page.close()
            
            # デバッグ用の保存
            page.screenshot(path="debug_screenshot.png")
            print("スクリーンショットを保存しました: debug_screenshot.png")
            
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            try:
                page.screenshot(path="error_screenshot.png")
                print("エラー時のスクリーンショットを保存しました: error_screenshot.png")
            except:
                pass
                
        finally:
            context.close()
            browser.close()

if __name__ == '__main__':
    print("地方競馬レース情報の取得を開始します...")
    date_str = "20241120"
    get_race_info(date_str)