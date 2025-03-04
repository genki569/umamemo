#!/bin/bash

# Gitからpull
git pull

# ログディレクトリの設定
sudo mkdir -p /var/www/umamemo/logs
sudo chown -R www-data:www-data /var/www/umamemo/logs
sudo chmod 775 /var/www/umamemo/logs
sudo touch /var/www/umamemo/logs/umamemo.log
sudo chown www-data:www-data /var/www/umamemo/logs/umamemo.log
sudo chmod 664 /var/www/umamemo/logs/umamemo.log

# サービスの再起動
sudo systemctl restart umamemo 