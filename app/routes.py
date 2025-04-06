from flask import render_template, request, jsonify, redirect, url_for, flash, current_app, session, abort
from app import app, db
from app.models import (
    Horse, Race, Entry, Jockey, User, Favorite, 
    RaceReview, RaceMemo, UserSettings, ReviewPurchase, 
    Notification, LoginHistory, SupportTicket, 
    MembershipChangeLog, PaymentLog, ShutubaEntry,
    HorseMemo
)
from datetime import datetime, timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email as EmailValidator
from flask_login import login_required, current_user, login_user, UserMixin, LoginManager, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import traceback
import json
from sqlalchemy import and_, desc, func, or_, distinct, case, String, Integer, DateTime, cast
from sqlalchemy.orm import joinedload, subqueryload, load_only
from collections import defaultdict
from app.payments import PaymentManager
from app.forms import ChargePointForm, RegistrationForm
from werkzeug.utils import secure_filename
from functools import lru_cache
import stripe
import shutil
from calendar import monthrange
import logging

# カスタムコレータの定義（ファイルの先頭付近に配置）
def custom_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ルートの定義
@app.route('/')
@app.route('/index')
def index():
    # ここに特別な処理があるか確認
    return render_template('index.html')

class LoginForm(FlaskForm):
    email = StringField('メールアドレス', validators=[DataRequired(), EmailValidator()])
    password = PasswordField('パスワード', validators=[DataRequired()])
    submit = SubmitField('ログイン')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()  # usernameをemailに変更
        if user is None or not user.check_password(form.password.data):
            flash('メールアドレスまたはパスワードが正しくありません')
            return redirect(url_for('login'))
        login_user(user)  # remember_meフィールドを削除
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='ログイン', form=form)

@app.route('/logout')
def logout():
    logout_user()
    flash('ログアウトしました', 'success')
    return redirect(url_for('index'))

# 会場コードと会場名の辞書を定数として定義
VENUE_NAMES = {
    '101': '札幌', '102': '函館', '103': '福島', '104': '新潟',
    '105': '東京', '106': '中山', '107': '中京', '108': '京都',
    '109': '阪神', '110': '小倉', '201': '門別', '202': '帯広',
    '203': '盛岡', '204': '水沢', '205': '浦和', '206': '船橋',
    '207': '大井', '208': '川崎', '209': '金沢', '210': '笠松',
    '211': '名古屋', '212': '園田', '213': '姫路', '214': '高知',
    '215': '佐賀'
}

def normalize_venue_name(venue):
    """会場名を正規化する"""
    # 例: '11回浦和15日目' → '浦和'
    # 数字と「回」「日目」を削除
    import re
    
    # 会場名のマッピング
    venue_mapping = {
        '浦和': ['浦和', '浦和(4R-6R)', '浦和(9R-12R)', '11回浦和15日目'],
        '名古屋': ['名古屋', '25回名古屋5日目'],
        '佐賀': ['佐賀', '佐賀(4R-6R)', '佐賀(9R-12R)'],
        '帯広': ['帯広', '帯広(4R-6R)', '帯広(9R-12R)']
    }
    
    # 会場名を正規化
    for normalized_name, variations in venue_mapping.items():
        if any(variation in venue for variation in variations):
            return normalized_name
            
    # マッピングにない場合は数字と「回」「日目」を削除
    normalized = re.sub(r'\d+回|\d+日目|\([^\)]+\)', '', venue).strip()
    return normalized

def get_venue_code(venue_name):
    """会場名からコードを取得"""
    # 各会場名が含まれているかチェックし、最初に見つかった会場のコードを返す
    for code, name in VENUE_NAMES.items():
        if name in venue_name:
            return code
    return None

@app.route('/races')
def races():
    try:
        app.logger.info('Starting races route')
        # 利用可能な日付を取得
        available_dates = db.session.query(
            func.date(Race.date).label('race_date')
        ).distinct().order_by(
            func.date(Race.date).desc()
        ).all()
        
        app.logger.info(f'Available dates: {available_dates}')
        
        # 日付一覧の作成
        dates = []
        for date_row in available_dates:
            date = date_row.race_date
            dates.append({
                'value': date.strftime('%Y%m%d'),
                'month': date.month,
                'day': date.day,
                'weekday': date.strftime('%a')
            })

        # 選択された日付の取得
        selected_date = request.args.get('date')
        if selected_date:
            selected_date = datetime.strptime(selected_date, '%Y%m%d').date()
        else:
            selected_date = available_dates[0].race_date if available_dates else datetime.now().date()

        # レース情報の取得
        races = Race.query.filter(
            func.date(Race.date) == selected_date
        ).all()

        # 会場ごとにグループ化
        venue_races = {}
        for race in races:
            venue_code = get_venue_code(race.venue)
            if venue_code:
                if venue_code not in venue_races:
                    venue_races[venue_code] = {
                        'venue_name': VENUE_NAMES[venue_code],
                        'weather': getattr(race, 'weather', '不明'),
                        'track_condition': getattr(race, 'track_condition', '不明'),
                        'races': []
                    }
                venue_races[venue_code]['races'].append(race)

        # レースを各会場内でソート
        for venue_data in venue_races.values():
            venue_data['races'].sort(key=lambda x: x.race_number)

        return render_template(
            'races.html',
            dates=dates,
            selected_date=selected_date.strftime('%Y%m%d'),
            venue_races=venue_races,
            venues=VENUE_NAMES
        )

    except Exception as e:
        app.logger.error(f'Error: {str(e)}')
        return render_template(
            'races.html',
            dates=[],
            selected_date=datetime.now().strftime('%Y%m%d'),
            venue_races={},
            venues=VENUE_NAMES,
            error=str(e)
        )

@app.route('/races/<int:race_id>')
def race(race_id):
    try:
        race = Race.query.get_or_404(race_id)
        entries = db.session.query(Entry)\
            .join(Horse)\
            .outerjoin(Jockey)\
            .filter(Entry.race_id == race_id)\
            .options(
                joinedload(Entry.horse),
                joinedload(Entry.jockey)
            )\
            .order_by(Entry.horse_number.asc())\
            .all()
            
        return render_template('race_detail.html', 
                             race=race, 
                             entries=entries)
    except Exception as e:
        app.logger.error(f"Error in race: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_race', methods=['GET', 'POST'])
def add_race():
    if request.method == 'POST':
        name = request.form['name']
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        venue = request.form['venue']
        race = Race(name=name, date=date, venue=venue)
        db.session.add(race)
        db.session.commit()
        flash('レースが追されました', 'success')
        return redirect(url_for('races'))
    return render_template('add_race.html')

@app.route('/add_horse', methods=['GET', 'POST'])
def add_horse():
    if request.method == 'POST':
        name = request.form['name']
        horse = Horse(name=name)
        db.session.add(horse)
        db.session.commit()
        flash('馬が追加し', 'success')
        return redirect(url_for('horses'))
    return render_template('add_horse.html')

@app.route('/horses')
def horses():
    try:
        print("horses route started")
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        # シンプルなクエリ
        query = Horse.query
        
        if search:
            query = query.filter(Horse.name.ilike(f'%{search}%'))
        
        # ページネーション設定
        pagination = query.order_by(Horse.id.desc()).paginate(
            page=page,
            per_page=24,  # 1ページあたり24頭
            error_out=False
        )
        
        print(f"Page {page}: Found {len(pagination.items)} horses")
        
        return render_template('horses.html',
            horses=pagination.items,
            pagination=pagination,
            search=search)
            
    except Exception as e:
        print(f"Error in horses route: {str(e)}")
        return render_template('horses.html', horses=[], pagination=None, search='')

@app.route('/record_result', methods=['GET', 'POST'])
def record_result():
    race_id = request.args.get('race_id')
    race = Race.query.get_or_404(race_id)
    horses = Horse.query.all()

    if request.method == 'POST':
        horse_id = request.form['horse_id']
        finish_position = request.form['finish_position']
        jockey = request.form['jockey']
        time = request.form['time']
        weight = request.form.get('weight', 0)
        weight_change = request.form.get('weight_change', 0)

        entry = Entry(
            race_id=race.id,
            horse_id=horse_id,
            jockey_id=jockey,  # jockey_idに
            finish_position=finish_position,
            time=time,
            weight=weight,
            weight_change=weight_change
        )
        db.session.add(entry)
        db.session.commit()

        flash('レー結果が記録されました。', 'success')
        return redirect(url_for('upcoming_races'))

    return render_template('record_result.html', race=race, horses=horses)

@app.route('/upcoming_races', methods=['GET', 'POST'])
def upcoming_races():
    if request.method == 'POST':
        race_id = request.form['race_id']
        horse_ids = request.form.getlist('horse_ids')
        
        # 既エトーを除
        UpcomingRace.query.filter_by(race_id=race_id).delete()
        
        for horse_id in horse_ids:
            upcoming_race = UpcomingRace(race_id=race_id, horse_id=horse_id)
            db.session.add(upcoming_race)
        
        db.session.commit()
        flash('出表更新されました', 'success')
        return redirect(url_for('upcoming_races'))
    
    upcoming_races = UpcomingRace.query.join(Race).order_by(Race.date).all()
    races = Race.query.filter(Race.date >= datetime.now()).order_by(Race.date).all()
    horses = Horse.query.order_by(Horse.name).all()
    return render_template('upcoming_races.html', upcoming_races=upcoming_races, races=races, horses=horses)

@app.route('/horses/<int:horse_id>')
def horse_detail(horse_id):
    try:
        # SQLAlchemyのクエリログを有効化
        logging.basicConfig()
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        
        current_app.logger.info(f"Starting horse_detail route with ID: {horse_id}")
        
        # クエリの実行
        horse = db.session.query(Horse).get_or_404(horse_id)
        current_app.logger.info(f"Horse query executed: {horse.name if horse else 'Not found'}")
        
        entries_query = db.session.query(
            Entry,
            Race.date,
            Race.name.label('race_name'),
            Jockey.name.label('jockey_name')
        ).join(
            Race
        ).outerjoin(
            Jockey
        ).filter(
            Entry.horse_id == horse_id,
            Race.date.isnot(None)
        ).order_by(
            Race.date.desc()
        )
        
        # クエリの内容を出力
        current_app.logger.info(f"Entries query: {str(entries_query)}")
        
        entries = entries_query.all()
        current_app.logger.info(f"Found {len(entries)} entries")
        
        # 結果の整形
        race_results = []
        for entry, race_date, race_name, jockey_name in entries:
            race_results.append({
                'race': {
                    'id': entry.race_id,
                    'date': race_date,
                    'name': race_name
                },
                'horse_number': entry.horse_number,
                'jockey': {'name': jockey_name},
                'time': entry.time,
                'weight': entry.weight,
                'weight_change': entry.weight_change if hasattr(entry, 'weight_change') else None
            })
        
        is_favorite = False
        if current_user.is_authenticated:
            is_favorite = db.session.query(Favorite).filter_by(
                user_id=current_user.id,
                horse_id=horse_id
            ).first() is not None
        
        memos = json.loads(horse.memo) if horse.memo else []
        
        return render_template('horse_detail.html', 
                             horse=horse,
                             entries=race_results,  # 整形したデータを渡す
                             is_favorite=is_favorite,
                             memos=memos)
                             
    except Exception as e:
        current_app.logger.error(f"Error in horse_detail: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return render_template('error.html', 
                             error_message="馬の詳細情報の取得中にエラーが発生しました。",
                             debug_info=str(e)), 500

@app.route('/horses/<int:horse_id>/memo', methods=['POST'])
@login_required
def save_horse_memo(horse_id):
    try:
        app.logger.info(f'Saving memo for horse {horse_id} by user {current_user.id}')
        content = request.form.get('content')
        if not content:
            flash('メモ内容を入力してください', 'error')
            return redirect(url_for('horse_detail', horse_id=horse_id))
            
        horse = db.session.query(Horse).get_or_404(horse_id)
        
        # メモの追加処理を改善
        try:
            current_memos = json.loads(horse.memo) if horse.memo else []
        except (json.JSONDecodeError, TypeError):
            app.logger.warning(f'Invalid memo format for horse {horse_id}, resetting to empty list')
            current_memos = []
        
        new_memo = {
            'id': len(current_memos) + 1,
            'content': content,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': current_user.id
        }
        
        current_memos.append(new_memo)
        horse.memo = json.dumps(current_memos)
        
        # 最終更新日時も更新
        horse.updated_at = datetime.now()
        
        db.session.commit()
        app.logger.info(f'Memo saved successfully for horse {horse_id}')
        flash('メモを保存しました', 'success')
        
    except Exception as e:
        app.logger.error(f'Error saving memo: {str(e)}')
        db.session.rollback()
        flash('メモの保存に失敗しました', 'error')
    
    # リファラーに基づいてリダイレクト
    referer = request.referrer
    if referer and 'race_detail' in referer:
        return redirect(referer)
    return redirect(url_for('horse_detail', horse_id=horse_id))

@app.route('/horse/<int:horse_id>/memo/<int:memo_id>', methods=['DELETE'])
@login_required
def delete_horse_memo(horse_id, memo_id):
    try:
        horse = db.session.query(Horse).get_or_404(horse_id)
        current_memos = json.loads(horse.memo) if horse.memo else []
        
        # メモの削除処理
        updated_memos = [memo for memo in current_memos if memo['id'] != memo_id]
        horse.memo = json.dumps(updated_memos)
        
        db.session.commit()
        return jsonify({'status': 'success'})
        
    except Exception as e:
        current_app.logger.error(f"Error deleting memo: {str(e)}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add_memo/<int:horse_id>', methods=['POST'])
def add_memo(horse_id):
    horse = Horse.query.get_or_404(horse_id)
    memo = request.form['memo']
    new_note = HorseNote(horse_id=horse_id, note=memo)
    db.session.add(new_note)
    db.session.commit()
    return redirect(url_for('main.horse_detail', horse_id=horse_id))

@app.route('/import_horses', methods=['GET', 'POST'])
def import_horses():
    if request.method == 'POST':
        csv_file_path = os.path.join(current_app.root_path, '..', 'horse_list_all.csv')
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                horse = Horse.query.filter_by(horse_id=row['horse_id']).first()
                if horse:
                    horse.name = row['name']
                    horse.sex = row['sex']
                    horse.birth_year = int(row['birth_year'])
                    horse.trainer = row['trainer']
                else:
                    horse = Horse(
                        horse_id=row['horse_id'],
                        name=row['name'],
                        sex=row['sex'],
                        birth_year=int(row['birth_year']),
                        trainer=row['trainer']
                    )
                    db.session.add(horse)
        
        db.session.commit()
        flash('馬のデータをインポーしまた。', 'success')
        return redirect(url_for('main.horses'))
    return render_template('import_horses.html')

@app.route('/memos')
@login_required
def memos():
    try:
        # メモ付きの馬を取得
        horses_with_memos = db.session.query(Horse).filter(
            Horse.memo.isnot(None)
        ).options(
            load_only('id', 'name', 'memo')
        ).all()
        
        # レースメモを取得
        race_memos = db.session.query(RaceMemo).filter(
            RaceMemo.user_id == current_user.id
        ).options(
            joinedload(RaceMemo.race).load_only('id', 'name', 'date')
        ).order_by(
            RaceMemo.created_at.desc()
        ).all()
        
        return render_template('mypage/memos.html',
                             title='メモ一覧',
                             horses=horses_with_memos,
                             race_memos=race_memos)
                             
    except Exception as e:
        current_app.logger.error(f"Error in memos route: {str(e)}")
        flash('メモ一覧の取得中にエラーが発生しました', 'error')
        return render_template('mypage/memos.html',
                             title='メモ一覧',
                             horses=[],
                             race_memos=[])

@app.route('/edit_memo/<int:horse_id>', methods=['GET', 'POST'])
def edit_memo(horse_id):
    horse = Horse.query.get_or_404(horse_id)
    if request.method == 'POST':
        horse.memo = request.form['memo']
        db.session.commit()
        flash('メモ更新された。', 'success')
        return redirect(url_for('main.memos'))
    return render_template('edit_memo.html', horse=horse)

@app.route('/edit_race/<int:race_id>', methods=['GET', 'POST'])
def edit_race(race_id):
    race = Race.query.get_or_404(race_id)
    if request.method == 'POST':
        race.name = request.form['name']
        race.date = request.form['date']
        race.course = request.form['course']
        race.distance = request.form['distance']
        race.race_type = request.form['race_type']
        race.prize = request.form['prize']
        db.session.commit()
        flash('ース報が更新た。', 'success')
        return redirect(url_for('main.races'))
    return render_template('edit_race.html', race=race)

@app.route('/horse/<int:horse_id>/note', methods=['GET', 'POST'])
def horse_note(horse_id):
    horse = Horse.query.get_or_404(horse_id)
    
    if request.method == 'POST':
        note_text = request.json.get('note')
        horse.add_memo(note_text)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'note': horse.get_memos() if horse.memo else []})

