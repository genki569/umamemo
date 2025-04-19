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
import traceback
import sys
import argparse

# FLASKのインポートエラーを回避するために条件分岐を追加
try:
    from app import app, db
    from app.models import Race, Horse, Jockey, ShutubaEntry
except ImportError:
    print("警告: Flaskアプリケーションモジュールがインポートできません。スタンドアロンモードで実行します。")
    app = None
    db = None

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
    """
    try:
        # レースページにアクセス
        print(f"レースページアクセス中: {race_url}")
        try:
            page.goto(race_url, wait_until='domcontentloaded', timeout=60000)
        except TimeoutError:
            print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
            
        page.wait_for_timeout(5000)  # ページの読み込み完了を待機
        
        # HTMLが存在するか簡単に確認
        page_title = page.title()
        if "404" in page_title or "エラー" in page_title or "見つかりません" in page_title:
            print(f"ページが存在しません: {race_url}")
            return None
        
        # ページのHTMLを取得してBeautifulSoupで解析
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # レース情報の取得
        race_id = generate_race_id(race_url)
        if not race_id:
            print(f"レースIDの生成に失敗しました: {race_url}")
            return None
        
        # レース名と番号を取得（複数の可能性のあるセレクタを試す）
        race_num_text = ""
        for selector in ['.RaceNum', '.RaceMainMenu .RaceNum', '.RaceData .RaceNum']:
            elem = soup.select_one(selector)
            if elem:
                race_num_text = elem.text.strip()
                break
                
        if not race_num_text:
            print("レース番号が見つかりません。クラス名が変更された可能性があります。")
            race_num_text = ""
            
        race_name = ""
        for selector in ['.RaceName', '.RaceMainMenu .RaceName', '.RaceData .RaceName']:
            elem = soup.select_one(selector)
            if elem:
                race_name = elem.text.strip()
                break
                
        if not race_name:
            print("レース名が見つかりません。クラス名が変更された可能性があります。")
            race_name = ""
            
        race_number = int(race_num_text.replace('R', '')) if race_num_text else 0
        
        # 開催場所と日付を取得（複数の可能性のあるセレクタを試す）
        race_data = ""
        for selector in ['.RaceData', '.RaceMainMenu .RaceData', '.RaceSubData']:
            elem = soup.select_one(selector)
            if elem:
                race_data = elem.text.strip()
                break
                
        if not race_data:
            print("レースデータが見つかりません。クラス名が変更された可能性があります。")
            race_data = ""
            
        race_datetime_text = ""
        for selector in ['.RaceData01', '.RaceMainMenu .RaceData01', '.RaceSubData']:
            elem = soup.select_one(selector)
            if elem:
                race_datetime_text = elem.text.strip()
                break
                
        if not race_datetime_text:
            print("レース日時が見つかりません。クラス名が変更された可能性があります。")
            race_datetime_text = ""
        
        # ページソースを保存（デバッグ用）
        with open(f"debug/race_page_{race_id}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 開催場所の抽出（例: "東京"）
        venue = ""
        venue_pattern = r'(\d+回)([^\d]+)(\d+日)'
        venue_match = re.search(venue_pattern, race_data)
        if venue_match:
            venue = venue_match.group(2)
        else:
            # 別のパターンで試す
            venue_pattern2 = r'([^\d]+)(競馬場|ウインズ)'
            venue_match2 = re.search(venue_pattern2, race_data)
            if venue_match2:
                venue = venue_match2.group(1)
                
        venue_code = generate_venue_code(venue)
        
        # 日付の抽出（例: "2023年6月3日"）
        race_date = ""
        # 複数のパターンで試す
        date_patterns = [
            r'(\d+年\d+月\d+日)',
            r'(\d+/\d+/\d+)',
            r'(\d+-\d+-\d+)'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, race_datetime_text)
            if date_match:
                race_date_text = date_match.group(1)
                # 日付フォーマットを統一
                if '年' in race_date_text:
                    race_date = race_date_text.replace('年', '-').replace('月', '-').replace('日', '')
                elif '/' in race_date_text:
                    parts = race_date_text.split('/')
                    if len(parts) == 3:
                        race_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                else:
                    race_date = race_date_text
                break
        
        # 出馬表テーブルから馬情報を抽出（複数のセレクタを試す）
        horse_entries = []
        horse_rows = []
        
        # 複数の可能性のあるセレクタで馬リストを取得
        for selector in ['table.Shutuba_Table tr.HorseList', 'table.RaceTable01 tr']:
            rows = soup.select(selector)
            if rows:
                horse_rows = rows
                break
        
        if not horse_rows:
            print(f"馬情報が見つかりません: {race_url}")
            return None
        
        print(f"出走馬数: {len(horse_rows)}")
        
        for row in horse_rows:
            try:
                # スタイルによって馬番のセレクタが異なるため複数試す
                horse_number_elem = None
                for selector in ['.Waku span', '.Umaban', 'td:first-child']:
                    elem = row.select_one(selector)
                    if elem and elem.text.strip().isdigit():
                        horse_number_elem = elem
                        break
                        
                horse_number = int(horse_number_elem.text.strip()) if horse_number_elem else 0
                
                if horse_number == 0:
                    # おそらくヘッダー行なのでスキップ
                    continue
                
                # 枠番
                waku_num = 0
                waku_element = row.select_one('.Waku')
                if waku_element:
                    waku_class = waku_element.get('class', [])
                    # 枠番のクラス名から番号を抽出（例: "Waku1" → 1）
                    for class_name in waku_class:
                        if class_name.startswith('Waku') and len(class_name) > 4:
                            try:
                                waku_num = int(class_name[4:])
                            except ValueError:
                                pass
                
                # 馬名 - 複数のセレクタを試す
                horse_name = ""
                for selector in ['.HorseName a', '.HorseInfo a', 'td a[href*="horse"]']:
                    elem = row.select_one(selector)
                    if elem:
                        horse_name = elem.text.strip()
                        break
                        
                horse_id = generate_horse_id(horse_name) if horse_name else 0
                
                # 馬齢と性別 - 複数のセレクタを試す
                horse_info = ""
                for selector in ['.Barei', '.HorseInfo span', 'td:nth-child(4)']:
                    elem = row.select_one(selector)
                    if elem:
                        info_text = elem.text.strip()
                        # 性別年齢のパターン（例: 牡3, 牝5, セ6）をチェック
                        if re.match(r'^[牡牝セ]\d+$', info_text):
                            horse_info = info_text
                            break
                
                # 性別と年齢を抽出（例: "牡3" → 性別="牡", 年齢=3）
                gender = ""
                age = 0
                if horse_info:
                    gender = horse_info[0]  # 最初の文字（牡/牝/セ）
                    try:
                        age = int(horse_info[1:])
                    except ValueError:
                        pass
                
                # 斤量 - 複数のセレクタを試す
                weight = ""
                for selector in ['.Jockey .JockeyWeight', '.Jockey', 'td:nth-child(6)']:
                    elem = row.select_one(selector)
                    if elem:
                        text = elem.text.strip()
                        # 斤量のパターン（例: 54.0, 53.5）を検出
                        weight_match = re.search(r'\d+\.\d+', text)
                        if weight_match:
                            weight = weight_match.group(0)
                            break
                
                # 騎手 - 複数のセレクタを試す
                jockey_name = ""
                for selector in ['.Jockey a', 'td a[href*="jockey"]']:
                    elem = row.select_one(selector)
                    if elem:
                        jockey_name = elem.text.strip()
                        break
                        
                jockey_id = generate_jockey_id(jockey_name) if jockey_name else 0
                
                # 馬体重 - 複数のセレクタを試す
                horse_weight_text = ""
                for selector in ['.Weight', 'td:nth-child(9)', 'td.Weight']:
                    elem = row.select_one(selector)
                    if elem:
                        text = elem.text.strip()
                        # 馬体重のパターン（例: 466(+4), 480(-2)）を検出
                        if re.search(r'\d+\([+-]?\d+\)', text):
                            horse_weight_text = text
                            break
                
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
                
                # 最低限の情報が含まれているか確認
                if horse_name and jockey_name:
                    horse_entries.append(entry)
                
            except Exception as horse_error:
                print(f"馬データ処理中にエラー: {str(horse_error)}")
                continue
        
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
        print(f"レース情報スクレイピングエラー ({race_url}): {str(e)}")
        traceback.print_exc()
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

def get_race_urls_for_date(page, context, date_str: str) -> List[str]:
    """
    指定された日付のレースURLリストを取得する関数
    
    @param page: Playwrightのページオブジェクト
    @param context: Playwrightのコンテキストオブジェクト
    @param date_str: 日付文字列 (YYYY-MM-DD形式)
    @return: レースURLのリスト、エラー時は空リスト
    
    指定された日付のnetkeibaのカレンダーページにアクセスし、
    その日に開催される全レースのURLを抽出します。
    """
    all_race_urls = []  # 返却用のリスト
    
    try:
        # 日付をYYYYMMDD形式に変換
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_param = date_obj.strftime('%Y%m%d')
        
        # タイムアウトを設定
        page.set_default_timeout(90000)  # 90秒
        
        print(f"\n{date_str}のレース情報を取得中...")
        
        # カレンダーページに直接アクセス
        calendar_url = f"https://race.netkeiba.com/top/race_list.html?kaisai_date={date_param}"
        print(f"レース一覧ページにアクセスしています: {calendar_url}")
        
        # デバッグディレクトリを作成
        os.makedirs('debug', exist_ok=True)
        
        try:
            # ユーザーエージェントを変更して再設定
            context.clear_cookies()
            page.evaluate('''() => {
                Object.defineProperty(navigator, 'userAgent', {
                    get: function() {
                        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36';
                    }
                });
            }''')
            
            # ヘッダー情報を追加（一般的なブラウザのように見せる）
            page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # 最初に一般ページにアクセスしてクッキーを取得（ボット対策のため）
            print("最初にトップページにアクセスしてクッキーを取得...")
            page.goto("https://www.netkeiba.com/", wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)
            
            # 実際のページにアクセス（load条件で待機）
            print(f"競馬場別一覧ページにアクセス中... {calendar_url}")
            page.goto(calendar_url, wait_until='load', timeout=90000)
            print("ページの読み込みが完了しました")
            
            # スクリーンショットを保存（デバッグ用）
            page.screenshot(path=f"debug/screenshot_{date_param}.png")
            print(f"スクリーンショットを保存: debug/screenshot_{date_param}.png")
            
            # ページの準備が整うまで待機
            page.wait_for_timeout(5000)  # 5秒待機
            
            # JavaScriptが完全に実行されるのを待つ
            page.wait_for_function('''() => {
                return document.readyState === 'complete';
            }''', timeout=30000)
            
            print("JavaScriptの実行が完了しました")
        except TimeoutError:
            print("ページの完全な読み込みはタイムアウトしましたが、処理を継続します")
            # タイムアウト後も少し待つ
            page.wait_for_timeout(5000)
            # スクリーンショットを保存（タイムアウト後）
            page.screenshot(path=f"debug/timeout_screenshot_{date_param}.png")
            print(f"タイムアウト後のスクリーンショットを保存: debug/timeout_screenshot_{date_param}.png")
        
        # デバッグ用にHTMLを保存
        try:
            html_content = page.content()
            with open(f"debug/html_{date_param}.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("HTMLコンテンツをデバッグ用に保存しました")
        except Exception as e:
            print(f"HTMLコンテンツの保存中にエラー: {str(e)}")
        
        # 画像のようなレース表示を確認
        print("レース情報を探索中...")
        
        # ページ上にレース情報があるか確認（より緩やかな条件）
        race_text_present = page.evaluate('''() => {
            const bodyText = document.body.innerText;
            // より緩やかな条件（いずれかの要素があればOK）
            return bodyText.includes('R') || 
                   bodyText.includes('レース') || 
                   document.querySelector('*[class*="Race"]') !== null;
        }''')
        
        # 全角の数字も考慮に入れる
        if not race_text_present:
            race_text_present = page.evaluate('''() => {
                const bodyText = document.body.innerText;
                // 全角数字のレース表記をチェック
                return bodyText.includes('１Ｒ') || bodyText.includes('２Ｒ') || 
                       bodyText.includes('３Ｒ') || bodyText.includes('出走表');
            }''')
        
        # レース番号が直接の要素として存在するか確認
        race_nums_found = page.evaluate('''() => {
            const elements = Array.from(document.querySelectorAll('*'));
            const raceNumElements = elements.filter(el => 
                el.textContent && /^\d+R$/.test(el.textContent.trim())
            );
            return raceNumElements.length;
        }''')
        print(f"レース番号らしき要素の数: {race_nums_found}")
        
        if not race_text_present and race_nums_found == 0:
            print("ページ上にレース情報が見つかりません。この日はレースがない可能性があります。")
            
            # 表示されている日付ボタンをすべて取得してみる
            date_buttons = page.query_selector_all('a[href*="kaisai_date="]')
            print(f"日付ボタン数: {len(date_buttons)}")
            
            if len(date_buttons) > 0:
                print("利用可能な日付ボタン:")
                for i, btn in enumerate(date_buttons[:5]):  # 最初の5件だけ表示
                    text = btn.inner_text().strip()
                    href = btn.get_attribute('href')
                    print(f"  {i+1}. {text} - {href}")
            
            return all_race_urls
        
        print("ページ上にレース情報らしきものが見つかりました。URLを抽出します...")
        
        # 実際のレースブロックを取得（複数の競馬場に対応）
        race_blocks = []
        
        # まず、日付と時間情報を取得して確認
        race_dates = page.evaluate('''() => {
            const dateElements = Array.from(document.querySelectorAll('*'));
            return dateElements
                .filter(el => el.textContent && el.textContent.match(/\d+月\d+日/))
                .map(el => el.textContent.trim())
                .slice(0, 5);  // 最初の5件だけ
        }''');
        print("ページ上の日付情報:")
        for date_text in race_dates:
            print(f"  - {date_text}")
        
        # まず、レースリンクを直接セレクタで取得（スクリーンショットの階層構造に基づく）
        direct_race_selectors = [
            'a[href*="race_id="]',
            'a[href*="shutuba.html"]',
            'a[href*="result.html"]',
            '.RaceList_Item a',
            '.RaceList_ItemTitle a',
            'a[href*="/race/"]',
            '*[class*="Race"] a'
        ]
        
        for selector in direct_race_selectors:
            try:
                links = page.query_selector_all(selector)
                print(f"セレクタ '{selector}' によるリンク数: {len(links)}")
                if links:
                    for link in links:
                        href = link.get_attribute('href')
                        text = link.inner_text().strip()
                        if href and ('race_id=' in href or 'shutuba.html' in href or 'result.html' in href):
                            race_blocks.append(link)
                            if len(race_blocks) <= 5:  # 最初の5件だけ表示
                                print(f"  リンク: {text} - {href}")
            except Exception as e:
                print(f"セレクタ '{selector}' の処理中にエラー: {str(e)}")
        
        print(f"直接セレクタで取得したレースリンク数: {len(race_blocks)}")
        
        # リンクが見つからない場合は、エレメントのクリックを試みる
        if len(race_blocks) == 0:
            print("リンクが見つからないため、レース番号要素を検索してクリックを試みます...")
            
            # 数字+Rのパターンを持つ要素を検索
            race_num_elements = page.query_selector_all('div:has-text(/[0-9]+R/)')
            print(f"レース番号を含む要素数: {len(race_num_elements)}")
            
            for i, elem in enumerate(race_num_elements[:5]):  # 最初の5件だけ処理
                try:
                    text = elem.inner_text().strip()
                    print(f"要素 {i+1}: {text}")
                    
                    # 要素をクリックしてみる
                    elem.click()
                    page.wait_for_timeout(2000)
                    
                    # 現在のURLを取得
                    current_url = page.url
                    if 'race_id=' in current_url:
                        print(f"クリック後のURL: {current_url}")
                        race_id_match = re.search(r'race_id=(\d+)', current_url)
                        if race_id_match:
                            race_id = race_id_match.group(1)
                            shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                            if shutuba_url not in all_race_urls:
                                all_race_urls.append(shutuba_url)
                                print(f"クリックから取得したURL: {shutuba_url}")
                    
                    # 元のページに戻る
                    page.goto(calendar_url, wait_until='domcontentloaded')
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"要素クリック処理中にエラー: {str(e)}")
        
        # R数字のテキストを含む要素から探す
        if len(race_blocks) == 0:
            try:
                # 正規表現でより柔軟に検索
                r_elements_js = page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    return elements
                        .filter(el => el.textContent && (
                            /\\d+R/.test(el.textContent.trim()) ||
                            /\\d+レース/.test(el.textContent.trim())
                        ))
                        .map(el => ({
                            text: el.textContent.trim(),
                            id: el.id || '',
                            className: el.className || '',
                            tagName: el.tagName
                        }))
                        .slice(0, 10);  // 最初の10件だけ
                }''')
                
                print(f"正規表現で検出したR番号要素数: {len(r_elements_js)}")
                for i, elem_info in enumerate(r_elements_js):
                    print(f"  要素 {i+1}: {elem_info.get('text')} - {elem_info.get('tagName')} (id={elem_info.get('id')}, class={elem_info.get('className')})")
                
                # 検出した要素を使ってリンクを探索
                for elem_info in r_elements_js:
                    class_name = elem_info.get('className', '')
                    if class_name:
                        selector = f".{class_name.replace(' ', '.')} a, .{class_name.replace(' ', '.')} > a"
                        links = page.query_selector_all(selector)
                        if links:
                            for link in links:
                                href = link.get_attribute('href')
                                if href and 'race_id=' in href:
                                    race_blocks.append(link)
            except Exception as e:
                print(f"R番号要素の処理中にエラー: {str(e)}")
        
        print(f"レースブロック合計数: {len(race_blocks)}")
        
        # レースブロックからURLを抽出
        for block in race_blocks:
            try:
                href = block.get_attribute('href')
                if href and ('race_id=' in href or 'shutuba.html' in href or 'result.html' in href):
                    # 相対パスを絶対パスに変換
                    full_url = href
                    if href.startswith("../"):
                        full_url = href.replace("../", "https://race.netkeiba.com/")
                    elif href.startswith("/"):
                        full_url = f"https://race.netkeiba.com{href}"
                    elif not href.startswith("http"):
                        full_url = f"https://race.netkeiba.com/{href}"
                    
                    # レースIDを抽出
                    race_id_match = re.search(r'race_id=(\d+)', full_url)
                    race_id = race_id_match.group(1) if race_id_match else None
                    
                    # 出走表URLに変換
                    if race_id:
                        shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                        
                        # 重複チェック
                        if shutuba_url not in all_race_urls:
                            all_race_urls.append(shutuba_url)
                            print(f"レースURL追加: {shutuba_url}")
            except Exception as e:
                print(f"レースブロック処理エラー: {str(e)}")
                continue
        
        # 画像から確認した競馬場情報から直接構築（最後の手段）
        if len(all_race_urls) == 0:
            print("リンクからURLを取得できなかったため、競馬場情報から直接構築します...")
            
            # 競馬場コードと有効なレースIDパターンのマッピング
            venue_patterns = {
                "福島": {"venue_code": "03", "kaisai_kai": "1", "kaisai_day": "3"},
                "阪神": {"venue_code": "09", "kaisai_kai": "2", "kaisai_day": "7"},
                "中山": {"venue_code": "06", "kaisai_kai": "3", "kaisai_day": "7"}
            }
            
            # ページ内の文字列から競馬場名を検出
            try:
                page_text = page.inner_text('body')
                detected_venues = []
                
                for venue_name in venue_patterns.keys():
                    if venue_name in page_text:
                        detected_venues.append(venue_name)
                        print(f"競馬場 {venue_name} を検出しました")
                
                # 競馬場が検出できなくても、スクリーンショットの情報から手動で指定
                if not detected_venues:
                    print("競馬場が検出できなかったため、既知の競馬場を使用")
                    detected_venues = ["福島", "阪神", "中山"]
                
                # 日付の文字を検出（例: 4月19日(土)）
                date_pattern = r'(\d+)月(\d+)日\(.\)'
                date_matches = re.findall(date_pattern, page_text)
                
                # 日付から月と日を取得（直近の一致を使用）
                if date_matches:
                    month, day = date_matches[-1]
                    print(f"レース日: {month}月{day}日")
                elif date_str:
                    # 日付が検出できなければ引数の日付を使用
                    month = date_obj.month
                    day = date_obj.day
                    print(f"日付が検出できなかったため指定日付を使用: {month}月{day}日")
                
                # 検出された競馬場ごとにレースIDを生成
                for venue_name in detected_venues:
                    venue_info = venue_patterns.get(venue_name, {})
                    venue_code = venue_info.get("venue_code", "")
                    kaisai_kai = venue_info.get("kaisai_kai", "")
                    kaisai_day = venue_info.get("kaisai_day", "")
                    
                    if venue_code and kaisai_kai and kaisai_day:
                        year = date_obj.year
                        
                        # レースIDの基本部分を生成
                        base_race_id = f"{year}{venue_code}{kaisai_kai.zfill(2)}{kaisai_day.zfill(2)}"
                        
                        # 各レース番号（1R～12R）にURLを生成
                        for race_num in range(1, 13):
                            race_id = f"{base_race_id}{race_num:02d}"
                            shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
                            
                            # 重複チェック
                            if shutuba_url not in all_race_urls:
                                all_race_urls.append(shutuba_url)
                                print(f"生成されたURL追加: {shutuba_url}")
            except Exception as e:
                print(f"競馬場情報からのURL生成中にエラー: {str(e)}")
        
        # URLの有効性を確認（サンプルとしての最初の数件）
        if all_race_urls:
            valid_urls = []
            test_count = min(3, len(all_race_urls))
            print(f"生成したURLのサンプル {test_count}件の有効性を確認中...")
            
            for i, url in enumerate(all_race_urls[:test_count]):
                try:
                    test_page = context.new_page()
                    try:
                        test_page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        page.wait_for_timeout(2000)
                        
                        # 有効なページかチェック
                        title = test_page.title()
                        test_page.screenshot(path=f"debug/url_test_{i+1}.png")
                        print(f"URL {i+1} テスト: {title}")
                        
                        if "404" not in title and "エラー" not in title and "見つかりません" not in title:
                            valid_urls.append(url)
                            print(f"  有効なURL: {url}")
                        else:
                            print(f"  無効なURL: {url}")
                    finally:
                        test_page.close()
                except Exception as e:
                    print(f"  URLテストエラー: {url} - {str(e)}")
            
            # 有効性確認の結果を表示
            if valid_urls:
                print(f"{len(valid_urls)}/{test_count}件のURLが有効です。全URLを保持します。")
            else:
                print(f"テストしたすべてのURLが無効でした。ただし、全URLを保持します（障害の可能性あり）。")
        
        # 結果を出力
        print(f"{date_str}のレースURL数: {len(all_race_urls)}")
        
        if len(all_race_urls) > 0:
            for i, url in enumerate(all_race_urls[:3], 1):  # 最初の3件だけ表示
                print(f"URL {i}: {url}")
        else:
            print(f"{date_str}のレースはありません")
        
        return all_race_urls
        
    except Exception as e:
        # エラー発生時の処理
        print(f"レースURL取得エラー: {str(e)}")
        traceback.print_exc()
        return all_race_urls

def get_jra_race_info_for_dates(dates_list):
    """
    指定された日付リストのJRAレース情報を取得する関数
    
    @param dates_list: 日付文字列のリスト (YYYY-MM-DD形式)
    @return: 取得したエントリー情報のリスト
    
    この関数は、指定された複数日付のJRAレース出走表情報を一括で取得します。
    Playwrightを使用してブラウザを操作し、各日付のレースページにアクセスしてデータをスクレイピングします。
    """
    all_entries = []
    entries_by_date = {}
    
    try:
        # Playwrightの設定
        with sync_playwright() as playwright:
            # ブラウザの起動（ヘッドレスモード）
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
            )
            page = context.new_page()
            
            # 各日付のレース情報を取得
            print(f"\n処理対象日: {', '.join(dates_list)}")
            for date_str in dates_list:
                try:
                    print(f"\n{date_str}のレース情報を取得します...")
                    
                    # URLを取得（contextも渡す）
                    race_urls = get_race_urls_for_date(page, context, date_str)
                    print(f"{date_str}のレースURL数: {len(race_urls)}")
                    
                    if race_urls:
                        success_count = 0
                        date_entries = []  # この日付用のエントリーリスト
                        
                        # 各レースの出馬表を取得
                        for idx, race_url in enumerate(race_urls, 1):
                            try:
                                print(f"[{idx}/{len(race_urls)}] スクレイピング中: {race_url}")
                                race_entry = scrape_race_entry(page, race_url)
                                
                                if race_entry and race_entry.get('entries') and len(race_entry['entries']) > 0:
                                    # この日付のエントリーリストに追加
                                    date_entries.extend(race_entry['entries'])
                                    # 全体のエントリーリストにも追加
                                    all_entries.extend(race_entry['entries'])
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
                        
                        # 日付ごとにエントリーを記録
                        if date_entries:
                            date_key = date_str.replace('-', '')
                            entries_by_date[date_key] = date_entries
                            print(f"{date_str}の出走馬データ: {len(date_entries)}件")
                        
                        print(f"{date_str}の処理完了: {success_count}/{len(race_urls)}件のレースを取得")
                    else:
                        print(f"{date_str}のレースが見つかりませんでした")
                
                except Exception as e:
                    print(f"{date_str}の処理中にエラー: {str(e)}")
                    traceback.print_exc()
                    continue
            
            # ブラウザの終了
            browser.close()
        
        # 日付ごとのエントリー情報を保存
        for date_key, entries in entries_by_date.items():
            output_dir = 'data/race_entries'
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f'jra_race_entries_{date_key}.csv')
            
            if entries and len(entries) > 0:
                save_to_csv(entries, output_path)
                print(f"{date_key}: {len(entries)}件のエントリーを保存しました: {output_path}")
            else:
                print(f"{date_key}: エントリーがないためCSVは保存しませんでした")
        
    except Exception as e:
        print(f"全体の処理中にエラー発生: {str(e)}")
        traceback.print_exc()
    
    return all_entries

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
    
    # スクリプト実行のタイプを表示
    script_type = "単体スクリプト" if __name__ == '__main__' else "モジュール"
    print(f"JRA出走表スクレイピングを開始します（実行モード: {script_type}）")
    
    # 引数で日付が指定されている場合はその日付のデータを取得
    if args.date:
        try:
            # 日付形式の検証
            target_date = datetime.strptime(args.date, '%Y-%m-%d').strftime('%Y-%m-%d')
            print(f"指定された日付 {target_date} の出走表情報を取得します...")
            
            # 指定された日付のレース情報を取得
            get_jra_race_info_for_dates([target_date])
            
        except ValueError:
            # 日付形式が不正な場合のエラー処理
            print("日付の形式が不正です。YYYY-MM-DD形式で指定してください")
            sys.exit(1)
    else:
        # 引数がない場合は今日から3日間のデータを取得
        print("今日から3日間の出走表情報を取得します...")
        
        # 今日から3日間の日付を取得
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
        print(f"処理対象日: {', '.join(dates)}")
        
        # 3日分のレース情報を取得
        get_jra_race_info_for_dates(dates)
        
        # 処理完了メッセージ
        print("\nすべての処理が完了しました")
        print("CSVファイルは data/race_entries/ ディレクトリに保存されています")
        print("ファイル名形式: jra_race_entries_YYYYMMDD.csv") 