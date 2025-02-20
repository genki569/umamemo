from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, StringField, PasswordField, EmailField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User

class ChargePointForm(FlaskForm):
    amount = SelectField('チャージ金額', 
                        choices=[
                            ('100', '100ポイント (100円)'),
                            ('500', '500ポイント (500円)'),
                            ('1000', '1,000ポイント (1,000円)'),
                            ('5000', '5,000ポイント (5,000円)'),
                            ('10000', '10,000ポイント (10,000円)')
                        ],
                        coerce=int)
    submit = SubmitField('チャージする') 

class RegistrationForm(FlaskForm):
    username = StringField('ユーザー名', 
                         validators=[
                             DataRequired(message='ユーザー名を入力してください'),
                             Length(min=3, max=20, message='ユーザー名は3文字以上20文字以内で入力してください')
                         ])
    
    email = EmailField('メールアドレス',
                      validators=[
                          DataRequired(message='メールアドレスを入力してください'),
                          Email(message='有効なメールアドレスを入力してください')
                      ])
    
    password = PasswordField('パスワード',
                           validators=[
                               DataRequired(message='パスワードを入力してください'),
                               Length(min=8, message='パスワードは8文字以上で入力してください')
                           ])
    
    submit = SubmitField('登録')

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user:
            raise ValidationError('このユーザー名は既に使用されています')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError('このメールアドレスは既に登録されています') 

class LoginForm(FlaskForm):
    email = EmailField('メールアドレス',
                      validators=[
                          DataRequired(message='メールアドレスを入力してください'),
                          Email(message='有効なメールアドレスを入力してください')
                      ])
    
    password = PasswordField('パスワード',
                           validators=[
                               DataRequired(message='パスワードを入力してください')
                           ])
    
    submit = SubmitField('ログイン') 