@app.route('/races/<int:race_id>/memo', methods=['POST'])
@login_required
def save_race_memo(race_id):
    try:
        content = request.form.get('memo')
        if not content:
            flash('メモ内容を入力してください', 'error')
            return redirect(f'/races/{race_id}')  # 直接URLを指定
            
        race = Race.query.get_or_404(race_id)
        
        memo = RaceMemo(
            race_id=race_id,
            user_id=current_user.id,
            content=content,
            created_at=datetime.now()
        )
        
        db.session.add(memo)
        db.session.commit()
        flash('メモを保存しました', 'success')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error saving race memo: {str(e)}')
        flash('メモの保存に失敗しました', 'error')
    
    # 正しいレース詳細ページにリダイレクト
    return redirect(f'/races/{race_id}')

def format_date(date_str):
    """文字整形す"""
    try:
        if isinstance(date_str, str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%Y年%m月%d日')
        return 'N/A'
    except ValueError:
        try:
            # のの
            if len(date_str) == 4:
                return f"{date_str}年"
            return date_str
        except:
            return 'N/A'

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        horses = Horse.query.filter(Horse.name.like(f'%{query}%')).all()
    else:
        horses = []
    return render_template('search_results.html', horses=horses, query=query)

# キャッシュされたデータを保持
jockey_stats_cache = {
    'data': None,
    'timestamp': None
}

# キャッシュの有効期限（1時間）
CACHE_DURATION = timedelta(hours=1)

def get_cached_jockey_stats():
    current_time = datetime.now()
    
    # キャッシュ有効な場合はキャッシュ返す
    if (jockey_stats_cache['data'] is not None and 
        jockey_stats_cache['timestamp'] is not None and 
        current_time - jockey_stats_cache['timestamp'] < CACHE_DURATION):
        return jockey_stats_cache['data']
    
    # 中央競馬の開催場所リスト
    central_venues = ['東京', '中山', '阪神', '京都', '中京', '小倉', '福島', '新潟', '札幌']
    
    # 1回のクエリで必要なデータを全て取得
    results = db.session.query(
        Jockey.id,
        Jockey.name,
        Entry.position,
        Race.venue
    ).select_from(Jockey).outerjoin(
        Entry
    ).outerjoin(
        Race, Entry.race_id == Race.id
    ).all()
    
    # データを騎手ごとに整理
    jockey_data = {}
    for jockey_id, name, position, venue in results:
        if jockey_id not in jockey_data:
            jockey_data[jockey_id] = {
                'name': name,
                'total_rides': 0,
                'wins': 0,
                'seconds': 0,
                'thirds': 0,
                'central_races': 0,
                'local_races': 0
            }
        
        if position is not None:
            jockey_data[jockey_id]['total_rides'] += 1
            if position == 1:
                jockey_data[jockey_id]['wins'] += 1
            elif position == 2:
                jockey_data[jockey_id]['seconds'] += 1
            elif position == 3:
                jockey_data[jockey_id]['thirds'] += 1
        
        if venue:
            if any(v in venue for v in central_venues):
                jockey_data[jockey_id]['central_races'] += 1
            else:
                jockey_data[jockey_id]['local_races'] += 1
    
    # 統計データを作成
    jockey_stats = []
    for jockey_id, data in jockey_data.items():
        total_rides = data['total_rides']
        wins = data['wins']
        seconds = data['seconds']
        thirds = data['thirds']
        
        jockey_stats.append({
            'id': jockey_id,
            'name': data['name'],
            'total_rides': total_rides,
            'wins': wins,
            'seconds': seconds,
            'thirds': thirds,
            'others': total_rides - (wins + seconds + thirds),
            'win_rate': round((wins / total_rides * 100), 1) if total_rides > 0 else 0,
            'place_rate': round(((wins + seconds + thirds) / total_rides * 100), 1) if total_rides > 0 else 0,
            'affiliation': "中央" if data['central_races'] >= data['local_races'] else "地方"
        })
    
    # 勝利数で降順ソート
    jockey_stats.sort(key=lambda x: x['wins'], reverse=True)
    
    # キャッシュを更新
    jockey_stats_cache['data'] = jockey_stats
    jockey_stats_cache['timestamp'] = current_time
    
    return jockey_stats

@app.route('/jockeys')
def jockeys():
    try:
        jockey_stats = get_cached_jockey_stats()
        return render_template('jockeys.html', jockey_stats=jockey_stats)
    except Exception as e:
        current_app.logger.error(f"Error fetching jockeys: {str(e)}")
        traceback.print_exc()
        return render_template('jockeys.html', jockey_stats=[])

@app.route('/jockey/<int:jockey_id>')
def jockey_detail(jockey_id):
    try:
        jockey = Jockey.query.get_or_404(jockey_id)
        
        # 騎手の全レース履歴取得
        entries = Entry.query.filter_by(jockey_id=jockey_id).all()
        total_rides = len(entries)
        wins = sum(1 for e in entries if e.position == 1)
        seconds = sum(1 for e in entries if e.position == 2)
        thirds = sum(1 for e in entries if e.position == 3)
        
        # 央競馬の開催場所リスト
        central_venues = ['東京', '中山', '阪神', '京都', '中京', '小倉', '福島', '新潟', '札幌']
        
        # レース情報を取得して所属を判
        races = db.session.query(Race).join(Entry).filter(Entry.jockey_id == jockey_id).all()
        
        # venueがNoneの場合のエラー処理を追加
        central_races = sum(1 for r in races if r.venue and any(venue in r.venue for venue in central_venues))
        local_races = sum(1 for r in races if r.venue and not any(venue in r.venue for venue in central_venues))
        
        # 主な所属を判断（レース数の多い方）
        affiliation = "中央" if central_races >= local_races else "地方"
        
        stats = {
            'total_rides': total_rides,
            'wins': wins,
            'seconds': seconds,
            'thirds': thirds,
            'others': total_rides - (wins + seconds + thirds),
            'win_rate': round((wins / total_rides * 100), 1) if total_rides > 0 else 0,
            'place_rate': round(((wins + seconds + thirds) / total_rides * 100), 1) if total_rides > 0 else 0,
            'central_races': central_races,
            'local_races': local_races,
            'affiliation': affiliation
        }
        
        # 最近の騎乗成績を取得（最新10件）
        recent_rides = db.session.query(
            Entry, Race, Horse
        ).join(
            Race, Entry.race_id == Race.id
        ).join(
            Horse, Entry.horse_id == Horse.id
        ).filter(
            Entry.jockey_id == jockey_id
        ).order_by(
            Race.date.desc()
        ).limit(10).all()

        # 日のフォーマット
        for entry, race, horse in recent_rides:
            if isinstance(race.date, str):
                race.formatted_date = datetime.strptime(race.date, '%Y-%m-%d').strftime('%Y/%m/%d')
            else:
                race.formatted_date = race.date.strftime('%Y/%m/%d')

        return render_template('jockey_detail.html', 
                             jockey=jockey,
                             stats=stats,
                             recent_rides=recent_rides)

    except Exception as e:
        current_app.logger.error(f"Error fetching jockey details: {str(e)}")
        traceback.print_exc()
        flash('騎手情報の取得中にエラーが発まし。', 'error')
        return redirect(url_for('jockeys'))

def create_entry(race, entry_data):
    try:
        # デバ報追加
        print(f"Creating entry for race:")
        print(f"Race ID: {race.id}")
        print(f"Race Name: {race.name}")
        print(f"Race Date: {race.date}")
        print(f"Race Venue: {race.venue}")
        print(f"Entry Data: {entry_data}")
        
        # 既存のエトリーをチェク
        existing_entries = (Entry.query
                          .join(Race)
                          .filter(
                              Race.date == race.date,
                              Race.venue == race.venue,
                              Race.start_time == race.start_time,
                              Race.name == race.name
                          )
                          .all())
        
        if existing_entries:
            print(f"Warning: Found existing entries for this race combination")
            return None
        
        # 着順を値に変換（失格、中止などの場合はNoneを設定）
        try:
            result = int(entry_data['順'])
        except (ValueError, TypeError):
            result = None
        
        # 馬体と増減を分離
        weight_str = entry_data.get('馬体重', '')
        if weight_str and '(' in weight_str:
            horse_weight = int(weight_str.split('(')[0])
            weight_change = int(weight_str.split('(')[1].rstrip(')'))
        else:
            horse_weight = None
            weight_change = None
        
        # ッズを数
        try:
            odds = float(entry_data.get('単勝', 0))
        except (ValueError, TypeError):
            odds = None
        
        # 上りを数値に変換
        try:
            last3f = float(entry_data.get('上り', 0))
        except (ValueError, TypeError):
            last3f = None
            
        # 騎情報取得
        jockey = get_or_create_jockey(entry_data) if '' in entry_data else None
        jockey_id = jockey.id if jockey else None
        
        # 馬情報を得
        horse = get_or_create_horse(entry_data)
        
        horse_number = int(entry_data.get('番', 0))
        entry_dict = {
            'id': Entry.generate_entry_id(race.id, horse_number),  # 新しいID生成
            'race_id': race.id,
            'horse_id': horse.id,
            'horse_number': horse_number,
            'jockey_id': jockey.id if jockey else None,
            'number': int(entry_data.get('馬番', 0)),
            'frame': int(entry_data.get('枠番', 0)),
            'weight': float(entry_data.get('斤量', 0)),
            'odds': odds,
            'popularity': int(entry_data.get('人気', 0)) if entry_data.get('人気') else None,  # 余分な閉じカッを削除
            'result': result,
            'time': entry_data.get('タイム', ''),
            'margin': entry_data.get('着差', ''),
            'passing': entry_data.get('通過', ''),
            'last3f': last3f,
            'horse_weight': horse_weight,
            'weight_change': weight_change
        }
        
        entry = Entry(**entry_dict)
        db.session.add(entry)
        return entry
    except Exception as e:
        current_app.logger.warning(f"ントリーの処理中にエラーが発生しました: {str(e)}")
        current_app.logger.warning(f"問題のデータ: {entry_data}")
        return None

@app.route('/shutuba')
def shutuba_list():
    try:
        # 日付の取得（races関数と同じロジック）
        selected_date = request.args.get('date')
        if selected_date:
            try:
                target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            except ValueError:
                target_date = datetime.now().date()
        else:
            target_date = datetime.now().date()

        # 出馬表があるレースのみを取得
        races = Race.query\
            .join(ShutubaEntry)\
            .filter(func.date(Race.date) == target_date)\
            .group_by(Race.id)\
            .order_by(Race.venue_id, Race.race_number)\
            .all()

        # 利用可能な日付リストを取得（出馬表があるもののみ）
        available_dates = db.session.query(distinct(Race.date))\
            .join(ShutubaEntry)\
            .order_by(Race.date.desc())\
            .all()

        # 日付リストを整形
        dates = []
        for (date,) in available_dates:
            if isinstance(date, datetime):
                date = date.date()
            dates.append({
                'value': date.strftime('%Y-%m-%d'),
                'month': date.month,
                'day': date.day,
                'weekday': ['月', '火', '水', '木', '金', '土', '日'][date.weekday()]
            })

        # 会場ごとにレースをグループ化
        venue_races = {}
        for race in races:
            venue_id = str(race.venue_id)
            if venue_id not in venue_races:
                venue_races[venue_id] = {
                    'venue_name': VENUE_NAMES.get(venue_id, '不明'),
                    'weather': race.weather,
                    'track_condition': race.track_condition,
                    'races': []
                }
            venue_races[venue_id]['races'].append(race)

        return render_template('shutuba_list.html',
                            dates=dates,
                            date=target_date,
                            selected_date=selected_date,
                            venue_races=venue_races)

    except Exception as e:
        app.logger.error(f"Error in shutuba_list: {str(e)}")
        return render_template('shutuba_list.html',
                            dates=[],
                            date=datetime.now().date(),
                            venue_races={})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # userにIDを割り当てる
        
        # ユーザー設定を作成
        user_settings = UserSettings(user_id=user.id)
        db.session.add(user_settings)
        
        db.session.commit()
        flash('登録完しました')
        return redirect(url_for('login'))
    return render_template('register.html', title='新規登録', form=form)

@app.route('/api/points/add', methods=['POST'])
@login_required
def add_points():
    try:
        points = int(request.json.get('points', 0))
        reason = request.json.get('reason', '')
        
        if points <= 0:
            return jsonify({'success': False, 'message': '無効なポイント数です'}), 400
            
        current_user.add_points(points, reason)
        
        return jsonify({
            'success': True,
            'new_balance': current_user.point_balance,
            'message': f'{points}ポイントを加しました'
        })
        
    except Exception as e:
        app.logger.error(f"Point addition error: {str(e)}")
        return jsonify({'success': False, 'message': 'ポイントの追加失敗しまし'}), 500

@app.route('/api/points/use', methods=['POST'])
@login_required
def use_points():
    try:
        points = int(request.json.get('points', 0))
        
        if points <= 0:
            return jsonify({'success': False, 'message': '無効なポイント数です'}), 400
            
        if not current_user.has_enough_points(points):
            return jsonify({'success': False, 'message': 'ポイントが不足しています'}), 400
            
        if current_user.use_points(points):
            return jsonify({
                'success': True,
                'new_balance': current_user.point_balance,
                'message': f'{points}ポイントを用しました'
            })
        
        return jsonify({'success': False, 'message': 'ポイントの使用に失敗しました'}), 400
        
    except Exception as e:
        app.logger.error(f"Point usage error: {str(e)}")
        return jsonify({'success': False, 'message': 'ポイントの使用に失敗しました'}), 500

@app.route('/api/points/balance', methods=['GET'])
@login_required
def get_point_balance():
    try:
        return jsonify({
            'success': True,
            'balance': current_user.point_balance
        })
    except Exception as e:
        app.logger.error(f"Point balance check error: {str(e)}")
        return jsonify({'success': False, 'message': 'ポイント残高の取得に失敗しまし'}), 500

@app.route('/toggle_favorite/<int:horse_id>', methods=['POST'])
def toggle_favorite(horse_id):
    """お気に入りの追加・削除"""
    # ログインチェック
    if not current_user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'ログインが必要です',
                'redirect': url_for('login', next=request.referrer)
            }), 401
        return redirect(url_for('login', next=request.referrer))

    try:
        app.logger.info(f"Toggle favorite request - User: {current_user.id}, Horse: {horse_id}")
        
        horse = Horse.query.get_or_404(horse_id)
        favorite = Favorite.query.filter_by(
            user_id=current_user.id,
            horse_id=horse_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            message = '馬をお気入りから削除しました'
            is_favorite = False
        else:
            favorite = Favorite(
                user_id=current_user.id,
                horse_id=horse_id
            )
            db.session.add(favorite)
            message = '馬をお気に入りに追加しました'
            is_favorite = True
            
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'success',
                'message': message,
                'is_favorite': is_favorite
            })
        return redirect(request.referrer or url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in toggle_favorite: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': 'お気にりの更新に失敗しました'
            }), 500
        return redirect(request.referrer or url_for('index'))

