import click
from flask.cli import with_appcontext
from app import app, db
from app.models import User

@app.cli.command('create-admin')
@click.argument('email')
@click.argument('username')
@click.argument('password')
@with_appcontext
def create_admin(email, username, password):
    """管理者ユーザーを作成するコマンド"""
    # 既存ユーザーのチェック
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        click.echo(f'ユーザー {email} は既に存在します。')
        if existing_user.is_admin:
            click.echo('このユーザーは既に管理者です。')
            return
        
        # 既存ユーザーを管理者に昇格
        existing_user.is_admin = True
        db.session.commit()
        click.echo(f'ユーザー {email} を管理者に昇格しました。')
        return
    
    # 新規管理者ユーザーの作成
    user = User(
        email=email,
        username=username,
        is_admin=True
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    click.echo(f'管理者ユーザー {username} ({email}) を作成しました。') 