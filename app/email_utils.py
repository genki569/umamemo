from flask import render_template, url_for
from flask_mail import Message
from threading import Thread
from app import app, mail

def send_async_email(app, msg):
    """非同期でメールを送信"""
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipients, text_body, html_body):
    """メール送信の共通関数"""
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # 非同期でメールを送信（UI をブロックしないため）
    Thread(target=send_async_email, args=(app, msg)).start()

def send_confirmation_email(user):
    """確認メールを送信"""
    token = user.generate_confirmation_token()
    confirm_url = url_for('confirm_email', token=token, _external=True)
    
    send_email(
        '【馬メモ】メールアドレスの確認',
        [user.email],
        render_template('email/confirm_email.txt', user=user, confirm_url=confirm_url),
        render_template('email/confirm_email.html', user=user, confirm_url=confirm_url)
    ) 