@app.route('/favorites')
@login_required
def favorites():
    try:
        favorite_horses = Horse.query\
            .join(Favorite)\
            .filter(Favorite.user_id == current_user.id)\
            .order_by(Horse.name)\
            .all()
        
        return render_template('favorites.html', 
                             favorites=favorite_horses,
                             favorite_horses=favorite_horses)
                            
    except Exception as e:
        app.logger.error(f"Error in favorites route: {str(e)}")
        return render_template('favorites.html', 
                             favorites=[],
                             favorite_horses=[],
                             error="お気に入情報の得中にエラーが発生しました。")

@app.route('/mypage/favorites')
@login_required
def mypage_favorites():
    """マイページのお気に入り馬覧"""
    try:
        page = request.args.get('page', 1, type=int)
        
        # デバッグ用のログ出力
        app.logger.info(f"Current user ID: {current_user.id}")
        
        # まずお気入りの数を確認
        favorite_count = Favorite.query.filter_by(user_id=current_user.id).count()
        app.logger.info(f"Favorite count: {favorite_count}")
        
        # お気に入り馬を取（クエリを分解して確認）
        favorites_query = Horse.query\
            .join(Favorite)\
            .filter(Favorite.user_id == current_user.id)\
            .order_by(Horse.name)
            
        # SQLクエをログ出力
        app.logger.info(f"SQL Query: {str(favorites_query)}")
        
        # 結果を取得しページネーション
        favorites = favorites_query.paginate(
            page=page,
            per_page=12,
            error_out=False
        )
        
        app.logger.info(f"Total favorites: {favorites.total}")
        
        return render_template('mypage/favorites.html',
                             favorites=favorites)
                             
    except Exception as e:
        app.logger.error(f"Error in mypage_favorites: {str(e)}")
        app.logger.error(traceback.format_exc())  # スタックトレースを出力
        flash('おに入り情報取得中にエラーが発生ました', 'error')
        return render_template('mypage/favorites.html',
                             favorites=[])

# プアム機能のメインージ
@app.route('/premium')
def premium():
    """プレミアムプランのトップページ"""
    return render_template('premium/index.html')

# プレミアム機能の詳細ページ
@app.route('/premium/features')
def premium_features():
    """プレアム機能の詳細ペー"""
    return render_template('premium/features.html')

# プレミアムの支払ページ
@app.route('/premium/payment', methods=['GET', 'POST'])
@login_required
def premium_payment():
    """プレミアム会員支払いペー"""
    return render_template('premium/payment.html')

# プレミアム登録完了ページ
@app.route('/premium/complete')
@login_required
def premium_complete():
    """プレミアム会員登録完了ページ"""
    return render_template('premium/complete.html')

# プレミアム会員登録処理
@app.route('/premium/subscribe', methods=['POST'])
@login_required
def premium_subscribe():
    """プレミアム会員への登録処理"""
    try:
        data = request.get_json()
        
        # 支払い実際にはStripeなの決済サービスを使用）
        payment_successful = process_payment(data)  # この関は実装が必要
        
        if payment_successful:
            # ユーザーのプレミアム状態を更新
            current_user.is_premium = True
            current_user.premium_expires_at = datetime.now() + timedelta(days=int(data['duration']))
            
            # 支払い履歴を記録
            payment_log = PaymentLog(
                user_id=current_user.id,
                amount=data['price'],
                plan_type=data['plan'],
                duration_days=data['duration']
            )
            db.session.add(payment_log)
            
            # 変更履歴を記録
            membership_change = MembershipChangeLog(
                user_id=current_user.id,
                changed_by=current_user.id,
                old_status='normal',
                new_status='premium',
                reason='ユーザーによる購入'
            )
            db.session.add(membership_change)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'プレミア会員が了しました'
            })
        else:
            return jsonify({
                'success': False,
                'message': '支払い処理に失敗しました'
            }), 400
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in premium subscription: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'エーが発生しました'
        }), 500

# デッグ用簡易ログイン
@app.route('/debug-login')
def debug_login():
    if app.debug:  # デバッグモーのみ
        user = User.query.first()  # 最初のユーーでログイン
        if user:
            login_user(user)
            flash('デバッグ用ログインしました。', 'success')
            return redirect(url_for('premium'))
    return redirect(url_for('index'))

# バッグの一時的なユーザークラス
class DebugUser(UserMixin):
    def __init__(self, user):
        self.user = user
        
    def get_id(self):
        return str(self.user.id)
        
    @property
    def is_authenticated(self):
        return True
        
    @property
    def is_active(self):
        return True

# ユーザーラッパークラス
class UserWrapper(UserMixin):
    def __init__(self, user):
        self.user = user
        
    def get_id(self):
        return str(self.user.id)
        
    @property
    def is_authenticated(self):
        return True
        
    @property
    def is_active(self):
        return True

    # 元のーザーモデの属性をプロキシ
    def __getattr__(self, attr):
        return getattr(self.user, attr)


@app.route('/debug/create-user')
def create_debug_user():
    if not app.debug:
        return redirect(url_for('index'))
        
    # デバッグユーザーが在するか確認
    debug_user = User.query.filter_by(email='debug@example.com').first()
    
    if not debug_user:
        # デバッグユーザーを作成
        debug_user = User(
            email='debug@example.com',
            username='debuguser',
            password_hash=generate_password_hash('debug123')
        )
        db.session.add(debug_user)
        try:
            db.session.commit()
            flash('バッグユーザーを作成しました', 'success')
        except Exception as e:
            db.session.rollback()
            flash('ーーザー作成失敗した', 'danger')
            return redirect(url_for('index'))
    
    # UserWrapperでラップしてログン
    user_wrapper = UserWrapper(debug_user)
    if login_user(user_wrapper, force=True):
        flash('デバッグユーザーでグインしまた', 'info')
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
    else:
        flash('ログインに失敗しました', 'danger')
    
    return redirect(url_for('index'))

@app.route('/debug/db-check')
def debug_db_check():
    try:
        # レース数を認
        race_count = Race.query.count()
        
        # 馬の数を確認
        horse_count = Horse.query.count()
        
        # 最のレースを確認
        latest_race = Race.query.order_by(Race.date.desc()).first()
        
        # いくつかの馬を取得
        some_horses = Horse.query.limit(5).all()
        
        return jsonify({
            'status': 'success',
            'counts': {
                'races': race_count,
                'horses': horse_count
            },
            'latest_race': {
                'id': latest_race.id if latest_race else None,
                'name': latest_race.name if latest_race else None,
                'date': str(latest_race.date) if latest_race else None
            },
            'sample_horses': [
                {'id': h.id, 'name': h.name} for h in some_horses
            ]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        })

# 回顧ノート関連のルート
@app.route('/races/<int:race_id>/review', methods=['GET', 'POST'])
@login_required
def race_review(race_id):
    race = Race.query.get_or_404(race_id)
    review = RaceReview.query.filter_by(user_id=current_user.id, race_id=race_id).first()
    
    if request.method == 'POST':
        try:
            # フォームからデータを取得
            content = request.form.get('content', '')
            summary = request.form.get('summary', '')
            is_premium = 'is_premium' in request.form
            price = int(request.form.get('price', 0)) if is_premium else 0
            
            # デバッグログを追加
            current_app.logger.info(f"Saving review for race {race_id}: content={content[:20]}..., summary={summary}, premium={is_premium}, price={price}")
            
            if review:
                # 既存のレビューを更新
                review.content = content
                review.summary = summary
                review.is_premium = is_premium
                review.price = price
                review.updated_at = datetime.utcnow()
                db.session.commit()
                flash('レビューを更新しました', 'success')
            else:
                # 新しいレビューを作成
                new_review = RaceReview(
                    user_id=current_user.id,
                    race_id=race_id,
                    content=content,
                    summary=summary,
                    is_premium=is_premium,
                    price=price
                )
                db.session.add(new_review)
                db.session.commit()
                flash('レビューを保存しました', 'success')
            
            return redirect(url_for('race', race_id=race_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving review: {str(e)}")
            current_app.logger.error(traceback.format_exc())
            flash('レビューの保存中にエラーが発生しました', 'danger')
    
    return render_template('race_review.html', race=race, review=review)

@app.route('/races/<int:race_id>/reviews')
def race_reviews(race_id):
    race = Race.query.get_or_404(race_id)
    reviews = RaceReview.query.filter_by(race_id=race_id).order_by(RaceReview.created_at.desc()).all()
    return render_template('race_reviews.html', race=race, reviews=reviews)

@app.route('/reviews', methods=['GET'])
def all_reviews():
    # 検索エリの取
    search_query = request.args.get('search', '')
    
    # ベースクエリの作成
    query = RaceReview.query.join(Race)
    
    # 検索条件の適用
    if search_query:
        query = query.filter(Race.name.like(f'%{search_query}%'))
    
    # 日順に並び替え
    reviews = query.order_by(RaceReview.created_at.desc()).all()
    
    return render_template('all_reviews.html', reviews=reviews, search_query=search_query)

@app.route('/races/<int:race_id>/memo/<int:memo_id>/delete', methods=['POST'])
@login_required
def delete_race_memo(race_id, memo_id):
    try:
        memo = RaceMemo.query.get_or_404(memo_id)
        
        # 権限チェック
        if memo.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'このメモを削除する権限がありません'}), 403
        
        db.session.delete(memo)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'メモを削除しました'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting race memo: {str(e)}")
        return jsonify({'status': 'error', 'message': 'メモの削除中にエラーが発生しました'}), 500

