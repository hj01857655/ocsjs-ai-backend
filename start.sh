#!/bin/bash

# 设置默认端口
export PORT=${PORT:-5000}

# 启动应用
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --preload app:app
