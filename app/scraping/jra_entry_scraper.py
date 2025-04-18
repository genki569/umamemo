#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
中央競馬（JRA）の出馬表をスクレイピングするスクリプト
netkeiba.comから中央競馬の出馬表データを取得し、CSVファイルに保存します。

主な機能:
- 指定された日付の全レースURLを取得
- 各レースの出走表情報（馬名、騎手名、斤量など）を抽出
- 抽出したデータをCSV形式で保存
- データベースへの保存機能

制限事項:
- netkeiba.comの仕様変更によりスクレイピングが失敗する可能性があります
- 大量のリクエストを短時間に送ると制限される可能性があります
"""

from playwright.sync_api import sync_playwright, TimeoutError
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import os
import csv
import re
import json
from app import app, db
from app.models import Race, Horse, Jockey, ShutubaEntry
import traceback
import sys
import argparse

def generate_race_id(race_url: str) -> str:
    """
    レースURLからレースIDを生成する関数
    
    @param race_url: レースのURL（文字列）
    @return: 抽出されたレースID（文字列）、エラー時はNone
    
    レースIDはネット競馬のURLから「race_id=」の後ろの部分を抽出します。
    例: https://race.netkeiba.com/race/shutuba.html?race_id=202306050611 → 202306050611
    """
    try:
        # URLからrace_idパラメータを抽出
        race_id = race_url.split('race_id=')[1].split('&')[0]
        return race_id
    except Exception as e:
        print(f"レースID生成エラー: {str(e)}")
        return None

def generate_venue_code(venue_name: str) -> str:
    """
    開催場所から3桁のコードを生成する関数
    
    @param venue_name: 開催場所の名前（文字列）
    @return: 対応する3桁のコード（文字列）、不明な場合は'999'
    
    場所名と対応するコードのマッピングを定義し、指定された場所のコードを返します。
    中央競馬場は101-110、地方競馬場は201-215のコード範囲を使用。
    """
    venue_codes = {
        '札幌': '101',
        '函館': '102',
        '福島': '103',
        '新潟': '104',
        '東京': '105',
        '中山': '106',
        '中京': '107',
        '京都': '108',
        '阪神': '109',
        '小倉': '110',
        '門別': '201',
        '帯広': '202',
        '盛岡': '203',
        '水沢': '204',
        '浦和': '205',
        '船橋': '206',
        '大井': '207',
        '川崎': '208',
        '金沢': '209',
        '笠松': '210',
        '名古屋': '211',
        '園田': '212',
        '姫路': '213',
        '高知': '214',
        '佐賀': '215'
    }
    return venue_codes.get(venue_name, '999')  # 不明な場合は999を返す

def generate_entry_id(race_id, horse_number):
    """
    エントリーIDを生成する関数
    
    @param race_id: レースID（15桁の文字列）
    @param horse_number: 馬番（数値または文字列）
    @return: 17桁のエントリーID（整数）、エラー時はNone
    
    レースID(15桁) + 馬番(2桁)の形式で17桁のIDを生成します。
    例: レースID=202306050611、馬番=7 の場合 → 20230605061107
    """
    try:
        # 馬番を2桁の文字列に変換してレースIDと結合
        return int(f"{race_id}{str(int(horse_number)).zfill(2)}")
    except:
        return None

def generate_horse_id(horse_name: str) -> int:
    """
    馬名から一意なIDを生成する関数
    
    @param horse_name: 馬の名前（文字列）
    @return: 10桁の馬ID（整数）
    
    馬名から一貫性のあるハッシュを生成し、それを10桁のIDに変換します。
    同じ馬名には常に同じIDを返すように設計されています。
    IDの先頭は1で始まり、名前の各文字に位置の重みをつけてハッシュ化しています。
    """
    if not hasattr(generate_horse_id, 'used_ids'):
        generate_horse_id.used_ids = set()
        generate_horse_id.name_to_id = {}

    # 既に生成済みのIDがあればそれを返す
    if horse_name in generate_horse_id.name_to_id:
        return generate_horse_id.name_to_id[horse_name]

    # 馬名からハッシュ値を生成（位置ごとに重み付け）
    name_hash = 0
    for i, char in enumerate(horse_name):
        position_weight = (i + 1) * 100
        char_value = ord(char) * position_weight
        name_hash = (name_hash * 31 + char_value) & 0xFFFFFFFF

    # ハッシュ値を10桁のIDに変換（先頭は1）
    base_id = int(f"1{abs(name_hash) % 999999999:09d}")

    # 衝突回避（既に使用されているIDの場合はインクリメント）
    while base_id in generate_horse_id.used_ids:
        base_id += 1
        if base_id % 1000000000 == 0:
            base_id = 1000000000

    # 生成したIDを記録
    generate_horse_id.used_ids.add(base_id)
    generate_horse_id.name_to_id[horse_name] = base_id

    return base_id

def generate_jockey_id(jockey_name: str) -> int:
    """
    騎手名から一意なIDを生成する関数
    
    @param jockey_name: 騎手の名前（文字列）
    @return: 10桁の騎手ID（整数）
    
    騎手名から一貫性のあるハッシュを生成し、それを10桁のIDに変換します。
    同じ騎手名には常に同じIDを返すように設計されています。
    IDの先頭は2で始まり、名前の文字コードの合計をハッシュ化しています。
    """
    if not hasattr(generate_jockey_id, 'used_ids'):
        generate_jockey_id.used_ids = set()
        generate_jockey_id.name_to_id = {}

    # 既に生成済みのIDがあればそれを返す
    if jockey_name in generate_jockey_id.name_to_id:
        return generate_jockey_id.name_to_id[jockey_name]

    # 騎手名からハッシュ値を生成（単純な文字コードの合計）
    name_hash = sum(ord(c) for c in jockey_name)
    
    # ハッシュ値を10桁のIDに変換（先頭は2）
    base_id = int(f"2{abs(name_hash) % 999999999:09d}")

    # 衝突回避（既に使用されているIDの場合はインクリメント）
    while base_id in generate_jockey_id.used_ids:
        base_id += 1
        if base_id % 1000000000 == 0:
            base_id = 2000000000

    # 生成したIDを記録
    generate_jockey_id.used_ids.add(base_id)
    generate_jockey_id.name_to_id[jockey_name] = base_id

    return base_id

def scrape_race_entry(page, race_url: str) -> Dict[str, any]:
    """
    レースの出走表ページから情報を取得する関数
    
    @param page: Playwrightのページオブジェクト
    @param race_url: スクレイピング対象のレースURL（文字列）
    @return: レース情報と出走馬情報を含む辞書、エラー時はNone
    
    レースの基本情報（レース名、番号、開催場所など）と
    出走馬の詳細情報（馬名、騎手名、斤量など）を抽出します。
    BeautifulSoupを使用してHTML要素を解析し、正規表現でテキストから必要な情報を抽出します。
    エラー発生時はスクリーンショットを保存し、デバッグに役立てます。
    """
    try:
        # レースページにアクセス
        page.goto(race_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)  # ページの読み込み完了を待機
        
        # ページのHTMLを取得してBeautifulSoupで解析
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # レース情報の取得
        race_id = generate_race_id(race_url)
        if not race_id:
            print(f"レースIDの生成に失敗しました: {race_url}")
            return None
        
        # レース名と番号を取得
        race_num_text = soup.select_one('.RaceNum').text.strip() if soup.select_one('.RaceNum') else ""
        race_name = soup.select_one('.RaceName').text.strip() if soup.select_one('.RaceName') else ""
        race_number = int(race_num_text.replace('R', '')) if race_num_text else 0
        
        # 開催場所と日付を取得
        race_data = soup.select_one('.RaceData').text.strip() if soup.select_one('.RaceData') else ""
        race_datetime_text = soup.select_one('.RaceData01').text.strip() if soup.select_one('.RaceData01') else ""
        
        # 開催場所の抽出（例: "東京"）
        venue_pattern = r'(\d+回)([^\d]+)(\d+日)'
        venue_match = re.search(venue_pattern, race_data)
        venue = venue_match.group(2) if venue_match else ""
        venue_code = generate_venue_code(venue)
        
        # 日付の抽出（例: "2023年6月3日"）
        date_pattern = r'(\d+年\d+月\d+日)'
        date_match = re.search(date_pattern, race_datetime_text)
        race_date_text = date_match.group(1) if date_match else ""
        
        # 日付をYYYY-MM-DD形式に変換
        race_date = None
        if race_date_text:
            race_date_text = race_date_text.replace('年', '-').replace('月', '-').replace('日', '')
            race_date = race_date_text
        
        # 出馬表テーブルから馬情報を抽出
        horse_entries = []
        horse_rows = soup.select('table.Shutuba_Table tr.HorseList')
        
        for row in horse_rows:
            # 馬番
            horse_number_elem = row.select_one('.Waku span')
            horse_number = int(horse_number_elem.text) if horse_number_elem else 0
            
            # 枠番
            waku_element = row.select_one('.Waku')
            waku_class = waku_element.get('class', []) if waku_element else []
            waku_num = 0
            
            # 枠番のクラス名から番号を抽出（例: "Waku1" → 1）
            for class_name in waku_class:
                if class_name.startswith('Waku') and len(class_name) > 4:
                    try:
                        waku_num = int(class_name[4:])
                    except ValueError:
                        pass
            
            # 馬名
            horse_name_elem = row.select_one('.HorseName a')
            horse_name = horse_name_elem.text.strip() if horse_name_elem else ""
            horse_id = generate_horse_id(horse_name) if horse_name else 0
            
            # 馬齢と性別
            horse_info_elem = row.select_one('.Barei')
            horse_info = horse_info_elem.text.strip() if horse_info_elem else ""
            
            # 性別と年齢を抽出（例: "牡3" → 性別="牡", 年齢=3）
            gender = ""
            age = 0
            if horse_info:
                gender = horse_info[0]  # 最初の文字（牡/牝/セ）
                try:
                    age = int(horse_info[1:])
                except ValueError:
                    pass
            
            # 斤量
            weight_elem = row.select_one('.Jockey .JockeyWeight')
            weight = weight_elem.text.strip() if weight_elem else ""
            
            # 騎手
            jockey_elem = row.select_one('.Jockey a')
            jockey_name = jockey_elem.text.strip() if jockey_elem else ""
            jockey_id = generate_jockey_id(jockey_name) if jockey_name else 0
            
            # 馬体重
            horse_weight_elem = row.select_one('.Weight')
            horse_weight_text = horse_weight_elem.text.strip() if horse_weight_elem else ""
            
            # 馬体重と増減を抽出（例: "466(+4)" → 体重=466, 増減=+4）
            horse_weight = 0
            weight_diff = 0
            
            if horse_weight_text:
                weight_match = re.search(r'(\d+)\(([+-]?\d+)\)', horse_weight_text)
                if weight_match:
                    horse_weight = int(weight_match.group(1))
                    weight_diff = int(weight_match.group(2))
                else:
                    try:
                        horse_weight = int(horse_weight_text)
                    except ValueError:
                        pass
            
            # エントリーID生成
            entry_id = generate_entry_id(race_id, horse_number)
            
            # 馬の詳細情報を辞書に格納
            entry = {
                'entry_id': entry_id,
                'race_id': race_id,
                'race_date': race_date,
                'venue': venue,
                'venue_code': venue_code,
                'race_number': race_number,
                'race_name': race_name,
                'horse_number': horse_number,
                'frame_number': waku_num,
                'horse_id': horse_id,
                'horse_name': horse_name,
                'gender': gender,
                'age': age,
                'weight': weight,
                'jockey_id': jockey_id,
                'jockey_name': jockey_name,
                'horse_weight': horse_weight,
                'weight_diff': weight_diff,
                'odds': 0.0,  # オッズ情報がある場合は抽出
                'popularity': 0,  # 人気順があれば抽出
                'race_url': race_url
            }
            
            horse_entries.append(entry)
        
        # 全体のレース情報と馬リストをまとめる
        race_entry = {
            'race_id': race_id,
            'race_date': race_date,
            'venue': venue,
            'venue_code': venue_code,
            'race_number': race_number,
            'race_name': race_name,
            'race_url': race_url,
            'entries': horse_entries
        }
        
        return race_entry
    
    except Exception as e:
        # エラー発生時の処理
        print(f"レース情報スクレイピングエラー: {str(e)}")
        traceback.print_exc()
        try:
            # デバッグ用にスクリーンショットを保存
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            screenshot_path = f"error_screenshots/race_error_{timestamp}.png"
            os.makedirs("error_screenshots", exist_ok=True)
            page.screenshot(path=screenshot_path)
            print(f"エラー時のスクリーンショットを保存しました: {screenshot_path}")
        except Exception as screenshot_error:
            print(f"スクリーンショット保存エラー: {str(screenshot_error)}")
        
        return None

def save_to_csv(data: List[Dict], csv_path: str, mode: str = 'w') -> bool:
    """
    スクレイピングしたデータをCSVファイルに保存する関数
    
    @param data: 保存するデータのリスト
    @param csv_path: 保存先のCSVファイルパス
    @param mode: ファイルオープンモード（'w':上書き, 'a':追記）
    @return: 保存が成功したかどうかのブール値
    
    エントリー情報を指定されたCSVファイルに保存します。
    モードは'w'（新規作成/上書き）または'a'（追記）で指定可能です。
    ファイルが存在しない場合はヘッダー行を含めて新規作成します。
    """
    if not data or len(data) == 0:
        print("保存するデータがありません")
        return False
    
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # ファイルが存在しない、またはモードが'w'の場合はヘッダーを書き込む
        file_exists = os.path.isfile(csv_path) and mode == 'a'
        
        with open(csv_path, mode, newline='', encoding='utf-8') as f:
            # CSV列のフィールド名を定義
            fieldnames = [
                'entry_id', 'race_id', 'horse_number', 'waku_number',
                'horse_id', 'horse_name', 'gender', 'age',
                'jockey_id', 'jockey_name', 'weight', 'horse_weight',
                'weight_diff', 'trainer_name', 'odds', 'popularity'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # ファイルが新規の場合はヘッダーを書き込む
            if not file_exists:
                writer.writeheader()
            
            # データを書き込む
            for row in data:
                writer.writerow(row)
        
        print(f"{len(data)}件のデータをCSVに保存しました: {csv_path}")
        return True
    
    except Exception as e:
        # エラー発生時の処理
        error_trace = traceback.format_exc()
        print(f"CSVファイル保存エラー: {str(e)}")
        print(error_trace)
        return False

def get_race_urls_for_date(page, date_str: str) -> List[str]:
    """
    指定された日付のレースURLリストを取得する関数
    
    @param page: Playwrightのページオブジェクト
    @param date_str: 日付文字列 (YYYY-MM-DD形式)
    @return: レースURLのリスト、エラー時は空リスト
    
    指定された日付のnetkeibaのカレンダーページにアクセスし、
    その日に開催される全レースのURLを抽出します。
    """
    try:
        # 日付をYYYYMMDD形式に変換
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_param = date_obj.strftime('%Y%m%d')
        
        # カレンダーページにアクセス
        calendar_url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_param}"
        page.goto(calendar_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(3000)
        
        # ページのHTMLを取得してBeautifulSoupで解析
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # レースリンクを取得（すべてのレース）
        race_links = []
        race_card_elements = soup.select('div.RaceList_DataItem')
        
        for element in race_card_elements:
            # すべてのレースのURLを抽出（中央競馬フィルタリングを削除）
            race_elems = element.select('li.RaceList_DataItem')
            for race in race_elems:
                link_elem = race.select_one('a')
                if link_elem and 'href' in link_elem.attrs:
                    relative_link = link_elem['href']
                    if 'shutuba.html' in relative_link:
                        absolute_link = f"https://race.netkeiba.com{relative_link}"
                        race_links.append(absolute_link)
        
        # デバッグ出力
        print(f"{date_str}のレースURL取得: {len(race_links)}件")
        return race_links
    
    except Exception as e:
        # エラー発生時の処理
        error_trace = traceback.format_exc()
        print(f"レースURL取得エラー: {str(e)}")
        print(error_trace)
        return []

def get_race_info_for_next_three_days():
    """
    今日から3日間のレース情報を取得する関数
    
    @return: なし（処理結果はファイルに保存されます）
    
    この関数は、現在日から3日間分のJRAレース出走表情報を取得し、
    CSVファイルに保存します。Playwrightを使用してブラウザを操作し、
    各日のレースページにアクセスしてデータをスクレイピングします。
    """
    try:
        # 今日から3日間の日付を取得
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
        
        # 出力ファイル名の設定
        current_date = today.strftime('%Y%m%d')
        filename = f'jra_race_entries_{current_date}.csv'
        
        # データディレクトリの作成
        os.makedirs('data/race_entries', exist_ok=True)
        output_path = os.path.join('data/race_entries', filename)
        
        # Playwrightの設定
        with sync_playwright() as playwright:
            # ブラウザの起動（ヘッドレスモード）
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
            )
            page = context.new_page()
            
            # 各日付のレース情報を取得
            all_entries = []
            for date_str in dates:
                try:
                    # URLを取得
                    race_urls = get_race_urls_for_date(page, date_str)
                    print(f"{date_str}のレースURL数: {len(race_urls)}")
                    
                    if race_urls:
                        success_count = 0
                        # 各レースの出馬表を取得
                        for idx, race_url in enumerate(race_urls, 1):
                            try:
                                print(f"[{idx}/{len(race_urls)}] スクレイピング中: {race_url}")
                                race_entry = scrape_race_entry(page, race_url)
                                if race_entry and race_entry.get('entries') and len(race_entry['entries']) > 0:
                                    save_to_csv(race_entry['entries'], filename)
                                    success_count += 1
                                    print(f"保存完了: {race_entry.get('venue', '不明')} {race_entry.get('race_number', '?')}R（成功: {success_count}/{idx}）")
                                    # アクセス間隔を空ける（サーバー負荷軽減のため）
                                    time.sleep(2)
                                else:
                                    print(f"スキップ: 有効なエントリーがありません - {race_url}")
                            except Exception as e:
                                print(f"レース処理中にエラー: {str(e)}")
                                traceback.print_exc()
                                continue
                        
                        print(f"{date_str}の処理完了: {success_count}/{len(race_urls)}件のレースを取得")
                    else:
                        print(f"{date_str}のレースが見つかりませんでした")
                
                except Exception as e:
                    print(f"{date_str}の処理中にエラー: {str(e)}")
                    traceback.print_exc()
                    continue
            
            # ブラウザの終了
            browser.close()
            
    except Exception as e:
        print(f"全体の処理中にエラー発生: {str(e)}")
        traceback.print_exc()

def scrape_jra_entries_for_date(date_str: str):
    """
    指定された日付のJRAレースエントリー情報をスクレイピングする関数
    
    @param date_str: 日付文字列（YYYY-MM-DD形式）
    @return: なし（処理結果はファイルに保存されます）
    
    指定された日付のJRAレースの出走表情報を取得し、
    CSVファイルに保存します。単一日付のスクレイピングに特化しています。
    """
    try:
        # 出力ファイル名の設定
        filename = f'jra_race_entries_{date_str.replace("-", "")}.csv'
        output_path = os.path.join('data/race_entries', filename)
        
        # データディレクトリの作成
        os.makedirs('data/race_entries', exist_ok=True)
        
        # Playwrightの設定と実行
        with sync_playwright() as playwright:
            # ブラウザの起動
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
            )
            page = context.new_page()
            
            race_urls = get_race_urls_for_date(page, date_str)
            print(f"{len(race_urls)}件のレースURLを取得しました")
            
            # 各レースの出馬表を取得
            all_entries = []
            success_count = 0
            
            for idx, race_url in enumerate(race_urls, 1):
                try:
                    print(f"[{idx}/{len(race_urls)}] スクレイピング中: {race_url}")
                    race_entry = scrape_race_entry(page, race_url)
                    
                    if race_entry and race_entry.get('entries') and len(race_entry['entries']) > 0:
                        for entry in race_entry['entries']:
                            all_entries.append(entry)
                        
                        success_count += 1
                        print(f"取得成功: {race_entry.get('venue', '不明')} {race_entry.get('race_number', '?')}R")
                    else:
                        print(f"スキップ: 有効なエントリーがありません - {race_url}")
                    
                    # アクセス間隔を空ける（サーバー負荷軽減のため）
                    time.sleep(3)
                    
                except Exception as e:
                    print(f"レース処理中にエラー: {str(e)}")
                    traceback.print_exc()
                    continue
            
            # 取得したデータをCSVに保存
            if all_entries:
                save_to_csv(all_entries, output_path)
                print(f"合計{len(all_entries)}件のエントリーを保存しました: {output_path}")
            else:
                print("保存するデータがありません")
            
            # ブラウザの終了
            browser.close()
        
    except Exception as e:
        print(f"スクレイピング処理中にエラー発生: {str(e)}")
        traceback.print_exc()

if __name__ == '__main__':
    """
    スクリプト実行時のメイン処理
    
    コマンドライン引数に基づいて、以下のいずれかの処理を実行します:
    1. 引数なし: 今日から3日間の出走表情報を取得します
    2. 日付指定: 指定された日付の出走表情報を取得します
    
    取得したデータはCSVファイルに保存され、処理の進捗状況はコンソールに表示されます。
    """
    parser = argparse.ArgumentParser(description='JRAの出走表情報をスクレイピングするツール')
    parser.add_argument('--date', type=str, help='スクレイピングする日付（YYYY-MM-DD形式）')
    args = parser.parse_args()
    
    # 引数で日付が指定されている場合はその日付のデータを取得
    if args.date:
        try:
            # 日付形式の検証
            target_date = datetime.strptime(args.date, '%Y-%m-%d').strftime('%Y-%m-%d')
            print(f"指定された日付 {target_date} の出走表情報を取得します...")
            
            # 指定された日付のレース情報を取得
            race_entries = scrape_jra_entries_for_date(target_date)
            
            if race_entries:
                # CSV保存処理
                save_status = save_to_csv(race_entries, target_date)
                if save_status:
                    print(f"{target_date}の出走表情報を正常に保存しました")
                else:
                    print(f"{target_date}の出走表情報の保存中にエラーが発生しました")
            else:
                print(f"{target_date}にレースデータが見つかりませんでした")
        except ValueError:
            # 日付形式が不正な場合のエラー処理
            print("日付の形式が不正です。YYYY-MM-DD形式で指定してください")
            sys.exit(1)
    else:
        # 引数がない場合は今日から3日間のデータを取得
        print("今日から3日間の出走表情報を取得します...")
        
        # 次の3日間のレース情報を取得
        race_info = get_race_info_for_next_three_days()
        
        if race_info and len(race_info) > 0:
            # 取得したレース情報を日付ごとに処理
            for date, races in race_info.items():
                if races and len(races) > 0:
                    print(f"{date}のレース情報: {len(races)}レース")
                    
                    # 指定日のレース情報をスクレイピング
                    race_entries = scrape_jra_entries_for_date(date)
                    
                    if race_entries:
                        # CSV保存処理
                        save_status = save_to_csv(race_entries, date)
                        if save_status:
                            print(f"{date}の出走表情報を正常に保存しました")
                        else:
                            print(f"{date}の出走表情報の保存中にエラーが発生しました")
                    else:
                        print(f"{date}の出走表情報の取得に失敗しました")
                else:
                    print(f"{date}には開催レースがありません")
        else:
            print("今後3日間の開催レース情報が見つかりませんでした") 