@app.route('/mypage')
@login_required
def mypage_home():
    try:
        # レースメモを取得（最新5件）
        race_memos = db.session.query(RaceMemo, Race)\
            .join(Race, RaceMemo.race_id == Race.id)\
            .filter(RaceMemo.user_id == current_user.id)\
            .order_by(RaceMemo.created_at.desc())\
            .limit(5)\
            .all()

        # 馬メモを取得（最新5件）
        horse_memos = db.session.query(Horse)\
            .filter(Horse.memo.isnot(None))\
            .order_by(Horse.updated_at.desc())\
            .limit(5)\
            .all()

        # 馬メモのJSONをパース
        for horse in horse_memos:
            if horse.memo:
                try:
                    memos = json.loads(horse.memo)
                    # 最新のメモ内容を取得
                    if memos and isinstance(memos, list) and len(memos) > 0:
                        horse.memo = memos[-1].get('content', '')
                except json.JSONDecodeError:
                    horse.memo = ''

        # 通知を取得
        notifications = Notification.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Notification.created_at.desc())\
            .limit(5)\
            .all()

        app.logger.info(f"Found {len(race_memos)} race memos and {len(horse_memos)} horse memos for user {current_user.id}")

        return render_template('mypage/index.html',
                            notifications=notifications,
                            race_memos=race_memos,
                            horse_memos=horse_memos)

    except Exception as e:
        app.logger.error(f"Error in mypage_home: {str(e)}")
        flash('データの取得中にエラーが発生しました', 'error')
        return render_template('mypage/index.html',
                            notifications=[],
                            race_memos=[],
                            horse_memos=[])

@app.route('/mypage/reviews')
@login_required
def mypage_reviews():
    """自分の回顧ノート一覧"""
    page = request.args.get('page', 1, type=int)
    reviews = RaceReview.query\
        .filter_by(user_id=current_user.id)\
        .order_by(RaceReview.created_at.desc())\
        .paginate(page=page, per_page=10)
    return render_template('mypage/reviews.html', reviews=reviews)

@app.route('/mypage/purchased-reviews')
@login_required
def mypage_purchased_reviews():
    """購入済みレビュー一覧を表示"""
    try:
        # 購入済みレビューを取得
        purchased_reviews = RaceReview.query\
            .join(ReviewPurchase)\
            .join(Race)\
            .filter(ReviewPurchase.user_id == current_user.id)\
            .options(
                db.joinedload(RaceReview.race),
                db.joinedload(RaceReview.user)
            )\
            .order_by(ReviewPurchase.purchased_at.desc())\
            .all()
            
        # 各レビューのURLを設定
        for review in purchased_reviews:
            review.view_url = url_for('view_review',
                                    race_id=review.race_id,
                                    review_id=review.id)
        
        return render_template('mypage/purchased_reviews.html',
                             reviews=purchased_reviews)
                             
    except Exception as e:
        app.logger.error(f"Error in mypage_purchased_reviews: {str(e)}")
        flash('購入済みレビューの取得中にエラーが発生しました', 'error')
        return render_template('mypage/purchased_reviews.html',
                             reviews=[])

@app.route('/mypage/review-sales')
@login_required
def mypage_review_sales():
    try:
        # 売上計のクリ
        sales_summary = db.session.query(
            RaceReview.id,
            RaceReview.title,
            Race.name.label('race_name'),
            Race.date.label('race_date'),
            func.count(ReviewPurchase.id).label('purchase_count'),
            func.sum(ReviewPurchase.price).label('total_sales'),  # price_paidをpriceに変
        ).join(
            ReviewPurchase, RaceReview.id == ReviewPurchase.review_id
        ).join(
            Race, RaceReview.race_id == Race.id
        ).filter(
            RaceReview.user_id == current_user.id
        ).group_by(
            RaceReview.id,
            RaceReview.title,
            Race.name,
            Race.date
        ).order_by(
            func.sum(ReviewPurchase.price).desc()  # price_paidをpriceに
        ).all()

        # 上を計算
        total_revenue = sum(sale.total_sales for sale in sales_summary)
        
        return render_template('mypage/review_sales.html',
                             sales_summary=sales_summary,
                             total_revenue=total_revenue)
                             
    except Exception as e:
        app.logger.error(f"Error in mypage_review_sales: {str(e)}")
        return render_template('mypage/review_sales.html',
                             sales_summary=[],
                             total_revenue=0,
                             error="売上情報取得中エラーが発生しました。")

# お気に入り解除API
@app.route('/api/favorites/<int:horse_id>', methods=['DELETE'])
@login_required
def remove_favorite(horse_id):
    """お気に入りか削除するAPI"""
    try:
        favorite = Favorite.query.filter_by(
            user_id=current_user.id,
            horse_id=horse_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': 'お気に入りら削除しました'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'おに入りが見つかりませ'
            }), 404
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing favorite: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'エラーが発生しました'
        }), 500


















@app.route('/mypage/settings', methods=['GET', 'POST'])
@login_required
def mypage_settings():
    if request.method == 'POST':
        try:
            # デバッグ出力を追加
            app.logger.info(f"Form data: {request.form}")
            app.logger.info(f"Files: {request.files}")

            # プロフィール画像の処理
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    try:
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        current_user.profile_image = url_for('static', filename=f'uploads/{filename}')
                        app.logger.info(f"Image saved: {filepath}")
                    except Exception as e:
                        app.logger.error(f"Error saving image: {str(e)}")

            # プロフィー情報の更新
            current_user.introduction = request.form.get('introduction', '')
            current_user.twitter = request.form.get('twitter', '')
            current_user.note = request.form.get('note', '')
            current_user.blog = request.form.get('blog', '')
            current_user.youtube = request.form.get('youtube', '')
            current_user.specialties = request.form.get('specialties', '')
            current_user.analysis_style = request.form.get('analysis_style', '')

            # 変更を確認
            app.logger.info(f"Updated user data: {current_user.__dict__}")

            db.session.add(current_user)  # 明示的にセッションに追加
            db.session.commit()
            app.logger.info("Database committed successfully")
            flash('プロールを更しました', 'success')
            
            # 更新後のデータを確認
            app.logger.info(f"Saved user data: {current_user.introduction}, {current_user.twitter}, {current_user.note}")
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error saving settings: {str(e)}")
            flash('設定の保存に失しました', 'error')
        
        return redirect(url_for('mypage_settings'))

    # GETリクエスト時のデータを確認
    app.logger.info(f"Current user data: {current_user.introduction}, {current_user.twitter}, {current_user.note}")
    return render_template('mypage/settings.html', 
                         title='設定',
                         user=current_user)


# プレミアム機能へのリダイレト
@app.route('/premium/redirect')
@custom_login_required
def premium_redirect():
    return redirect(url_for('premium_features'))  # 'premium'から'premium_features'に変更

# レミアム機能のクセスチェック
def premium_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_premium:
            flash('この機能はプレミアム会員専です', 'warning')
            return redirect(url_for('premium_features'))  # 'premium'から'premium_features'に変更
        return f(*args, **kwargs)
    return decorated_function

# レビュー関連のルートを加
@app.route('/races/<int:race_id>/review/create', methods=['GET', 'POST'])
@login_required
def create_review(race_id):
    """レビューの作成・編集"""
    race = Race.query.get_or_404(race_id)
    
    if request.method == 'POST':
        review = RaceReview(
            race_id=race_id,
            user_id=current_user.id,
            title=request.form['title'],
            pace_analysis=request.form['pace_analysis'],
            track_condition_note=request.form['track_condition_note'],
            race_flow=request.form['race_flow'],
            overall_impression=request.form['overall_impression'],
            winner_analysis=request.form['winner_analysis'],
            placed_horses_analysis=request.form['placed_horses_analysis'],
            notable_performances=request.form['notable_performances'],
            future_prospects=request.form['future_prospects'],
            is_public=request.form.get('is_public', type=bool),
            sale_status=request.form.get('sale_status', 'free'),
            price=request.form.get('price', type=int, default=0),
            description=request.form.get('description', '')
        )  # ここに閉じ括弧を追加
        db.session.add(review)
        db.session.commit()
        
        # 新規レビュー作成時に通知を作成
        Notification.create_new_review_notification(review)
        
        flash('レビューを作成しました', 'success')
        return redirect(url_for('view_review', race_id=race_id, review_id=review.id))
    
    return render_template('review/create.html', race=race)

@app.route('/races/<int:race_id>/review/<int:review_id>', methods=['GET'])
def view_review(race_id, review_id):
    """レビュー詳細を表示"""
    try:
        review = RaceReview.query.get_or_404(review_id)
        race = Race.query.options(joinedload(Race.entries)).get_or_404(race_id)
        
        # 購入済みかどうかをチェック
        is_purchased = False
        if current_user.is_authenticated:
            purchase = ReviewPurchase.query.filter_by(
                user_id=current_user.id,
                review_id=review_id
            ).first()
            is_purchased = purchase is not None
        
        # レース情報を取得
        race_entries = race.entries.order_by(Entry.position).all()
        
        return render_template('review/view.html', 
                             review=review, 
                             race=race,
                             race_entries=race_entries,
                             is_purchased=is_purchased)
    except Exception as e:
        app.logger.error(f"Error in view_review: {str(e)}")
        flash('レビューの表示に失敗しました', 'error')
        return redirect(url_for('index'))

