#!/usr/local/bin/python
import sys
import os

# パスを追加
sys.path.insert(0, os.path.expanduser('~/.local/lib/python3.6/site-packages'))

import cgitb
cgitb.enable()

# 必ずヘッダーを出力
print("Content-Type: text/html")
print()

try:
    from wsgiref.handlers import CGIHandler
    from app import app

    if __name__ == '__main__':
        CGIHandler().run(app)
except Exception as e:
    print("<h1>Error</h1>")
    print(f"<pre>{str(e)}</pre>")