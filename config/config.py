# -*- coding: utf-8 -*-
"""
配置文件
"""
import os
import json


# 加载JSON配置文件
def load_config():
    # 从项目根目录加载配置文件
    # __file__ 是 config/config.py，需要向上两级到达项目根目录
    # config/config.py -> config/ -> 项目根目录
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_file = os.path.join(project_root, 'config.json')

    try:
        if os.path.exists(config_file):
            # 尝试多种编码方式
            for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'cp1252']:
                try:
                    with open(config_file, 'r', encoding=encoding) as f:
                        return json.load(f)
                except UnicodeDecodeError:
                    continue
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误 (编码: {encoding}): {str(e)}")
                    continue
            print(f"无法读取配置文件，尝试了多种编码方式")
    except Exception as e:
        print(f"读取配置文件出错: {str(e)}")
    return {}

# 全局配置
_config = load_config()

# 基础配置
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
    if os.environ.get('DATABASE_URL'):
        # 如果有DATABASE_URL环境变量，直接使用
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
        # 从DATABASE_URL解析数据库信息
        import urllib.parse as urlparse
        url = urlparse.urlparse(SQLALCHEMY_DATABASE_URI)
        scheme = str(url.scheme or 'mysql')
        DB_TYPE = scheme.split('+')[0] if '+' in scheme else scheme
        DB_HOST = url.hostname
        DB_PORT = url.port or 3306
        DB_USER = url.username
        DB_PASSWORD = url.password
        DB_NAME = url.path[1:] if url.path else "ocs_qa"
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

    # 数据库连接池配置 - 增强版本
    SQLALCHEMY_ENGINE_OPTIONS = {
        # 基础连接池配置
        'pool_size': 25,                    # 连接池大小（增加到25）
        'pool_timeout': 20,                 # 获取连接超时时间（减少到20秒）
        'pool_recycle': 3600,              # 连接回收时间（1小时）
        'pool_pre_ping': True,             # 连接前ping检查
        'max_overflow': 35,                # 最大溢出连接数（增加到35）

        # 性能优化配置
        'echo': False,                     # 不打印SQL语句
        'echo_pool': False,                # 不打印连接池信息
        'pool_reset_on_return': 'commit',  # 连接返回时重置方式

        # 连接质量配置
        'pool_reset_on_return': 'rollback', # 更安全的重置方式
        'isolation_level': 'READ_COMMITTED', # 事务隔离级别

        # MySQL特定优化
        'connect_args': {
            'charset': 'utf8mb4',
            'autocommit': False,           # 禁用自动提交，提高性能
            'connect_timeout': 10,         # 连接超时
            'read_timeout': 30,            # 读取超时
            'write_timeout': 30,           # 写入超时
            'max_allowed_packet': 16777216, # 最大数据包大小
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'", # SQL模式
            'use_unicode': True,           # 使用Unicode
            'binary_prefix': True,         # 二进制前缀
        }
    }

    # 数据库会话配置
    SQLALCHEMY_SESSION_OPTIONS = {
        'autoflush': True,                 # 自动刷新
        'autocommit': False,               # 禁用自动提交
        'expire_on_commit': False,         # 提交后不过期对象
    }

    # 数据库性能监控配置
    SQLALCHEMY_RECORD_QUERIES = True      # 记录查询（开发环境）
    SQLALCHEMY_TRACK_MODIFICATIONS = False # 禁用修改跟踪以提高性能

    # Redis配置 - 优化版本
    REDIS_ENABLED = _config.get('redis', {}).get('enabled', True)  # 默认启用Redis
    REDIS_HOST = _config.get('redis', {}).get('host', "localhost")
    REDIS_PORT = int(_config.get('redis', {}).get('port', 6379))
    REDIS_PASSWORD = _config.get('redis', {}).get('password', "")
    REDIS_DB = int(_config.get('redis', {}).get('db', 0))

    # Redis连接池配置
    REDIS_CONNECTION_POOL = {
        'max_connections': CACHE_MAX_CONNECTIONS,
        'retry_on_timeout': CACHE_RETRY_ON_TIMEOUT,
        'socket_timeout': CACHE_SOCKET_TIMEOUT,
        'socket_connect_timeout': CACHE_SOCKET_CONNECT_TIMEOUT,
        'health_check_interval': CACHE_HEALTH_CHECK_INTERVAL,
        'decode_responses': True,
        'encoding': 'utf-8',
        'socket_keepalive': True,
        'socket_keepalive_options': {},
    }

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls', 'csv', 'json'}

def update_config(new_config):
    """更新系统配置"""
    import json

    # 更新运行时配置
    Config.ENABLE_CACHE = new_config.get('ENABLE_CACHE', Config.ENABLE_CACHE)
    Config.CACHE_EXPIRATION = new_config.get('CACHE_EXPIRATION', Config.CACHE_EXPIRATION)
    Config.ENABLE_RECORD = new_config.get('ENABLE_RECORD', Config.ENABLE_RECORD)
    Config.ACCESS_TOKEN = new_config.get('ACCESS_TOKEN', Config.ACCESS_TOKEN)

    # 更新第三方代理池配置
    if 'THIRD_PARTY_APIS' in new_config:
        Config.THIRD_PARTY_APIS = new_config['THIRD_PARTY_APIS']

    config_data = {
        'service': {
            'host': Config.HOST,
            'port': Config.PORT,
            'debug': Config.DEBUG
        },
        'third_party_apis': Config.THIRD_PARTY_APIS,
        'cache': {
            'enable': Config.ENABLE_CACHE,
            'expiration': Config.CACHE_EXPIRATION
        },
        'security': {
            'access_token': Config.ACCESS_TOKEN,
            'secret_key': Config.SECRET_KEY if hasattr(Config, 'SECRET_KEY') else os.urandom(24).hex()
        },
        'database': {
            'type': Config.DB_TYPE,
            'host': Config.DB_HOST,
            'port': Config.DB_PORT,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'name': Config.DB_NAME
        },
        'redis': {
            'enabled': Config.REDIS_ENABLED,
            'host': Config.REDIS_HOST,
            'port': Config.REDIS_PORT,
            'password': Config.REDIS_PASSWORD,
            'db': Config.REDIS_DB
        },
        'record': {
            'enable': Config.ENABLE_RECORD
        }
    }

    try:
        # 获取项目根目录路径
        # config/config.py -> config/ -> 项目根目录
        project_root = os.path.dirname(os.path.dirname(__file__))
        config_file = os.path.join(project_root, 'config.json')

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

        return True
    except Exception as e:
        raise e