@app.route('/reviews/<int:review_id>/purchase', methods=['GET', 'POST'])
@login_required
def purchase_review(review_id):
    review = RaceReview.query.get_or_404(review_id)
    
    # 自分のレビューは購入不要
    if review.user_id == current_user.id:
        return redirect(url_for('review_detail', review_id=review_id))
    
    # 既に購入済みかチェック
    existing_purchase = ReviewPurchase.query.filter_by(
        user_id=current_user.id,
        review_id=review_id,
        status='completed'
    ).first()
    
    if existing_purchase:
        return redirect(url_for('review_detail', review_id=review_id))
    
    if request.method == 'POST':
        # ポイント残高チェック
        if current_user.point_balance < review.price:
            flash('ポイント残高が不足しています。', 'danger')
            return redirect(url_for('mypage_points'))
        
        try:
            # ポイント引き落とし
            current_user.point_balance -= review.price
            
            # 購入記録作成
            purchase = ReviewPurchase(
                user_id=current_user.id,
                review_id=review_id,
                price=review.price,
                status='completed'
            )
            
            # 販売者にポイント付与（手数料10%）
            if review.user:
                seller_amount = int(review.price * 0.9)
                review.user.point_balance += seller_amount
                
                # ポイントログ記録
                seller_log = UserPointLog(
                    user_id=review.user_id,
                    amount=seller_amount,
                    description=f'レビュー販売: {review.race.name}',
                    transaction_type='sale'
                )
                db.session.add(seller_log)
            
            # 購入者のポイントログ
            buyer_log = UserPointLog(
                user_id=current_user.id,
                amount=-review.price,
                description=f'レビュー購入: {review.race.name}',
                transaction_type='purchase'
            )
            
            db.session.add(purchase)
            db.session.add(buyer_log)
            db.session.commit()
            
            flash('レビューを購入しました。', 'success')
            return redirect(url_for('review_detail', review_id=review_id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error purchasing review: {str(e)}")
            flash('購入処理中にエラーが発生しました。', 'danger')
    
    return render_template('purchase_review.html', review=review)

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Stripeからのwebhook処理"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
        
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            PaymentManager.confirm_payment(payment_intent.id)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/notifications')
@login_required
def view_all_notifications():
    try:
        notifications = Notification.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Notification.created_at.desc())\
            .all()
        
        # 未読の通知を既読にマーク
        for notification in notifications:
            if not notification.is_read:  # readをis_readに変更
                notification.is_read = True
        db.session.commit()
        
        return render_template('notifications.html', notifications=notifications)
        
    except Exception as e:
        app.logger.error(f"Error in view_all_notifications: {str(e)}")
        flash('通知の取得中にエラーが発生しました', 'error')
        return render_template('notifications.html', notifications=[])

@app.route('/notifications/unread-count')
@login_required
def unread_notifications_count():
    try:
        count = db.session.query(func.count(Notification.id))\
            .filter(
                Notification.user_id == current_user.id,
                Notification.read == False  # is_read -> read に変更
            ).scalar()
        
        return jsonify({'count': count or 0})
    except Exception as e:
        app.logger.error(f"Error in unread_notifications_count: {str(e)}")
        return jsonify({'count': 0})

@app.route('/reviews/market')
def review_market():
    try:
        # 有料レビューの一覧を取得
        premium_reviews = RaceReview.query.filter_by(is_premium=True).order_by(RaceReview.created_at.desc()).all()
        
        # 購入済みレビューのIDリスト（ログインしている場合のみ）
        purchased_review_ids = []
        if current_user.is_authenticated:
            # 直接クエリを実行して購入済みレビューのIDを取得
            purchases = ReviewPurchase.query.filter_by(user_id=current_user.id).all()
            purchased_review_ids = [purchase.review_id for purchase in purchases]
            
            # デバッグログを追加
            current_app.logger.info(f"User {current_user.id} has purchased reviews: {purchased_review_ids}")
        
        # レビューにsummary属性がない場合、contentから生成
        for review in premium_reviews:
            if not hasattr(review, 'summary') or not review.summary:
               
                review.overall_impression = ''
        
        return render_template('review_market.html', 
                              reviews=premium_reviews,
                              purchased_review_ids=purchased_review_ids)
    except Exception as e:
        current_app.logger.error(f"Error in review_market: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return render_template('error.html', 
                              error_message="レビュー一覧の取得中にエラーが発生しました。",
                              debug_info=str(e)), 500

@app.route('/mypage/charge-points', methods=['GET'])
@login_required
def charge_points():
    return render_template('mypage/charge_points.html',
                         stripe_public_key=current_app.config['STRIPE_PUBLIC_KEY'])

@app.route('/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    try:
        data = request.get_json()
        amount = data.get('amount', 500)  # デフォルト500円
        
        # 許可された金額かチェック
        allowed_amounts = [500, 1000, 3000, 5000]
        if amount not in allowed_amounts:
            return jsonify({'error': '不正な金額です'}), 400

        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='jpy',
            automatic_payment_methods={
                'enabled': True,
            },
            metadata={
                'user_id': current_user.id,
                'points': amount  # 1円=1ポイント
            }
        )
        
        return jsonify({
            'clientSecret': payment_intent.client_secret
        })
    except Exception as e:
        app.logger.error(f"Error creating payment intent: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/mypage/point-charge-complete')
@login_required
def point_charge_complete():
    """ポイントチャー完処理"""
    payment_intent_id = request.args.get('payment_intent')
    if not payment_intent_id:
        flash('決済情報が見つかりません。', 'error')
        return redirect(url_for('mypage_charge_points'))
    
    try:
        # Stripeら決済情報を取得
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            points = int(intent.metadata.get('points', 0))
            
            # ポイントを追加
            current_user.add_points(
                points,
                type='charge',
                reference_id=payment_intent_id,
                description=f'ポイントチャジ: {points}P'
            )
            
            flash(f'{points}ポイントがチャージされました！', 'success')
            return redirect(url_for('mypage'))
            
        else:
            flash('決済が完了していません。', 'error')
            return redirect(url_for('mypage_charge_points'))
            
    except Exception as e:
        app.logger.error(f"Error in point charge completion: {str(e)}")
        flash('エラーが発生しました。', 'error')
        return redirect(url_for('mypage_charge_points'))

@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except:
        return []

# 管理者権限チェック用デコレータ
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('管理権限が必要です。', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# 管画面のルート
@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        # 総ユーザー数
        total_users = User.query.count()
        
        # 登録馬数
        total_horses = Horse.query.count()
        
        # 総レビュー数
        total_reviews = RaceReview.query.count()
        
        # 最近の登録ユーザー（最新5件）
        recent_users = User.query\
            .order_by(User.created_at.desc())\
            .limit(5)\
            .all()
            
        # 最の売上（最新5件）- payment_dateを使用
        recent_sales = PaymentLog.query\
            .filter_by(status='completed')\
            .order_by(PaymentLog.payment_date.desc())\
            .limit(5)\
            .all()

        return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_horses=total_horses,
                           total_reviews=total_reviews,
                           recent_users=recent_users,
                           recent_sales=recent_sales)
                           
    except Exception as e:
        app.logger.error(f"Error in admin dashboard: {str(e)}")
        flash('ダッシボードの読み込みに失敗しました', 'danger')
        return redirect(url_for('index'))

# 補助関数
def calculate_monthly_premium_growth():
    """月間のプレミアム会員増加率を計算"""
    try:
        last_month = datetime.now() - timedelta(days=30)
        new_premium_users = User.query\
            .filter(User.is_premium == True)\
            .filter(User.premium_since >= last_month)\
            .count()
        return new_premium_users
    except Exception as e:
        app.logger.error(f"Error calculating premium growth: {str(e)}")
        return 0

def get_disk_usage():
    """システムのディスク使用状況を取得"""
    try:
        total, used, free = shutil.disk_usage("/")
        return {
            'total': total // (2**30),  # GB
            'used': used // (2**30),
            'free': free // (2**30)
        }
    except Exception as e:
        app.logger.error(f"Error getting disk usage: {str(e)}")
        return {'total': 0, 'used': 0, 'free': 0}

def get_memory_usage():
    """システムのメモリ使用状況を取得"""
    try:
        process = psutil.Process()
        return {
            'memory_percent': process.memory_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024
        }
    except Exception as e:
        app.logger.error(f"Error getting memory usage: {str(e)}")
        return {'memory_percent': 0, 'memory_mb': 0}

def get_recent_errors():
    """最近のラーログを取得"""
    try:
        # ログファイルから最新のエラーを取得する実装
        # この実装は環境に応じて調整が必要
        return []
    except Exception as e:
        app.logger.error(f"Error getting recent errors: {str(e)}")
        return []

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """ユーザー管理画面"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        
        query = User.query
        
        # 検索フィルター
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
            
        # ページネーション
        pagination = query.order_by(User.created_at.desc()).paginate(
            page=page,
            per_page=20,
            error_out=False
        )
        
        return render_template('admin/users.html',
                           users=pagination.items,
                           pagination=pagination)
                           
    except Exception as e:
        app.logger.error(f"Error in admin users: {str(e)}")
        flash('ユーザー一覧の読み込み中にエラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/races')
@login_required
@admin_required
def admin_races():
    try:
        page = request.args.get('page', 1, type=int)
        date_str = request.args.get('date')
        
        # クエリの構築
        query = Race.query
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                # start_timeではなくdateカラムでフィルタリング
                query = query.filter(Race.date == target_date)
            except ValueError:
                flash('無効な日付形式です', 'error')
                return redirect(url_for('admin.races'))
        
        # ページネーション
        pagination = query.order_by(Race.date.desc(), Race.race_number.asc()).paginate(
            page=page, per_page=20, error_out=False)
        
        return render_template('admin/races.html',
                          races=pagination.items,
                          pagination=pagination,
                          selected_date=date_str,
                          VENUE_NAMES=VENUE_NAMES)
                        
    except Exception as e:
        current_app.logger.error(f"Error in admin races: {str(e)}")
        flash('レース一覧の読み込み中にエラーが発生しました', 'error')
        return redirect(url_for('admin.dashboard'))

@app.route('/admin/races/add', methods=['POST'])
@login_required
@admin_required
def admin_add_race():
    """レースの新規登録"""
    try:
        # 日付の処理を修正
        race_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        
        race = Race(
            date=race_date,
            venue_id=int(request.form['venue_id']),
            race_number=int(request.form['race_number']),
            name=request.form['name'],
            grade=request.form['grade'] or None,
            weather=request.form['weather'],
            track_condition=request.form['track_condition']
        )
        
        db.session.add(race)
        db.session.commit()
        
        flash('レースを登録しました', 'success')
        return redirect(url_for('admin.races', date=request.form['date']))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding race: {str(e)}")
        flash('レースの登録中にエラーが発生しました', 'error')
        return redirect(url_for('admin.races'))

@app.route('/admin/races/<int:race_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_race_delete(race_id):
    """レース削除"""
    try:
        race = Race.query.get_or_404(race_id)
        date_str = race.date.strftime('%Y-%m-%d')
        
        # 関連するレビューとメモを削除
        RaceReview.query.filter_by(race_id=race_id).delete()
        RaceMemo.query.filter_by(race_id=race_id).delete()
        
        db.session.delete(race)
        db.session.commit()
        
        flash('レースを削除しました', 'success')
        return redirect(url_for('admin_races', date=date_str))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting race: {str(e)}")
        flash('レースの除中にエラーが発生しました', 'error')
        return redirect(url_for('admin_races'))

@app.route('/admin/horses')
@login_required
@admin_required
def admin_horses():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20  # 1ページあたりの表示件数
        
        pagination = Horse.query\
            .order_by(Horse.id.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
            
        return render_template('admin/horses.html', 
                             horses=pagination.items,
                             pagination=pagination)
    except Exception as e:
        app.logger.error(f"Error in admin horses: {str(e)}")
        flash('馬一覧の読み込み中にエラーが発生しました', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/horses/add', methods=['POST'])
@login_required
@admin_required
def admin_add_horse():
    """馬の新規登録"""
    try:
        horse = Horse(
            name=request.form['name'],
            sex=request.form['sex'],
            birthday=datetime.strptime(request.form['birthday'], '%Y-%m-%d'),
            father=request.form['father'],
            mother=request.form['mother']
        )
        
        db.session.add(horse)
        db.session.commit()
        
        flash('馬を登録しました', 'success')
        return redirect(url_for('admin_horses'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding horse: {str(e)}")
        flash('馬の登中にエラーが発生しました', 'error')
        return redirect(url_for('admin_horses'))

@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """ユーザーの管理者権限をり替える"""
    user = User.query.get_or_404(user_id)
    
    # 自分自身の権限変更できない
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': '自分自身の権限は変更できません'}), 400
    
    data = request.get_json()
    user.is_admin = data.get('is_admin', False)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/admin/users/<int:user_id>/update-points', methods=['POST'])
@login_required
@admin_required
def update_user_points(user_id):
    """ユーザーのポイントを更新する"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    try:
        points = int(data.get('points', 0))
        reason = data.get('reason', '管理者によるポイント付与')
        
        if points < 0:
            return jsonify({'success': False, 'message': 'ポイントは0以上である必要があります'}), 400
            
        # ポント履歴を記録
        point_history = UserPoint(
            user_id=user.id,
            amount=points,  # point_amount → amount に修正
            type='admin_add',  # transaction_type → type に修正
            description=reason
        )
        
        # ユーザーのポイントを更新（既存のポイントに加算）
        user.point_balance += points
        
        db.session.add(point_history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{points}ポイントを追加しました',
            'new_balance': user.point_balance
        })
    except ValueError:
        return jsonify({'success': False, 'message': '不正な値です'}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating points: {str(e)}")
        return jsonify({'success': False, 'message': 'ポイントの更新に失敗しました'}), 500

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """ユーザのアカウントステータスを切り替える"""
    user = User.query.get_or_404(user_id)
    
    # 自分自身のステータスは変更できない
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': '自分自身のテータスは変更できません'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/admin/users/search')
@login_required
@admin_required
def search_users():
    """ユーザーの検索・フィタリング"""
    keyword = request.args.get('keyword', '')
    membership = request.args.get('membership', '')
    status = request.args.get('status', '')
    
    query = User.query
    
    if keyword:
        query = query.filter(or_(
            User.username.ilike(f'%{keyword}%'),
            User.email.ilike(f'%{keyword}%')
        ))
    
    if membership:
        if membership == 'premium':
            query = query.filter(User.is_premium == True)
        elif membership == 'normal':
            query = query.filter(User.is_premium == False)
    
    if status:
        if status == 'active':
            query = query.filter(User.is_active == True)
        elif status == 'inactive':
            query = query.filter(User.is_active == False)
    
    users = query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])

@app.route('/admin/users/<int:user_id>/detail')
@login_required
@admin_required
def admin_user_detail(user_id):
    """管理者用ーザー詳細ペジ"""
    try:
        user = User.query.get_or_404(user_id)
        
        # UserPoint → UserPointLogに変更
        point_history = UserPointLog.query\
            .filter_by(user_id=user.id)\
            .order_by(UserPointLog.created_at.desc())\
            .all()
        
        # ビュー購入履歴を取得
        review_purchases = ReviewPurchase.query\
            .filter_by(user_id=user.id)\
            .all()  # 並び順の指定一時的に削除
            
        login_history = LoginHistory.query\
            .filter_by(user_id=user.id)\
            .order_by(LoginHistory.login_at.desc())\
            .limit(10)\
            .all()
        
        return render_template('admin/user_detail.html',
                             user=user,
                             point_history=point_history,
                             review_purchases=review_purchases,
                             login_history=login_history)
                             
    except Exception as e:
        app.logger.error(f"Error in admin_user_detail: {str(e)}")
        flash('ユーザー情報取得中にエラーが発生しした。', 'error')
        return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/support-history')
@login_required
@admin_required
def get_support_history(user_id):
    """サポート履を取得"""
    history = SupportTicket.query.filter_by(user_id=user_id).order_by(SupportTicket.created_at.desc()).all()
    return jsonify([ticket.to_dict() for ticket in history])

@app.route('/admin/users/<int:user_id>/support-ticket', methods=['POST'])
@login_required
@admin_required
def create_support_ticket(user_id):
    """ポートチケを作成"""
    data = request.get_json()
    
    ticket = SupportTicket(
        user_id=user_id,
        title=data['title'],
        content=data['content'],
        status=data['status'],
        priority=data['priority'],
        created_by=current_user.id
    )
    
    db.session.add(ticket)
    db.session.commit()
    
    return jsonify({'success': True, 'ticket': ticket.to_dict()})

