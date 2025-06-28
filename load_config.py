#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载器 - 解决Railway部署时的模块导入问题
"""

import os
import sys
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 加载JSON配置文件
def load_config():
    config_file = os.path.join(project_root, 'config.json')

    print(f"🔍 [load_config.py] 项目根目录: {project_root}")
    print(f"🔍 [load_config.py] 配置文件路径: {config_file}")
    print(f"🔍 [load_config.py] 配置文件是否存在: {os.path.exists(config_file)}")

    try:
        if os.path.exists(config_file):
            # 尝试多种编码方式
            for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'cp1252']:
                try:
                    with open(config_file, 'r', encoding=encoding) as f:
                        config_data = json.load(f)
                        print(f"✅ [load_config.py] 成功加载配置文件 (编码: {encoding})")
                        return config_data
                except UnicodeDecodeError:
                    continue
                except json.JSONDecodeError as e:
                    print(f"❌ [load_config.py] JSON解析错误 (编码: {encoding}): {str(e)}")
                    continue
            print(f"❌ [load_config.py] 无法读取配置文件，尝试了多种编码方式")
        else:
            print(f"❌ [load_config.py] 配置文件不存在: {config_file}")
    except Exception as e:
        print(f"❌ [load_config.py] 读取配置文件出错: {str(e)}")
    return {}

# 全局配置
_config = load_config()

# 基础配置类
class Config:
    # Flask配置 - 支持环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY', _config.get('security', {}).get('secret_key', os.urandom(24)))
    ENV = os.environ.get('FLASK_ENV', 'development')

    # 服务配置 - 支持环境变量
    HOST = os.environ.get('HOST', _config.get('service', {}).get('host', "0.0.0.0"))
    PORT = int(os.environ.get('PORT', _config.get('service', {}).get('port', 5000)))
    DEBUG = os.environ.get('DEBUG', str(_config.get('service', {}).get('debug', True))).lower() == 'true'
    SSL_CERT_FILE = _config.get('SSL_CERT_FILE')

    # 第三方代理池配置
    THIRD_PARTY_APIS = _config.get('third_party_apis', [])

    # 默认使用第三方代理池
    DEFAULT_PROVIDER = 'third_party_api_pool'

    # 日志配置
    LOG_LEVEL = _config.get('logging', {}).get('level', "INFO")

    # 安全配置（可选）
    ACCESS_TOKEN = _config.get('security', {}).get('access_token')

    # 响应配置
    MAX_TOKENS = int(_config.get('response', {}).get('max_tokens', 500))
    TEMPERATURE = float(_config.get('response', {}).get('temperature', 0.7))

    # 缓存配置 - 优化版本
    ENABLE_CACHE = _config.get('cache', {}).get('enable', True)
    CACHE_EXPIRATION = int(_config.get('cache', {}).get('expiration', 2592000))  # 默认缓存30天

    # 多级缓存配置
    CACHE_LEVELS = {
        'hot': 86400,      # 热门问题缓存1天
        'normal': 604800,  # 普通问题缓存7天
        'cold': 2592000,   # 冷门问题缓存30天
    }

    # 缓存性能配置
    CACHE_MAX_CONNECTIONS = 50          # Redis最大连接数
    CACHE_RETRY_ON_TIMEOUT = True       # 超时重试
    CACHE_SOCKET_TIMEOUT = 5            # Socket超时时间
    CACHE_SOCKET_CONNECT_TIMEOUT = 5    # 连接超时时间
    CACHE_HEALTH_CHECK_INTERVAL = 30    # 健康检查间隔

    # 记录配置
    ENABLE_RECORD = _config.get('record', {}).get('enable', True)  # 是否记录问答到数据库

    # 数据库配置 - 支持环境变量
    # 优先使用环境变量，然后是配置文件，最后是默认值
    # Railway通常使用MYSQL_URL，也支持DATABASE_URL
    database_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
    if database_url:
        # 如果有MYSQL_URL或DATABASE_URL环境变量，处理并使用

        # 从DATABASE_URL解析数据库信息
        import urllib.parse as urlparse
        url = urlparse.urlparse(database_url)
        scheme = url.scheme or 'mysql'
        DB_TYPE = scheme.split('+')[0] if '+' in scheme else scheme
        DB_HOST = url.hostname
        DB_PORT = url.port or 3306
        DB_USER = url.username
        DB_PASSWORD = url.password
        DB_NAME = url.path[1:] if url.path else "railway"

        # 构建SQLAlchemy兼容的连接字符串，确保使用PyMySQL驱动
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?charset=utf8mb4"
            f"&autocommit=true"
            f"&connect_timeout=10"
            f"&read_timeout=30"
            f"&write_timeout=30"
        )
    else:
        # 使用配置文件或环境变量
        DB_TYPE = os.environ.get('DB_TYPE', _config.get('database', {}).get('type', "mysql"))
        DB_HOST = os.environ.get('DB_HOST', _config.get('database', {}).get('host', "localhost"))
        DB_PORT = int(os.environ.get('DB_PORT', _config.get('database', {}).get('port', 3306)))
        DB_USER = os.environ.get('DB_USER', _config.get('database', {}).get('user', "root"))
        DB_PASSWORD = os.environ.get('DB_PASSWORD', _config.get('database', {}).get('password', "123456"))
        DB_NAME = os.environ.get('DB_NAME', _config.get('database', {}).get('name', "ocs_qa"))

        # 数据库连接字符串 - 优化版本
        SQLALCHEMY_DATABASE_URI = (
            f"{DB_TYPE}+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?charset=utf8mb4"
            f"&autocommit=true"
            f"&connect_timeout=10"
            f"&read_timeout=30"
            f"&write_timeout=30"
            f"&max_allowed_packet=16777216"
            f"&sql_mode=STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO"
        )

    # 数据库连接池配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 25,
        'pool_timeout': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 35,
        'echo': False,
        'echo_pool': False,
        'pool_reset_on_return': 'rollback',
        'isolation_level': 'READ_COMMITTED',
    }

    # Redis配置
    REDIS_HOST = os.environ.get('REDIS_HOST', _config.get('redis', {}).get('host', "localhost"))
    REDIS_PORT = int(os.environ.get('REDIS_PORT', _config.get('redis', {}).get('port', 6379)))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', _config.get('redis', {}).get('password', ""))
    REDIS_DB = int(os.environ.get('REDIS_DB', _config.get('redis', {}).get('db', 0)))
    REDIS_ENABLED = os.environ.get('REDIS_ENABLED', str(_config.get('redis', {}).get('enabled', True))).lower() == 'true'

    # SQLAlchemy配置
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ECHO = False
