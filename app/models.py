from datetime import datetime
from app import db, login, app
import json
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import case
@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class Race(db.Model):
    __tablename__ = 'races'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    venue = db.Column(db.String(50))
    venue_id = db.Column(db.String(50))
    race_number = db.Column(db.Integer)
    race_year = db.Column(db.Integer)
    kai = db.Column(db.String(20))
    nichi = db.Column(db.String(20))
    race_class = db.Column(db.String(50))
    distance = db.Column(db.Integer)
    track_type = db.Column(db.String(20))
    direction = db.Column(db.String(20))
    weather = db.Column(db.String(20))
    track_condition = db.Column(db.String(20))
    memo = db.Column(db.Text)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    entries = db.relationship('Entry', back_populates='race', lazy='dynamic')
    
    __table_args__ = (
        db.Index('idx_race_date_venue', 'date', 'venue'),
        db.Index('idx_race_date_desc', date.desc()),
        db.Index('idx_race_venue_id', 'venue_id'),
        db.Index('idx_race_number', 'race_number'),
    )

    # 日付操作用のプロパティを追加
    @property
    def date_obj(self):
        """日付オブジェクトとして取得"""
        try:
            return datetime.strptime(self.date, '%Y-%m-%d')
        except (ValueError, TypeError):
            return None
            
    def format_date(self, format='%Y/%m/%d'):
        """指定されたフォーマットで日付を文字列として取得"""
        date_obj = self.date_obj
        if date_obj:
            return date_obj.strftime(format)
        return self.date  # フォールバック

    def __repr__(self):
        return f'<Race {self.name}>'

    def has_result(self):
        """レース結果が登録されているかどうかを判定"""
        # デバッグ用にSQLクエリを出力
        entries = Entry.query.filter_by(race_id=self.id).all()
        print(f"Race {self.id} has {len(entries)} entries")
        
        # とりあえ全てのレースを表するように一時的に変更
        return True  # 開発中は全てのレースを表示

        # 来の実装（後で有効化）
        # return Entry.query.filter(
        #     Entry.race_id == self.id,
        #     Entry.position.isnot(None)
        # ).first() is not None

    def get_entries(self):
        """エントリー一覧を取得（出馬表用）"""
        return Entry.query.filter_by(race_id=self.id).order_by(
            Entry.bracket_number,
            Entry.horse_number
        ).all()

    def get_shutuba_entries(self):
        """出馬表エントリーのみを取得"""
        return (Entry.query
                .filter_by(race_id=self.id)
                .join(Horse)
                .join(Jockey)
                .filter(Entry.horse_number.is_(None))
                .filter(Entry.position.is_(None))
                .filter(Entry.finish_time.is_(None))
                .all())
    
    def get_result_entries(self):
        """結果エントリーのみを取得"""
        return (Entry.query
                .filter_by(race_id=self.id)
                .join(Horse)
                .join(Jockey)
                .filter(Entry.horse_number.isnot(None))
                .order_by(Entry.horse_number)
                .all())

    @classmethod
    def generate_race_id(cls, date_str, venue, race_number):
        """レースIDの生成（15桁）"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_num = date_obj.strftime('%Y%m%d')
            venue_code = cls.get_venue_code(venue)
            kai = '01'  # 開催回は現時点では'01'固定
            race_num = str(race_number).zfill(2)
            return int(f"{date_num}{venue_code}{kai}{race_num}")
        except Exception as e:
            print(f"Error generating race ID: {str(e)}")
            return None
    
    def add_memo(self, content):
        """レースにメモを追加"""
        memo = RaceMemo(race_id=self.id, content=content)
        db.session.add(memo)
        return memo

    def get_memos(self):
        """レースのメモを取得"""
        return RaceMemo.query.filter_by(race_id=self.id).order_by(RaceMemo.created_at.desc()).all()

    def delete_memo(self, memo_id):
        """メモを削除"""
        memo = RaceMemo.query.get(memo_id)
        if memo and memo.race_id == self.id:
            db.session.delete(memo)

    def is_same_race(self, other):
        """同一レースかどうかを判定"""
        if not isinstance(other, Race):
            return False
        return (
            self.date == other.date and
            self.name == other.name and
            self.venue == other.venue
        )

    def get_shutuba_table(self):
        """出馬表データを取得（過去戦績含む）"""
        # Eager Loadingを使用して関連データを一度に取得
        entries = (db.session.query(
            ShutubaEntry,
            Horse,
            Jockey,
            db.session.query(
                Entry.horse_id,
                func.array_agg(
                    func.json_build_object(
                        'date', Race.date,
                        'venue', Race.venue,
                        'race_name', Race.name,
                        'position', Entry.position,
                        'finish_time', Entry.finish_time
                    )
                ).label('recent_results')
            ).join(Race)
            .filter(Entry.position.isnot(None))
            .group_by(Entry.horse_id)
            .correlate(Horse)
            .as_scalar()
        ).join(Horse)
        .outerjoin(Jockey)
        .filter(ShutubaEntry.race_id == self.id)
        .options(joinedload(ShutubaEntry.horse).joinedload(Horse.entries))
        .order_by(ShutubaEntry.bracket_number)
        .all())

        return [{
            'entry': entry,
            'horse': horse,
            'jockey': jockey,
            'recent_results': recent_results or []
        } for entry, horse, jockey, recent_results in entries]

    @cache.memoize(timeout=300)
    def get_race_statistics(self):
        """レース統計情報を取得（キャッシュ付き）"""
        return db.session.query(
            func.count(Entry.id).label('total_entries'),
            func.avg(Entry.odds).label('avg_odds'),
            func.min(Entry.odds).label('min_odds'),
            func.max(Entry.odds).label('max_odds')
        ).filter(
            Entry.race_id == self.id
        ).first()

    @cache.memoize(timeout=300)
    def get_track_condition_stats(self, horse_ids):
        """馬場状態別の成績を取得（キャッシュ付き）"""
        return db.session.query(
            Entry.horse_id,
            Race.track_condition,
            func.count(Entry.id).label('total'),
            func.sum(case([(Entry.position == 1, 1)], else_=0)).label('wins'),
            func.sum(case([(Entry.position <= 3, 1)], else_=0)).label('top3')
        ).join(Race).filter(
            Entry.horse_id.in_(horse_ids),
            Entry.position.isnot(None),
            Race.track_condition.isnot(None)
        ).group_by(
            Entry.horse_id,
            Race.track_condition
        ).all()

    @cache.memoize(timeout=300)
    def get_jockey_stats(self, horse_ids):
        """騎手別の成績を取得（キャッシュ付き）"""
        return db.session.query(
            Entry.horse_id,
            Jockey.name,
            func.count(Entry.id).label('total'),
            func.sum(case([(Entry.position == 1, 1)], else_=0)).label('wins'),
            func.sum(case([(Entry.position <= 3, 1)], else_=0)).label('top3')
        ).join(Race).join(Jockey).filter(
            Entry.horse_id.in_(horse_ids),
            Entry.position.isnot(None),
            Entry.jockey_id.isnot(None)
        ).group_by(
            Entry.horse_id,
            Jockey.id,
            Jockey.name
        ).all()

class Horse(db.Model):
    __tablename__ = 'horses'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sex = db.Column(db.String(10))
    memo = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp(),
                          onupdate=db.func.current_timestamp())
    created_at = db.Column(db.DateTime, nullable=False, 
                          server_default=db.func.current_timestamp())
    
    entries = db.relationship('Entry',
                            back_populates='horse',
                            lazy='dynamic',
                            overlaps="race_entries")

    # お気に入り関連
    favorites = db.relationship('Favorite',
                              back_populates='horse',
                              lazy='dynamic',
                              overlaps="horse_favorites,favorite_horses")

    # お気に入りにしているユーザーへ参照
    favorited_by = db.relationship(
        'User',
        secondary='favorites',
        backref=db.backref('favorite_horses', lazy='dynamic'),
        overlaps="favorites,horse_favorites"
    )

    # trainerカラムの追加（必要な場合）
    trainer = db.Column(db.String(100))

    def __repr__(self):
        return f'<Horse {self.name}>'

    def get_last_three_results(self):
        """
        過去3回の着順を取得
        戻り値: [(レース名, 着順, 日付), ...]
        """
        return db.session.query(
            Race.name,
            Entry.position,
            Race.date
        ).join(
            Entry, Entry.race_id == Race.id
        ).filter(
            Entry.horse_id == self.id
        ).order_by(
            Race.date.desc()
        ).limit(3).all()

    def is_favorite(self, user_id):
        """ユーザーのお気に入りかどうかをチェック"""
        if not user_id:
            return False
        return Favorite.query.filter_by(
            user_id=user_id,
            horse_id=self.id
        ).first() is not None

    def add_memo(self, content):
        current_memos = self.get_memos()
        new_memo = {
            'id': len(current_memos) + 1,
            'content': content,
            'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        current_memos.append(new_memo)
        self.memo = json.dumps(current_memos)

    def get_memos(self):
        try:
            return json.loads(self.memo) if self.memo else []
        except:
            return []

    def delete_memo(self, memo_id):
        current_memos = self.get_memos()
        self.memo = json.dumps([m for m in current_memos if m['id'] != memo_id])

class Entry(db.Model):
    __tablename__ = 'entries'
    
    id = db.Column(db.BigInteger, primary_key=True)
    race_id = db.Column(db.BigInteger, db.ForeignKey('races.id'), nullable=True)
    horse_id = db.Column(db.BigInteger, db.ForeignKey('horses.id'), nullable=True)
    jockey_id = db.Column(db.BigInteger, db.ForeignKey('jockeys.id'), nullable=True)
    horse_number = db.Column(db.Integer, nullable=True)
    odds = db.Column(db.String(10), nullable=True)
    popularity = db.Column(db.Integer, nullable=True)
    horse_weight = db.Column(db.Integer, nullable=True)
    weight_change = db.Column(db.Integer, nullable=True)
    prize = db.Column(db.Numeric(10,1), nullable=True)
    position = db.Column(db.Integer, nullable=True)
    frame_number = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Numeric(6,1), nullable=True)
    time = db.Column(db.String(10), nullable=True)
    margin = db.Column(db.String(10), nullable=True)
    passing = db.Column(db.String(20), nullable=True)
    last_3f = db.Column(db.Numeric(3,1), nullable=True)

    # リレーションシップ
    race = db.relationship('Race', back_populates='entries')
    horse = db.relationship('Horse', back_populates='entries')
    jockey = db.relationship('Jockey', back_populates='entries')

    @classmethod
    def generate_entry_id(cls, race_id, horse_number):
        """
        エントリーIDの生成（17桁）
        レースID(15桁) + 馬番(2桁)
        """
        try:
            return int(f"{race_id}{str(horse_number).zfill(2)}")
        except:
            return None

    def __init__(self, **kwargs):
        super(Entry, self).__init__(**kwargs)
        if 'id' not in kwargs and 'race_id' in kwargs and 'horse_number' in kwargs:
            self.id = self.generate_entry_id(
                kwargs['race_id'],
                kwargs['horse_number']
            )

    def __repr__(self):
        return f'<Entry {self.horse.name if self.horse else "Unknown"} in Race {self.race_id}>'

    @property
    def is_shutuba(self):
        """出馬表エントリーかどうかを判定"""
        return self.horse_number is None and self.position is None and self.finish_time is None
    
    @property
    def is_result(self):
        """結果エトリーかどうかを定"""
        return not self.is_shutuba

    def is_same_race(self, other):
        """同一レースのエントリーかどうかを判定"""
        if not isinstance(other, Entry):
            return False
        return self.race.is_same_race(other.race)

    __table_args__ = (
        db.Index('idx_entry_race_horse', 'race_id', 'horse_id'),
        db.Index('idx_entry_position', 'position'),
    )

class Jockey(db.Model):
    __tablename__ = 'jockeys'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    entries = db.relationship('Entry',
                            back_populates='jockey',
                            lazy='dynamic')

    def __repr__(self):
        return f'<Jockey {self.name}>'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # 基本情報
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ステータス関連
    is_admin = db.Column(db.Boolean, default=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_expires_at = db.Column(db.DateTime)
    point_balance = db.Column(db.Integer, default=0)
    
    # プロフィール関
    profile_image = db.Column(db.String(200))
    introduction = db.Column(db.Text)
    twitter = db.Column(db.String(100))
    note = db.Column(db.String(100))
    blog = db.Column(db.String(100))
    youtube = db.Column(db.String(100))
    specialties = db.Column(db.String(200))
    analysis_style = db.Column(db.String(200))
    
    # リレーションシップ
    user_settings = db.relationship('UserSettings', 
                                  backref=db.backref('user_ref', uselist=False),
                                  uselist=False)

    # パスワード関連のメソッドを追加
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # レビュー関連のリレーションシップを追加
    reviews = db.relationship('RaceReview', backref='author', lazy='dynamic')

    def get_point_balance(self):
        return self.point_balance
    
    def add_points(self, points):
        self.point_balance += points
        db.session.commit()
        return True
    
    def use_points(self, points):
        if self.point_balance >= points:
            self.point_balance -= points
            db.session.commit()
            return True
        return False
    
    def has_enough_points(self, points):
        return self.point_balance >= points

    def __repr__(self):
        return f'<User {self.username}>'

    @property
    def is_active(self):
        return True  # アカウントが有効かどうかのロジックを追加できます

    @property
    def is_authenticated(self):
        return True  # 認証済みかどうかのロジクを追加できます

    @property
    def is_anonymous(self):
        return False  # 匿名ユーザーかどうかのロジクを追加できます

    def get_id(self):
        return str(self.id)

# お気に入モデルを追加
class Favorite(db.Model):
    __tablename__ = 'favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    horse_id = db.Column(db.BigInteger, db.ForeignKey('horses.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # シンプルなリレーションシップ定義
    user = db.relationship('User')
    horse = db.relationship('Horse')

    def __repr__(self):
        return f'<Favorite {self.user_id} -> {self.horse_id}>'

class RaceReview(db.Model):
    __tablename__ = 'race_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.BigInteger, db.ForeignKey('races.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    title = db.Column(db.String(100), nullable=True)
    
    # レース全体の分析
    pace_analysis = db.Column(db.Text)
    track_condition_note = db.Column(db.Text)
    race_flow = db.Column(db.Text)
    overall_impression = db.Column(db.Text)
    
    # 上馬の分析
    winner_analysis = db.Column(db.Text)
    placed_horses_analysis = db.Column(db.Text)
    notable_performances = db.Column(db.Text)
    future_prospects = db.Column(db.Text)
    
    # 公開設定
    is_public = db.Column(db.Boolean, default=True)
    is_premium = db.Column(db.Boolean, default=False)
    
    # メモプロ関連の新しいカラム
    price = db.Column(db.Integer, nullable=True)
    sale_status = db.Column(db.String(10), nullable=True, default='draft')
    description = db.Column(db.Text)  # 販売の説明文
    
    # タイムスタンプ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    race = db.relationship('Race', backref=db.backref('reviews', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('race_reviews', lazy='dynamic'))
    purchases = db.relationship('ReviewPurchase', 
                              backref='target_review',
                              lazy='dynamic')

    def __init__(self, **kwargs):
        super(RaceReview, self).__init__(**kwargs)
        if 'sale_status' not in kwargs:
            self.sale_status = 'draft'

    def is_accessible_by(self, user):
        """ユーザーがこのレビューにアクセスできるかチック"""
        if self.is_public:
            return True
        if not user:
            return False
        if user.id == self.user_id:
            return True
        if self.sale_status == 'paid':
            return ReviewPurchase.query.filter_by(
                user_id=user.id,
                review_id=self.id,
                status='completed'
            ).first() is not None
        return False

    def is_purchased(self, user):
        """ユーザーがこのレビューを購入済みかどうかを確認"""
        if self.user_id == user.id:  # 作成者の場合
            return True
            
        return ReviewPurchase.query.filter_by(
            user_id=user.id,
            review_id=self.id,
            status='completed'
        ).first() is not None

class ReviewPurchase(db.Model):
    __tablename__ = 'review_purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey('race_reviews.id'), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ（既存のまま）
    user = db.relationship('User', backref=db.backref('review_purchase_history', lazy='dynamic'))
    review = db.relationship('RaceReview', backref=db.backref('purchase_history', lazy='dynamic'))

class RaceMemo(db.Model):
    __tablename__ = 'race_memos'
    
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.BigInteger, db.ForeignKey('races.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    race = db.relationship('Race', backref=db.backref('memos', lazy=True))
    user = db.relationship('User', backref=db.backref('race_memos', lazy=True))

    def __repr__(self):
        return f'<RaceMemo {self.id} for Race {self.race_id}>'

# UserSettingsモデルを追加
class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    notification_race = db.Column(db.Boolean, default=True)
    notification_memo = db.Column(db.Boolean, default=True)
    items_per_page = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('settings', uselist=False))

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'info', 'warning', 'error' など
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(255))  # 通知に関連するリンク（オプション）
    
    # リレーションシップ
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    @staticmethod
    def create_premium_notification(user, is_activated):
        """プレミアムステータス変更の通知を作成"""
        message = (
            "プレミアム会員に昇格しました！" if is_activated 
            else "プレミアム会員資格が終了しました。"
        )
        notification = Notification(
            user_id=user.id,
            message=message,
            type='premium_status'
        )
        db.session.add(notification)
        db.session.commit()
        return notification

class UserPointLog(db.Model):
    __tablename__ = 'user_point_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.String(20), nullable=False)  # 'add', 'use', 'admin_add' など
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('point_logs', lazy='dynamic'))

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    
    def __init__(self, user_id, ip_address):
        self.user_id = user_id
        self.ip_address = ip_address

class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')
    priority = db.Column(db.String(20), default='normal')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップの修正
    responses = db.relationship('SupportResponse', 
                              backref='support_ticket',  # backref名を変更
                              lazy='dynamic',
                              primaryjoin="SupportTicket.id==SupportResponse.ticket_id")  # 明示的にjoin条件を指定

class SupportResponse(db.Model):
    __tablename__ = 'support_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)  # 外部キーを正しく設定
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # ユザーへのリレーションシップ
    responder = db.relationship('User', 
                              backref=db.backref('support_responses', lazy='dynamic'),
                              foreign_keys=[created_by])

class MembershipChangeLog(db.Model):
    __tablename__ = 'membership_change_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    old_status = db.Column(db.String(20), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # リーシンシップの修正
    user = db.relationship('User', foreign_keys=[user_id], 
                          backref=db.backref('membership_changes', lazy='dynamic'))
    admin = db.relationship('User', foreign_keys=[changed_by],
                          backref=db.backref('membership_changes_made', lazy='dynamic'))

class PaymentLog(db.Model):
    __tablename__ = 'payment_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # monthly, half_yearly, yearly
    duration_days = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='completed')  # pending, completed, failed
    
    user = db.relationship('User', backref=db.backref('payment_logs', lazy='dynamic'))

# 既存のモデルの後に追加
class HorseMemo(db.Model):
    __tablename__ = 'horse_memos'
    
    id = db.Column(db.Integer, primary_key=True)
    horse_id = db.Column(db.Integer, db.ForeignKey('horses.id'), nullable=False)
    memo = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    horse = db.relationship('Horse', backref=db.backref('memos', lazy=True))

class RaceDetail(db.Model):
    __tablename__ = 'race_details'
    
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.BigInteger, db.ForeignKey('races.id'), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    race = db.relationship('Race', backref=db.backref('detail', uselist=False))

class ShutubaEntry(db.Model):
    __tablename__ = 'shutuba_entries'
    
    id = db.Column(db.BigInteger, primary_key=True)
    race_id = db.Column(db.BigInteger, db.ForeignKey('races.id'), nullable=False)
    horse_id = db.Column(db.BigInteger, db.ForeignKey('horses.id'), nullable=False)
    jockey_id = db.Column(db.BigInteger, db.ForeignKey('jockeys.id'))
    
    # 基本情報
    bracket_number = db.Column(db.Integer)      # 枠番
    horse_number = db.Column(db.Integer)        # 馬番
    weight_carry = db.Column(db.Float)          # 斤量
    odds = db.Column(db.Float)                  # オッズ
    popularity = db.Column(db.Integer)          # 人気順
    
    # リレーションシップの修正
    race = db.relationship('Race', backref=db.backref('shutuba_entries', lazy='dynamic'))
    horse = db.relationship('Horse', backref='shutuba_entries')
    jockey = db.relationship('Jockey', backref='shutuba_entries')

    __table_args__ = (
        db.Index('idx_shutuba_race_horse', 'race_id', 'horse_id'),  # 新しいインデックス
        db.Index('idx_shutuba_jockey', 'jockey_id'),  # 新しいインデックス
    )

    def get_recent_results(self, limit=5):
        """直近のレース結果を取得する"""
        return Entry.query.join(Race).filter(
            Entry.horse_id == self.horse_id,
            Entry.position.isnot(None)  # 結果が登録済のエントリのみ
        ).order_by(
            Race.date.desc()
        ).limit(limit).all()

    def get_course_results(self, limit=5):
        """同コースでの過去の結果を取得する"""
        return Entry.query.join(Race).filter(
            Entry.horse_id == self.horse_id,
            Entry.position.isnot(None),
            Race.venue_id == self.race.venue_id,
            Race.distance == self.race.distance
        ).order_by(
            Race.date.desc()
        ).limit(limit).all()