@app.route('/admin/users/<int:user_id>/send-notification', methods=['POST'])
@login_required
@admin_required
def send_user_notification(user_id):
    """ユザーに通知を送信"""
    data = request.get_json()
    
    notification = Notification(
        user_id=user_id,
        title=data['title'],
        message=data['message'],
        priority=data['priority'],
        created_by=current_user.id
    )
    
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/admin/users/<int:user_id>/toggle-premium', methods=['POST'])
@login_required
@admin_required
def toggle_premium_status(user_id):
    try:
        user = User.query.get_or_404(user_id)
        is_activating = not user.is_premium
        
        # プレアムステータスを切り替え
        user.is_premium = not user.is_premium
        if user.is_premium:
            user.premium_expires_at = datetime.now() + timedelta(days=30)  # 30日間有効
        else:
            user.premium_expires_at = None
            
        # 変更履歴を記
        log = MembershipChangeLog(
            user_id=user.id,
            changed_by=current_user.id,
            old_status='normal' if is_activating else 'premium',
            new_status='premium' if is_activating else 'normal',
            expires_at=user.premium_expires_at
        )
        db.session.add(log)
        
        # 通知を作成
        Notification.create_premium_notification(user, is_activating)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'プレミアムステータスを{"有効" if user.is_premium else "無効"}にしました。'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error toggling premium status: {str(e)}')
        return jsonify({
            'success': False,
            'message': 'エラが発生しました。'
        }), 500

@app.route('/admin/review-purchases')
@login_required
@admin_required
def admin_review_purchases():
    try:
        purchases = ReviewPurchase.query\
            .join(User)\
            .join(RaceReview)\
            .order_by(ReviewPurchase.created_at.desc())\
            .all()
            
        return render_template('admin/review_purchases.html', 
                             purchases=purchases)
                             
    except Exception as e:
        app.logger.error(f"Error in admin_review_purchases: {str(e)}")
        return render_template('admin/review_purchases.html', 
                             purchases=[],
                             error="購入履の取得中にエラーが発生しました。")

@app.route('/mypage/point-history')
@login_required
def mypage_point_history():
    """ポイント履歴を表示"""
    try:
        # UserPoint → UserPointLogに変更
        point_history = UserPointLog.query\
            .filter_by(user_id=current_user.id)\
            .order_by(UserPointLog.created_at.desc())\
            .all()
        
        return render_template('mypage/point_history.html',
                           point_history=point_history)
                             
    except Exception as e:
        app.logger.error(f"Error in point history: {str(e)}")
        flash('履歴の取得中にエラーが発生ました。', 'error')
        return redirect(url_for('mypage_home'))

# お気に入り機能の追加
@app.route('/api/favorites/toggle/<int:horse_id>', methods=['POST'])
@login_required
def api_toggle_favorite(horse_id):
    """お気に入API用エンドポイント"""
    try:
        app.logger.info(f"API Toggle favorite request - User: {current_user.id}, Horse: {horse_id}")
        
        horse = Horse.query.get_or_404(horse_id)
        favorite = Favorite.query.filter_by(
            user_id=current_user.id,
            horse_id=horse_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            message = '馬をお気に入りから削除ました'
            is_favorite = False
        else:
            favorite = Favorite(
                user_id=current_user.id,
                horse_id=horse_id
            )
            db.session.add(favorite)
            message = 'をお気に入に追加しました'
            is_favorite = True
            
        db.session.commit()
        app.logger.info(f"Successfully {message}")
        
        return jsonify({
            'status': 'success',
            'message': message,
            'is_favorite': is_favorite
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in api_toggle_favorite: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'お気に入りの新に失敗しました'
        }), 500

# おに入り一覧の取得API
@app.route('/api/favorites/list')
@login_required
def api_get_favorites():
    """お気に入り一覧を取得するAPI"""
    try:
        favorites = Horse.query\
            .join(Favorite)\
            .filter(Favorite.user_id == current_user.id)\
            .order_by(Horse.name)\
            .all()
            
        return jsonify({
            'status': 'success',
            'favorites': [{
                'id': horse.id,
                'name': horse.name,
                'sex': horse.sex,
                'memo': horse.memo
            } for horse in favorites]
        })
    except Exception as e:
        app.logger.error(f"Error in api_get_favorites: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'お気に入り一覧の取得に失敗しまし'
        }), 500

