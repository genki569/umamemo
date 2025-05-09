from datetime import datetime, timedelta
from app import db, login, app
import json
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import case
import secrets
from flask import current_app
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

    # @cache.memoize(timeout=300)  # コメントアウト
    def get_race_statistics(self):
        """レース統計情報を取得"""
        return db.session.query(
            func.count(Entry.id).label('total_entries'),
            func.avg(Entry.odds).label('avg_odds'),
            func.min(Entry.odds).label('min_odds'),
            func.max(Entry.odds).label('max_odds')
        ).filter(
            Entry.race_id == self.id
        ).first()

    # @cache.memoize(timeout=300)  # コメントアウト
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

    # @cache.memoize(timeout=300)  # コメントアウト
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
    
    id = db.Column(db.BigInteger, primary_key=True)  # BigIntegerのままにする
    name = db.Column(db.String(100), nullable=False)
    
    entries = db.relationship('Entry',
                            back_populates='jockey',
                            lazy='dynamic')

    def __repr__(self):
        return f'<Jockey {self.name}>'

class User(UserMixin, db.Model):
    """
    ユーザー情報を管理するモデルクラス
    
    ユーザーのプロフィール情報、ポイント情報、会員ステータスなどを管理し、
    ポイント加算/使用や会員ステータスの変更などの機能を提供します。
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    last_login = db.Column(db.DateTime, default=datetime.now)
    points = db.Column(db.Integer, default=0)
    is_premium = db.Column(db.Boolean, default=False)
    is_master = db.Column(db.Boolean, default=False)  # マスタープレミアム会員フラグ
    premium_expires_at = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # ステータス関連
    membership_type = db.Column(db.String(20), default='free')  # 'free', 'premium', 'master'
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
    
    # メール認証用のフィールドを追加
    email_confirmed = db.Column(db.Boolean, default=False)
    confirmation_token = db.Column(db.String(100), unique=True)
    confirmation_token_expires = db.Column(db.DateTime)
    
    # リレーションシップ
    user_settings = db.relationship('UserSettings', 
                                  backref=db.backref('user_ref', uselist=False),
                                  uselist=False,
                                  overlaps="user_settings,user_ref")

    # レビュー関連のリレーションシップを追加
    reviews = db.relationship('RaceReview', backref='author', lazy='dynamic')

    # リレーションシップを追加
    purchased_reviews = db.relationship('ReviewPurchase', backref='purchaser', lazy='dynamic')
    
    def get_point_balance(self):
        return self.point_balance
    
    def add_points(self, amount, reason=None):
        """
        ユーザーにポイントを追加する
        
        Args:
            amount: 追加するポイント数
            reason: ポイント追加の理由
            
        Returns:
            bool: ポイント追加が成功したかどうか
        """
        if amount <= 0:
            return False
            
        self.points += amount
        
        # ポイント履歴を記録
        point_log = UserPointLog(
            user_id=self.id,
            points=amount,
            action='add',
            reason=reason or 'システム付与'
        )
        db.session.add(point_log)
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"ポイント追加エラー: {e}")
            return False
    
    def use_points(self, amount, reason=None):
        """
        ユーザーのポイントを使用する
        
        Args:
            amount: 使用するポイント数
            reason: ポイント使用の理由
            
        Returns:
            bool: ポイント使用が成功したかどうか
        """
        if amount <= 0 or self.points < amount:
            return False
            
        self.points -= amount
        
        # ポイント履歴を記録
        point_log = UserPointLog(
            user_id=self.id,
            points=amount,
            action='use',
            reason=reason or 'ポイント使用'
        )
        db.session.add(point_log)
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"ポイント使用エラー: {e}")
            return False
            
    def get_membership_type(self):
        """
        ユーザーの会員種別を取得する
        
        Returns:
            str: 会員種別 (free, premium, master)
        """
        if self.is_master:
            return 'master'
        elif self.is_premium:
            return 'premium'
        else:
            return 'free'
            
    def is_premium_active(self):
        """
        プレミアム会員が有効かどうかを確認する
        
        Returns:
            bool: プレミアム会員が有効かどうか
        """
        return self.is_premium and (self.premium_expires_at is None or self.premium_expires_at > datetime.now())
            
    def is_master_active(self):
        """
        マスタープレミアム会員が有効かどうかを確認する
        
        Returns:
            bool: マスタープレミアム会員が有効かどうか
        """
        return self.is_master and (self.premium_expires_at is None or self.premium_expires_at > datetime.now())
            
    def set_premium_status(self, status, duration_days=30, changed_by=None, reason=None):
        """
        ユーザーの会員ステータスを設定する
        
        Args:
            status: 設定する会員ステータス ('free', 'premium', 'master')
            duration_days: プレミアム会員の有効期間（日数）
            changed_by: 変更を行ったユーザーID（None=システム変更）
            reason: 変更理由
            
        Returns:
            bool: 変更が成功したかどうか
        """
        try:
            # 現在のステータスを取得
            old_status = self.get_membership_type()
            
            # ステータスが同じ場合は何もしない（期間延長の場合を除く）
            if old_status == status and status == 'free':
                return True
                
            # 有効期限の計算
            expires_at = None
            if status in ['premium', 'master']:
                # 現在の有効期限がある場合はそこから延長、なければ現在から設定
                if self.premium_expires_at and self.premium_expires_at > datetime.now():
                    expires_at = self.premium_expires_at + timedelta(days=duration_days)
                else:
                    expires_at = datetime.now() + timedelta(days=duration_days)
            
            # ステータスの更新
            if status == 'master':
                self.is_premium = True
                self.is_master = True
                self.premium_expires_at = expires_at
            elif status == 'premium':
                self.is_premium = True
                self.is_master = False
                self.premium_expires_at = expires_at
            else:  # free
                self.is_premium = False
                self.is_master = False
                self.premium_expires_at = None
            
            # 変更ログを記録
            log = MembershipChangeLog(
                user_id=self.id,
                old_status=old_status,
                new_status=status,
                changed_by=changed_by,
                reason=reason,
                expires_at=expires_at
            )
            db.session.add(log)
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error setting premium status: {e}")
            return False
    
    def check_and_update_membership_status(self):
        """
        会員ステータスを確認し、期限切れの場合は自動的に更新する
        
        Returns:
            bool: ステータスが変更されたかどうか
        """
        # 期限切れでない場合は何もしない
        if not self.is_premium or not self.premium_expires_at:
            return False
            
        # 期限切れの場合
        if self.premium_expires_at < datetime.now():
            current_status = self.get_membership_type()
            self.is_premium = False
            self.is_master = False
            self.premium_expires_at = None
            
            # 変更ログを記録
            log = MembershipChangeLog(
                user_id=self.id,
                old_status=current_status,
                new_status='free',
                reason='自動更新: 会員期限切れ',
                expires_at=None
            )
            db.session.add(log)
            db.session.commit()
            return True
            
        return False

    def get_membership_history(self, limit=10):
        """
        ユーザーの会員ステータス変更履歴を取得する
        
        Args:
            limit: 取得する履歴の最大数
            
        Returns:
            list: 会員ステータス変更履歴のリスト
        """
        return MembershipChangeLog.get_user_membership_history(self.id, limit)

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

    def set_password(self, password):
        # scryptではなく、sha256を使用してハッシュ長を制御
        self.password_hash = generate_password_hash(
            password,
            method='pbkdf2:sha256',  # scryptから変更
            salt_length=8  # ソルトの長さも調整
        )
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 購入済みレビューを取得するメソッドを追加
    def get_purchased_review_ids(self):
        """ユーザーが購入したレース回顧のIDリストを返す"""
        purchases = ReviewPurchase.query.filter_by(user_id=self.id).all()
        return [purchase.review_id for purchase in purchases]

    def generate_confirmation_token(self):
        """メール確認用のトークンを生成"""
        token = secrets.token_urlsafe(32)
        self.confirmation_token = token
        self.confirmation_token_expires = datetime.utcnow() + timedelta(hours=24)
        return token
    
    def confirm_email(self):
        """メールアドレスを確認済みにする"""
        self.email_confirmed = True
        self.confirmation_token = None
        self.confirmation_token_expires = None
        
    def is_email_confirmed(self):
        """メールが確認済みかどうか"""
        return self.email_confirmed

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
    review = db.relationship('RaceReview', 
                           backref=db.backref('purchase_history', lazy='dynamic'),
                           overlaps="purchases,target_review")

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
    
    user = db.relationship('User', 
                           backref=db.backref('settings', uselist=False),
                           overlaps="user_settings,user_ref")

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)  # textタイプに変更
    type = db.Column(db.String(20), nullable=False)  # typeカラムを追加
    is_read = db.Column(db.Boolean)  # readをis_readに変更
    created_at = db.Column(db.DateTime)
    link = db.Column(db.String(255))  # linkカラムを追加

    def __repr__(self):
        return f'<Notification {self.id}>'

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
    """
    会員ステータス変更履歴を管理するモデルクラス
    
    ユーザーの会員種別変更に関する履歴を記録し、
    変更日時、変更前後のステータス、有効期限などを追跡します。
    """
    __tablename__ = 'membership_change_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    old_status = db.Column(db.String(20), nullable=False)
    new_status = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # リレーションシップ
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('membership_logs', lazy='dynamic'))
    changer = db.relationship('User', foreign_keys=[changed_by])
    
    def __init__(self, user_id, old_status, new_status, changed_by=None, reason=None, expires_at=None):
        """
        会員ステータス変更ログの初期化
        
        Args:
            user_id: ユーザーID
            old_status: 変更前のステータス
            new_status: 変更後のステータス
            changed_by: 変更を行ったユーザーID（None=システム変更）
            reason: 変更理由
            expires_at: 会員資格の有効期限
        """
        self.user_id = user_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_by = changed_by
        self.reason = reason
        self.expires_at = expires_at
    
    @staticmethod
    def get_user_membership_history(user_id, limit=10):
        """
        特定ユーザーの会員ステータス変更履歴を取得
        
        Args:
            user_id: 履歴を取得するユーザーID
            limit: 取得する履歴の最大数
            
        Returns:
            list: 会員ステータス変更履歴のリスト
        """
        return MembershipChangeLog.query.filter_by(user_id=user_id)\
            .order_by(MembershipChangeLog.created_at.desc())\
            .limit(limit).all()

class PaymentLog(db.Model):
    """
    支払いログを管理するモデルクラス
    
    ユーザーの支払い履歴を記録し、プレミアム会員と
    マスタープレミアム会員の支払い状況を追跡します。
    """
    __tablename__ = 'payment_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    plan_type = db.Column(db.String(20), nullable=False, default='premium')  # premium または master
    duration_days = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, failed, refunded
    payment_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    user = db.relationship('User', backref=db.backref('payment_logs', lazy=True))

    def __init__(self, user_id, amount, plan_type='premium', duration_days=30, status='pending', payment_date=None, transaction_id=None):
        """
        PaymentLogオブジェクトの初期化
        
        Args:
            user_id: ユーザーID
            amount: 支払い金額
            plan_type: プランタイプ（'premium'または'master'）
            duration_days: プラン期間（日数）
            status: 支払い状態
            payment_date: 支払い日時
            transaction_id: トランザクションID
        """
        self.user_id = user_id
        self.amount = amount
        self.plan_type = plan_type
        self.duration_days = duration_days
        self.status = status
        self.payment_date = payment_date or datetime.now()
        self.transaction_id = transaction_id

    def __repr__(self):
        """オブジェクトの文字列表現を返す"""
        return f'<PaymentLog {self.id} {self.user_id} {self.plan_type} {self.status}>'
    
    def is_master_plan(self):
        """マスタープレミアムプランかどうかを確認する"""
        return self.plan_type == 'master'

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

class AccessLog(db.Model):
    __tablename__ = 'access_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(50))
    path = db.Column(db.String(200))  # 200文字に合わせる
    method = db.Column(db.String(10))
    status_code = db.Column(db.Integer)
    user_agent = db.Column(db.String(200))  # 200文字に合わせる
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref=db.backref('access_logs', lazy='dynamic'))

# ポイント換金リクエストモデル
class PointWithdrawal(db.Model):
    __tablename__ = 'point_withdrawals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requested_amount = db.Column(db.Integer, nullable=False)  # リクエスト金額
    fee_amount = db.Column(db.Integer, nullable=False)  # 手数料
    fee_rate = db.Column(db.Float, nullable=False)  # 手数料率（0.15 または 0.10）
    net_amount = db.Column(db.Integer, nullable=False)  # 実際の換金額
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    request_note = db.Column(db.Text)  # ユーザーからのメモ
    admin_note = db.Column(db.Text)  # 管理者メモ
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 処理した管理者
    bank_info = db.Column(db.Text)  # 銀行情報（JSON形式で保存）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # 換金処理完了日時
    
    # リレーションシップ
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('withdrawals', lazy='dynamic'))
    admin = db.relationship('User', foreign_keys=[admin_id], backref=db.backref('processed_withdrawals', lazy='dynamic'))
    
    def __repr__(self):
        return f'<PointWithdrawal {self.id}: {self.user_id} - {self.requested_amount}pts>'
        
    @property
    def status_display(self):
        status_map = {
            'pending': '処理待ち',
            'approved': '承認済み',
            'rejected': '却下',
            'completed': '振込完了'
        }
        return status_map.get(self.status, self.status)
        
    @property
    def status_color(self):
        status_color_map = {
            'pending': 'warning',
            'approved': 'info',
            'rejected': 'danger',
            'completed': 'success'
        }
        return status_color_map.get(self.status, 'secondary')