@app.route('/admin/users/<int:user_id>/add-points', methods=['POST'])
@login_required
@admin_required
def admin_add_points(user_id):
    """管理者がユーザーのポイントを追加する"""
    # 管理者チェック手動で行う
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '権限があません'}), 403
        
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    try:
        points = int(data.get('points', 0))
        if points < 0:
            return jsonify({'success': False, 'message': 'ポイントは0以上である必要があります'}), 400
            
        # UserPoint → UserPointLogに変更
        point_log = UserPointLog(
            user_id=user.id,
            points=points,
            action_type='admin_add',
            description='管理者によるポイント付与'
        )
        
        user.point_balance += points
        
        db.session.add(point_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{points}ポイントを追加しました',
            'new_balance': user.point_balance
        })
        
    except ValueError:
        return jsonify({'success': False, 'message': '不正な値です'}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding points: {str(e)}")
        return jsonify({'success': False, 'message': 'ポイントの追加に失敗しました'}), 500

@app.route('/races/<int:race_id>/review/<int:review_id>/purchase', methods=['GET', 'POST'])
@login_required
def review_purchase(race_id, review_id):
    """レビューを購入する"""
    try:
        review = RaceReview.query.get_or_404(review_id)
        
        # GETリクエストの場合は、購入確認ページを表示
        if request.method == 'GET':
            suggested_amounts = [
                max(1000, review.price - current_user.point_balance),
                max(2000, review.price - current_user.point_balance),
                max(5000, review.price - current_user.point_balance)
            ]
            return render_template('review/purchase.html', 
                                review=review,
                                stripe_public_key=current_app.config['STRIPE_PUBLIC_KEY'],
                                suggested_amounts=suggested_amounts)
        
        # 既に購入済みかチェック
        existing_purchase = ReviewPurchase.query.filter_by(
            user_id=current_user.id,
            review_id=review_id
        ).first()
        
        if existing_purchase:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '既に購入済みのレビューです'})
            flash('既に購入済みのレビューです', 'warning')
            return redirect(url_for('view_review', race_id=race_id, review_id=review_id))
        
        # ポイント残高が十分な場合は直接購入
        if current_user.point_balance >= review.price:
            purchase = ReviewPurchase(
                user_id=current_user.id,
                review_id=review_id,
                price=review.price
            )
            
            current_user.point_balance -= review.price
            
            # ポイント履歴を記録
            current_user.add_points(
                -review.price,
                type='review_purchase',
                reference_id=review_id,
                description=f'レビュー購入: {review.title}'
            )
            
            db.session.add(purchase)
            db.session.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'レビュー購入しました',
                    'redirect_url': url_for('view_review', race_id=race_id, review_id=review_id)
                })
            
            flash('レビューを購入しました', 'success')
            return redirect(url_for('view_review', race_id=race_id, review_id=review_id))
            
        # ポイント不足の場合は購入確認ページを表示（非Ajax時）
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return redirect(url_for('review_purchase', race_id=race_id, review_id=review_id))
            
        # Ajaxクストの場合エラーレスポンスを返す
        return jsonify({
            'success': False,
            'message': 'ポイントが不足していす',
            'required_points': review.price - current_user.point_balance
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in review_purchase: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': '購入処理に失敗しました'})
        flash('購入処理に失敗しました', 'error')
        return redirect(url_for('review_market'))

@app.route('/review/<int:review_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_review(review_id):
    """回顧ノート編集"""
    review = RaceReview.query.get_or_404(review_id)
    
    # 作成者本人かチェック
    if review.user_id != current_user.id:
        flash('編集権限がありません', 'error')
        return redirect(url_for('mypage_reviews'))
    
    if request.method == 'POST':
        try:
            # フォームらデータを得して更新
            review.title = request.form.get('title')
            review.pace_analysis = request.form.get('pace_analysis')
            review.track_condition_note = request.form.get('track_condition_note')
            review.race_flow = request.form.get('race_flow')
            review.overall_impression = request.form.get('overall_impression')
            review.winner_analysis = request.form.get('winner_analysis')
            review.placed_horses_analysis = request.form.get('placed_horses_analysis')
            review.notable_performances = request.form.get('notable_performances')
            review.future_prospects = request.form.get('future_prospects')
            
            # 販売設定
            review.is_public = bool(request.form.get('is_public'))
            review.price = request.form.get('price', type=int)
            review.sale_status = request.form.get('sale_status')
            review.description = request.form.get('description')
            
            db.session.commit()
            flash('回顧ノートを更新しした', 'success')
            return redirect(url_for('view_review', race_id=review.race_id, review_id=review.id))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating review: {str(e)}")
            flash('更新中にエラー発生しました', 'error')
    
    return render_template('review/edit.html', review=review, title='回顧ノートの編集')

@app.route('/review/<int:review_id>/sales', methods=['GET'])
@login_required
def review_sales_detail(review_id):
    """回顧ノートの売詳細"""
    review = RaceReview.query.get_or_404(review_id)
    
    # 作成者本人かチェック
    if review.user_id != current_user.id:
        flash('閲覧権限がありません', 'error')
        return redirect(url_for('mypage_reviews'))
    
    # 購入履歴を得
    purchases = ReviewPurchase.query\
        .filter_by(review_id=review_id)\
        .order_by(ReviewPurchase.purchased_at.desc())\
        .all()
    
    return render_template('reviews/sales_detail.html', 
                         review=review,
                         purchases=purchases)

@app.route('/mypage/memos')
@login_required
def mypage_memos():
    try:
        # レースメモを取得（レース情報と一緒に）
        race_memos = db.session.query(RaceMemo, Race)\
            .join(Race, RaceMemo.race_id == Race.id)\
            .filter(RaceMemo.user_id == current_user.id)\
            .order_by(RaceMemo.created_at.desc())\
            .all()
            
        # 馬メモを取得（馬情報と一緒に）
        horse_memos = db.session.query(Horse)\
            .filter(Horse.memo.isnot(None))\
            .order_by(Horse.updated_at.desc())\
            .all()

        # 馬メモのJSONをパース
        for horse in horse_memos:
            if horse.memo:
                try:
                    memos = json.loads(horse.memo)
                    # 最新のメモ内容を取得
                    if memos and isinstance(memos, list) and len(memos) > 0:
                        horse.memo = memos[-1].get('content', '')
                except json.JSONDecodeError:
                    horse.memo = ''
            
        return render_template('mypage/memos.html',
                             race_memos=race_memos,
                             horse_memos=horse_memos)
                             
    except Exception as e:
        app.logger.error(f"Error in mypage_memos: {str(e)}")
        flash('メモの取得中にエラーが発生しました', 'error')
        return render_template('mypage/memos.html',
                             race_memos=[],
                             horse_memos=[])
# カスタムフィルターの定義
@app.template_filter('timeago')
def timeago_filter(date):
    """
    日付を「〜前」の形式に変換するフィルター
    例: 「3分前」「2時間前」「1日前」など
    """
    now = datetime.now()
    diff = now - date

    seconds = diff.total_seconds()
    if seconds < 60:
        return 'たった今'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes}分前'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}時間前'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days}日前'
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f'{weeks}週間前'
    else:
        return date.strftime('%Y/%m/%d')

@app.route('/start_trial', methods=['GET', 'POST'])
@login_required
def start_trial():
    if current_user.is_premium:
        flash('すにプレミアム会員です', 'info')
        return redirect(url_for('premium'))
        
    # トライアル開始のロジックを実装
    try:
        # ユーザー設定を更新
        user_settings = current_user.user_settings.first()
        if not user_settings:
            user_settings = UserSettings(user_id=current_user.id)
            db.session.add(user_settings)
        
        user_settings.is_trial = True
        user_settings.trial_start_date = datetime.utcnow()
        user_settings.trial_end_date = datetime.utcnow() + timedelta(days=7)
        
        db.session.commit()
        
        flash('トライアルが開始されました！', 'success')
        return redirect(url_for('premium'))
    except Exception as e:
        db.session.rollback()
        flash('トライアルの開始に失敗しました。', 'error')
        return redirect(url_for('premium'))

@app.route('/api/create-review-purchase-session', methods=['POST'])
@login_required
def create_review_purchase_session():
    """レビュー購入用のStripeセッションを作成"""
    try:
        data = request.get_json()
        amount = int(data.get('amount', 0))
        review_id = int(data.get('review_id', 0))
        
        review = RaceReview.query.get_or_404(review_id)
        
        # Stripe PaymentIntentを作成
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='jpy',
            metadata={
                'user_id': current_user.id,
                'review_id': review_id,
                'points': amount,  # 1円=1ポイント
                'type': 'review_purchase'
            }
        )
        
        return jsonify({
            'clientSecret': payment_intent.client_secret
        })
    except Exception as e:
        app.logger.error(f"Error creating review purchase session: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/review/purchase/complete')
@login_required
def review_purchase_complete():
    """レビュー購入完了処理"""
    payment_intent_id = request.args.get('payment_intent')
    review_id = request.args.get('review_id')
    
    if not payment_intent_id or not review_id:
        flash('決済情報が不完全です。', 'error')
        return redirect(url_for('review_market'))
    
    try:
        # Stripeから決済情報を取得
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            points = int(intent.metadata.get('points', 0))
            review = RaceReview.query.get_or_404(review_id)
            
            # ポントを追加
            current_user.add_points(
                points,
                type='charge',
                reference_id=payment_intent_id,
                description=f'ポイントチャー: {points}P'
            )
            
            # レビューを購入
            purchase = ReviewPurchase(
                user_id=current_user.id,
                review_id=review_id,
                price=review.price
            )
            
            current_user.point_balance -= review.price
            
            db.session.add(purchase)
            db.session.commit()
            
            flash(f'レビューを購入しました！', 'success')
            return redirect(url_for('view_review', race_id=review.race_id, review_id=review_id))
            
        else:
            flash('決済が完了していません。', 'error')
            return redirect(url_for('review_market'))
            
    except Exception as e:
        app.logger.error(f"Error in review purchase completion: {str(e)}")
        flash('ラーが発生しました。', 'error')
        return redirect(url_for('review_market'))

@app.route('/api/notifications/count', methods=['GET'])
@login_required
def get_notification_count():
    try:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({'count': count})
    except Exception as e:
        app.logger.error(f"Error in notification count: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/terms')
def terms():
    return render_template('legal/terms.html')

@app.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')

@app.route('/commercial-transactions')
def commercial_transactions():
    return render_template('legal/commercial_transactions.html')

# 新しい管理者用エントリー
@app.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    """基本的な分析ページ"""
    try:
        # 基本な統計情報のみ取得
        stats = {
            'total_users': User.query.count(),
            'total_reviews': RaceReview.query.count(),
            'total_horses': Horse.query.count()
        }
        
        return render_template('admin/analytics.html', stats=stats)
    except Exception as e:
        app.logger.error(f"Error in analytics: {str(e)}")
        flash('統計情報の取得中にエラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/system')
@login_required
@admin_required
def admin_system():
    """システム管理ペー"""
    try:
        system_info = {
            'disk': get_disk_usage(),
            'memory': get_memory_usage(),
            'cpu': get_cpu_usage(),
            'database': get_database_stats(),
            'cache': get_cache_stats(),
            'error_logs': get_recent_errors(limit=10)
        }
        
        return render_template('admin/system.html',
                             system_info=system_info)
    except Exception as e:
        app.logger.error(f"Error in system management: {str(e)}")
        flash('システム情報の取得中にエラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/content')
@login_required
@admin_required
def admin_content():
    """コンテンツ管理ページ"""
    try:
        reported_reviews = RaceReview.query.filter_by(is_reported=True).all()
        reported_comments = Comment.query.filter_by(is_reported=True).all()
        pending_reviews = RaceReview.query.filter_by(status='pending').all()
        
        return render_template('admin/content.html',
                             reported_reviews=reported_reviews,
                             reported_comments=reported_comments,
                             pending_reviews=pending_reviews)
    except Exception as e:
        app.logger.error(f"Error in content management: {str(e)}")
        flash('コンテンツ情報の取得中にエラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    """システム設定ページ"""
    if request.method == 'POST':
        try:
            # 設定の更新処理
            update_system_settings(request.form)
            flash('設定を更新しました', 'success')
        except Exception as e:
            app.logger.error(f"Error updating settings: {str(e)}")
            flash('設定の更新中にエラーが発生しました', 'error')
    
    settings = get_system_settings()
    return render_template('admin/settings.html', settings=settings)

# API エンドポイント
@app.route('/admin/api/user-stats')
@login_required
@admin_required
def api_user_stats():
    """ユーザー統計API"""
    try:
        period = request.args.get('period', 'monthly')
        stats = generate_user_stats(period)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/review-stats')
@login_required
@admin_required
def api_review_stats():
    """レビュー統計API"""
    try:
        period = request.args.get('period', 'monthly')
        stats = generate_review_stats(period)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    """レュー管理画面"""
    try:
        page = request.args.get('page', 1, type=int)
        status = request.args.get('status')
        
        query = RaceReview.query
        
        # ステータスによる絞り込み
        if status == 'public':
            query = query.filter_by(is_public=True)
        elif status == 'private':
            query = query.filter_by(is_public=False)
        elif status == 'reported':
            query = query.filter(RaceReview.reports.any())
        
        # ページネーション
        pagination = query.order_by(RaceReview.created_at.desc()).paginate(
            page=page,
            per_page=20,
            error_out=False
        )
        
        return render_template('admin/reviews.html',
                           reviews=pagination.items,
                           pagination=pagination)
                           
    except Exception as e:
        app.logger.error(f"Error in admin reviews: {str(e)}")
        flash('レビュー覧の読み込み中エラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/api/reviews/<int:review_id>')
@login_required
@admin_required
def admin_review_detail(review_id):
    """レビュー詳細API"""
    try:
        review = RaceReview.query.get_or_404(review_id)
        
        return jsonify({
            'race_name': review.race.name,
            'race_date': review.race.date.strftime('%Y/%m/%d'),
            'username': review.user.username,
            'rating': review.rating,
            'content': review.content,
            'reports': [{
                'reason': report.reason,
                'created_at': report.created_at.strftime('%Y/%m/%d %H:%M')
            } for report in review.reports]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reviews/<int:review_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_review_toggle(review_id):
    """レビューの公開/非公開切り替え"""
    try:
        review = RaceReview.query.get_or_404(review_id)
        review.is_public = not review.is_public
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/reviews/<int:review_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_review_delete(review_id):
    """レビュー削除"""
    try:
        review = RaceReview.query.get_or_404(review_id)
        
        # 購入履歴の削除
        ReviewPurchase.query.filter_by(review_id=review_id).delete()
        
        db.session.delete(review)
        db.session.commit()
        
        flash('レビューを削除しました', 'success')
        return redirect(url_for('admin_reviews'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting review: {str(e)}")
        flash('レビューの削除中にエラーが発生しました', 'error')
        return redirect(url_for('admin_reviews'))

@app.route('/admin/sales')
@login_required
@admin_required
def admin_sales():
    """売上/ポイント管理画面"""
    try:
        page = request.args.get('page', 1, type=int)
        type_filter = request.args.get('type')
        
        # 今月の日範囲
        today = datetime.now()
        this_month_start = datetime(today.year, today.month, 1)
        this_month_end = datetime(today.year, today.month, monthrange(today.year, today.month)[1], 23, 59, 59)
        
        # 先月の日付範囲
        last_month = today - timedelta(days=today.day)
        last_month_start = datetime(last_month.year, last_month.month, 1)
        last_month_end = datetime(last_month.year, last_month.month, monthrange(last_month.year, last_month.month)[1], 23, 59, 59)

        # 今月の売上集計
        monthly_sales = db.session.query(func.sum(PaymentLog.amount))\
            .filter(
                PaymentLog.status == 'completed',
                PaymentLog.created_at.between(this_month_start, this_month_end)
            ).scalar() or 0

        # 先月の売上集計
        last_month_sales = db.session.query(func.sum(PaymentLog.amount))\
            .filter(
                PaymentLog.status == 'completed',
                PaymentLog.created_at.between(last_month_start, last_month_end)
            ).scalar() or 0

        # 今月のポイント購入集計
        monthly_points = db.session.query(func.sum(PaymentLog.points))\
            .filter(
                PaymentLog.status == 'completed',
                PaymentLog.type == 'point',
                PaymentLog.created_at.between(this_month_start, this_month_end)
            ).scalar() or 0

        # 先月のポイント購入集計
        last_month_points = db.session.query(func.sum(PaymentLog.points))\
            .filter(
                PaymentLog.status == 'completed',
                PaymentLog.type == 'point',
                PaymentLog.created_at.between(last_month_start, last_month_end)
            ).scalar() or 0

        # 今月のレビュー購入数
        monthly_reviews = db.session.query(func.count(ReviewPurchase.id))\
            .filter(ReviewPurchase.created_at.between(this_month_start, this_month_end))\
            .scalar() or 0

        # 先月のレビュー購入数
        last_month_reviews = db.session.query(func.count(ReviewPurchase.id))\
            .filter(ReviewPurchase.created_at.between(last_month_start, last_month_end))\
            .scalar() or 0

        # 今月のプレミアム会員数
        monthly_premium = db.session.query(func.count(User.id))\
            .filter(
                User.is_premium == True,
                User.premium_expired_at > this_month_end
            ).scalar() or 0

        # 先月のプレミアム会員数
        last_month_premium = db.session.query(func.count(User.id))\
            .filter(
                User.is_premium == True,
                User.premium_expired_at > last_month_end
            ).scalar() or 0

        # 取引履歴のクエリ
        query = PaymentLog.query.join(User)
        
        if type_filter:
            query = query.filter(PaymentLog.type == type_filter)
        
        # ページネーション
        pagination = query.order_by(PaymentLog.created_at.desc()).paginate(
            page=page,
            per_page=20,
            error_out=False
        )
        
        return render_template('admin/sales.html',
                           monthly_sales=monthly_sales,
                           monthly_diff=monthly_sales - last_month_sales,
                           monthly_points=monthly_points,
                           monthly_points_diff=monthly_points - last_month_points,
                           monthly_reviews=monthly_reviews,
                           monthly_reviews_diff=monthly_reviews - last_month_reviews,
                           monthly_premium=monthly_premium,
                           monthly_premium_diff=monthly_premium - last_month_premium,
                           payment_logs=pagination.items,
                           pagination=pagination)
                           
    except Exception as e:
        app.logger.error(f"Error in admin sales: {str(e)}")
        flash('売上情報の読み込み中にエラーが発生しました', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/api/sales-stats')
@login_required
@admin_required
def admin_sales_stats():
    """売上統計API"""
    try:
        period = request.args.get('period', 'monthly')
        today = datetime.now()
        
        if period == 'daily':
            # 日次データ（過去30日）
            start_date = today - timedelta(days=29)
            date_trunc = func.date(PaymentLog.created_at)
            format_str = '%m/%d'
        elif period == 'monthly':
            # 月次データ（過去12ヶ月）
            start_date = datetime(today.year - 1, today.month, 1)
            date_trunc = func.date_trunc('month', PaymentLog.created_at)
            format_str = '%Y/%m'
        else:  # yearly
            # 年次データ（過去5年）
            start_date = datetime(today.year - 4, 1, 1)
            date_trunc = func.date_trunc('year', PaymentLog.created_at)
            format_str = '%Y'
        
        # 売上データの取得
        sales_data = db.session.query(
            date_trunc.label('date'),
            func.sum(PaymentLog.amount).label('amount')
        ).filter(
            PaymentLog.status == 'completed',
            PaymentLog.created_at >= start_date
        ).group_by('date').order_by('date').all()
        
        # データの整形
        labels = []
        sales = []
        
        for data in sales_data:
            labels.append(data.date.strftime(format_str))
            sales.append(float(data.amount))
        
        return jsonify({
            'labels': labels,
            'sales': sales
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/payment-logs/<int:log_id>')
@login_required
@admin_required
def admin_payment_log_detail(log_id):
    """取引詳細API"""
    try:
        log = PaymentLog.query.get_or_404(log_id)
        
        return jsonify({
            'id': log.id,
            'created_at': log.created_at.strftime('%Y/%m/%d %H:%M'),
            'username': log.user.username,
            'type_display': log.type_display,
            'amount': f"¥{log.amount:,}",
            'points': log.points,
            'status_display': log.status_display,
            'status_color': log.status_color,
            'payment_id': log.payment_id,
            'memo': log.memo
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# テンプレートフィルター
@app.template_filter('format_yen')
def format_yen(value):
    """金額を円表示にフーマット"""
    return f"¥{value:,}"

@app.template_filter('format_number')
def format_number(value):
    """数値をカンマ区切りにフォーマット"""
    return f"{value:,}"

@app.route('/races/<int:race_id>/shutuba')
def race_shutuba(race_id):
    try:
        # デバッグ情報を追加
        current_app.logger.info(f"Accessing shutuba for race_id: {race_id}")
        
        # レース情報を取得
        race = Race.query.get_or_404(race_id)
        
        # 出走表エントリーを別途取得
        entries = ShutubaEntry.query.options(
            joinedload(ShutubaEntry.horse),
            joinedload(ShutubaEntry.jockey)
        ).filter(ShutubaEntry.race_id == race_id).all()

        # 出走馬のIDリストを作成
        horse_ids = [entry.horse_id for entry in entries]

        # 各馬の最近の戦績を取得
        for entry in entries:
            # ShutubaEntryモデルのget_recent_resultsメソッドを使用
            recent_entries = entry.get_recent_results(limit=5)
            
            # 結果を整形
            formatted_results = []
            for recent_entry in recent_entries:
                race_data = recent_entry.race
                jockey_data = recent_entry.jockey
                
                formatted_results.append({
                    'date': race_data.date,
                    'venue': race_data.venue,
                    'name': race_data.name,
                    'position': recent_entry.position,
                    'popularity': recent_entry.popularity,
                    'jockey_name': jockey_data.name if jockey_data else '不明',
                    'weight_carry': getattr(recent_entry, 'weight', '-'),
                    'distance': race_data.distance,
                    'track_condition': race_data.track_condition or '不明',
                    'time': getattr(recent_entry, 'time', '-'),
                    'margin': getattr(recent_entry, 'margin', '-')
                })
            
            # エントリーに戦績を付与
            entry.recent_results = formatted_results
            
            # 同距離での成績を計算
            if race.distance:
                # 同距離のレース結果を取得
                distance_entries = Entry.query.join(Race).filter(
                    Entry.horse_id == entry.horse_id,
                    Entry.position.isnot(None),
                    Race.distance == race.distance
                ).all()
                
                if distance_entries:
                    total = len(distance_entries)
                    wins = sum(1 for e in distance_entries if e.position == 1)
                    top3 = sum(1 for e in distance_entries if e.position and e.position <= 3)
                    
                    entry.distance_stats = {
                        'total': total,
                        'wins': wins,
                        'win_rate': (wins / total) * 100 if total > 0 else 0,
                        'top3': top3,
                        'top3_rate': (top3 / total) * 100 if total > 0 else 0
                    }
                    
                    # 同距離での最速タイム
                    best_time_entry = None
                    best_time = float('inf')
                    
                    for e in distance_entries:
                        if hasattr(e, 'time') and e.time:
                            try:
                                # 時間を秒に変換して比較
                                time_parts = e.time.split(':')
                                if len(time_parts) == 2:
                                    minutes, seconds = time_parts
                                    total_seconds = float(minutes) * 60 + float(seconds)
                                    if total_seconds < best_time:
                                        best_time = total_seconds
                                        best_time_entry = e
                            except (ValueError, AttributeError):
                                pass
                    
                    if best_time_entry:
                        entry.best_time = {
                            'time': best_time_entry.time,
                            'date': best_time_entry.race.date,
                            'venue': best_time_entry.race.venue,
                            'track_condition': best_time_entry.race.track_condition or '不明'
                        }
                else:
                    entry.distance_stats = None
            else:
                entry.distance_stats = None
            
            # 月別成績を計算
            month_stats = {}
            
            # 全レース結果を取得
            all_entries = Entry.query.join(Race).filter(
                Entry.horse_id == entry.horse_id,
                Entry.position.isnot(None)
            ).all()
            
            for e in all_entries:
                race_date = e.race.date
                if isinstance(race_date, str):
                    try:
                        race_date = datetime.strptime(race_date, '%Y-%m-%d').date()
                    except ValueError:
                        continue
                
                month = race_date.month
                
                if month not in month_stats:
                    month_stats[month] = {'total': 0, 'wins': 0, 'top3': 0}
                
                month_stats[month]['total'] += 1
                
                if e.position == 1:
                    month_stats[month]['wins'] += 1
                
                if e.position and e.position <= 3:
                    month_stats[month]['top3'] += 1
            
            # 勝率と複勝率を計算
            for month, stats in month_stats.items():
                stats['win_rate'] = (stats['wins'] / stats['total']) * 100 if stats['total'] > 0 else 0
                stats['top3_rate'] = (stats['top3'] / stats['total']) * 100 if stats['total'] > 0 else 0
            
            entry.month_stats = month_stats

        # 会場名の辞書を定義
        VENUE_NAMES = {
            '東京': '東京競馬場',
            '中山': '中山競馬場',
            '阪神': '阪神競馬場',
            '京都': '京都競馬場',
            '中京': '中京競馬場',
            '小倉': '小倉競馬場',
            '福島': '福島競馬場',
            '新潟': '新潟競馬場',
            '札幌': '札幌競馬場',
            '函館': '函館競馬場',
            # 地方競馬場も追加
            '大井': '大井競馬場',
            '川崎': '川崎競馬場',
            '船橋': '船橋競馬場',
            '浦和': '浦和競馬場',
            '名古屋': '名古屋競馬場',
            '園田': '園田競馬場',
            '姫路': '姫路競馬場',
            '高知': '高知競馬場',
            '佐賀': '佐賀競馬場',
            '金沢': '金沢競馬場',
            '笠松': '笠松競馬場',
            '盛岡': '盛岡競馬場',
            '水沢': '水沢競馬場',
            '門別': '門別競馬場',
            '帯広': '帯広競馬場',
        }

        return render_template('shutuba.html',
                          race=race,
                          entries=entries,
                          venue_name=VENUE_NAMES.get(str(race.venue), '不明'))

    except Exception as e:
        current_app.logger.error(f"Error in race_shutuba: {str(e)}")
        # スタックトレースも記録
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash('出馬表の取得中にエラーが発生しました', 'error')
        return render_template('shutuba.html', 
                          race=None,
                          entries=[],
                          venue_name='不明')

@lru_cache(maxsize=128)
def get_race_statistics(race_id):
    """レース統計情報を取得（キャッシュ付き）"""
    try:
        return db.session.query(
            func.count(Entry.id).label('total_entries'),
            func.avg(Entry.odds).label('avg_odds'),
            func.min(Entry.odds).label('min_odds'),
            func.max(Entry.odds).label('max_odds')
        ).filter(
            Entry.race_id == race_id
        ).first()
    except Exception as e:
        current_app.logger.error(f"Error getting race statistics: {str(e)}")
        return None

def create_favorite_horse_entry_notifications(race_id, horse_id):
    """お気に入り馬の出走通知を作成"""
    try:
        # お気に入りユーザーと必要な情報を一括取得
        favorites = db.session.query(
            User.id,
            Horse.name,
            Race.name,
            Race.date
        ).join(
            Favorite, User.id == Favorite.user_id
        ).join(
            Horse, Favorite.horse_id == Horse.id
        ).join(
            Race, Race.id == race_id
        ).filter(
            Favorite.horse_id == horse_id
        ).all()

        # 通知を一括作成
        notifications = [
            Notification(
                user_id=user_id,
                type='favorite_horse_entry',
                content=f'お気に入りの{horse_name}が{race_name}({race_date.strftime("%Y/%m/%d")})に出走予定です',
                related_id=race_id,
                is_read=False
            )
            for user_id, horse_name, race_name, race_date in favorites
        ]
        
        if notifications:
            db.session.bulk_save_objects(notifications)
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating notifications: {str(e)}")

@app.route('/races/<int:race_id>/entries', methods=['POST'])
@login_required
def register_race_entry(race_id):
    try:
        data = request.get_json()
        horse_id = data.get('horse_id')
        
        if not horse_id:
            return jsonify({'status': 'error', 'message': '馬IDが指定されていません'}), 400

        # 重複チェック
        existing_entry = db.session.query(ShutubaEntry).filter_by(
            race_id=race_id,
            horse_id=horse_id
        ).first()
        
        if existing_entry:
            return jsonify({'status': 'error', 'message': 'すでに登録されています'}), 400
        
        # 出走登録
        entry = ShutubaEntry(
            race_id=race_id,
            horse_id=horse_id
        )
        db.session.add(entry)
        db.session.commit()
        
        # お気に入り馬の通知を作成
        create_favorite_horse_entry_notifications(race_id, horse_id)
        
        return jsonify({'status': 'success', 'message': '出走登録が完了しました'})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in register_race_entry: {str(e)}")
        return jsonify({'status': 'error', 'message': 'エラーが発生しました'}), 500

@app.route('/api/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    try:
        notification_ids = request.json.get('notification_ids', [])
        if notification_ids:
            Notification.query.filter(
                Notification.id.in_(notification_ids),
                Notification.user_id == current_user.id
            ).update({Notification.is_read: True}, synchronize_session=False)
        else:
            Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).update({Notification.is_read: True}, synchronize_session=False)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking notifications as read: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    try:
        if request.method == 'POST':
            data = request.get_json()
            
            # 設定を一括更新
            settings = db.session.query(UserSettings)\
                .filter_by(user_id=current_user.id)\
                .first()
                
            if not settings:
                settings = UserSettings(user_id=current_user.id)
                db.session.add(settings)
            
            # 通知設定の更新
            settings.email_notifications = data.get('email_notifications', False)
            settings.push_notifications = data.get('push_notifications', False)
            settings.notification_types = data.get('notification_types', [])
            
            # 表示設定の更新
            settings.theme = data.get('theme', 'light')
            settings.display_odds = data.get('display_odds', True)
            settings.language = data.get('language', 'ja')
            
            db.session.commit()
            return jsonify({'status': 'success'})
            
        else:
            # 設定を取得
            settings = db.session.query(UserSettings)\
                .filter_by(user_id=current_user.id)\
                .options(load_only(
                    'email_notifications',
                    'push_notifications',
                    'notification_types',
                    'theme',
                    'display_odds',
                    'language'
                ))\
                .first()
            
            if not settings:
                return jsonify({
                    'email_notifications': False,
                    'push_notifications': False,
                    'notification_types': [],
                    'theme': 'light',
                    'display_odds': True,
                    'language': 'ja'
                })
            
            return jsonify({
                'email_notifications': settings.email_notifications,
                'push_notifications': settings.push_notifications,
                'notification_types': settings.notification_types,
                'theme': settings.theme,
                'display_odds': settings.display_odds,
                'language': settings.language
            })
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in user settings: {str(e)}")
        return jsonify({'error': '設定の処理中にエラーが発生しました'}), 500

@app.route('/api/user/favorites', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_favorites():
    try:
        current_app.logger.info(f"Managing favorites: {request.method} request from user {current_user.id}")
        current_app.logger.info(f"Request data: {request.json}")
        
        if request.method == 'POST':
            horse_id = request.json.get('horse_id')
            
            if not horse_id:
                current_app.logger.error("No horse_id provided in request")
                return jsonify({'error': '馬IDが指定されていません'}), 400
                
            # 重複チェック
            existing = db.session.query(Favorite)\
                .filter_by(user_id=current_user.id, horse_id=horse_id)\
                .first()
                
            if existing:
                current_app.logger.info(f"Horse {horse_id} already in favorites for user {current_user.id}")
                return jsonify({'error': 'すでにお気に入りに登録されています'}), 400
                
            favorite = Favorite(user_id=current_user.id, horse_id=horse_id)
            db.session.add(favorite)
            db.session.commit()
            
            current_app.logger.info(f"Added horse {horse_id} to favorites for user {current_user.id}")
            return jsonify({'status': 'success'})
            
        else:  # DELETE
            horse_id = request.json.get('horse_id')
            
            if not horse_id:
                current_app.logger.error("No horse_id provided in request")
                return jsonify({'error': '馬IDが指定されていません'}), 400
                
            db.session.query(Favorite)\
                .filter_by(user_id=current_user.id, horse_id=horse_id)\
                .delete()
                
            db.session.commit()
            current_app.logger.info(f"Removed horse {horse_id} from favorites for user {current_user.id}")
            return jsonify({'status': 'success'})
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error managing favorites: {str(e)}")
        current_app.logger.error(f"Exception traceback: {traceback.format_exc()}")
        return jsonify({'error': 'お気に入りの処理中にエラーが発生しました'}), 500

@app.route('/races/<int:race_id>/memos/<int:memo_id>/delete', methods=['POST'])
@login_required
def delete_race_memo_post(race_id, memo_id):
    try:
        memo = RaceMemo.query.get_or_404(memo_id)
        
        # 権限チェック
        if memo.user_id != current_user.id:
            flash('このメモを削除する権限がありません', 'danger')
            return redirect(url_for('race', race_id=race_id))
        
        db.session.delete(memo)
        db.session.commit()
        
        flash('メモを削除しました', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting race memo: {str(e)}")
        flash('メモの削除中にエラーが発生しました', 'danger')
    
    return redirect(url_for('race', race_id=race_id))

@app.route('/races/<int:race_id>/review', methods=['POST'])
@login_required
def save_review(race_id):
    try:
        # フォームからデータを取得
        content = request.form.get('content', '')
        summary = request.form.get('summary', '')
        is_premium = 'is_premium' in request.form
        price = int(request.form.get('price', 0)) if is_premium else 0
        
        # デバッグログを追加
        current_app.logger.info(f"Saving review for race {race_id}: content={content[:20]}..., premium={is_premium}, price={price}")
        
        # 既存のレビューを確認
        existing_review = RaceReview.query.filter_by(
            user_id=current_user.id,
            race_id=race_id
        ).first()
        
        if existing_review:
            # 既存のレビューを更新
            existing_review.content = content
            # summaryフィールドがあれば更新、なければcontentの最初の部分を使用
            if hasattr(existing_review, 'summary'):
                existing_review.summary = summary
            existing_review.is_premium = is_premium
            existing_review.price = price
            existing_review.updated_at = datetime.utcnow()
            db.session.commit()
            flash('レビューを更新しました', 'success')
        else:
            # 新しいレビューを作成
            new_review = RaceReview(
                user_id=current_user.id,
                race_id=race_id,
                content=content,
                is_premium=is_premium,
                price=price
            )
            # summaryフィールドがあれば設定
            if hasattr(RaceReview, 'summary'):
                new_review.summary = summary
            db.session.add(new_review)
            db.session.commit()
            flash('レビューを保存しました', 'success')
        
        # 正しいエンドポイント名に修正
        return redirect(url_for('race', race_id=race_id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving review: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        flash('レビューの保存中にエラーが発生しました', 'danger')
        # 正しいエンドポイント名に修正
        return redirect(url_for('race', race_id=race_id))

@app.route('/reviews/<int:review_id>')
def review_detail(review_id):
    review = RaceReview.query.get_or_404(review_id)
    
    # 非公開レビューの場合、アクセス権をチェック
    if not review.is_public:
        if not current_user.is_authenticated:
            flash('このレビューは非公開です。', 'warning')
            return redirect(url_for('index'))
        
        # 作成者でない場合、購入済みかチェック
        if review.user_id != current_user.id:
            purchase = ReviewPurchase.query.filter_by(
                user_id=current_user.id,
                review_id=review_id,
                status='completed'
            ).first()
            
            if not purchase:
                flash('このレビューにアクセスする権限がありません。', 'warning')
                return redirect(url_for('index'))
    
    # 有料コンテンツの場合、購入済みかチェック
    if review.is_premium and current_user.is_authenticated and review.user_id != current_user.id:
        purchase = ReviewPurchase.query.filter_by(
            user_id=current_user.id,
            review_id=review_id,
            status='completed'
        ).first()
        
        if not purchase:
            return redirect(url_for('purchase_review', review_id=review_id))
    
    return render_template('review_detail.html', review=review)
