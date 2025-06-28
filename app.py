#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EduBrain AI - 智能题库系统
主应用入口文件
"""

import os
import sys
from flask import Flask, render_template, jsonify, request, make_response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入配置和服务
# 检测是否在容器/云环境中运行
def is_container_environment():
    """检测是否在容器或云环境中运行"""
    indicators = [
        os.environ.get('RAILWAY_STATIC_URL'),  # Railway静态URL
        os.environ.get('RAILWAY_PROJECT_ID'),  # Railway项目ID
        os.environ.get('RAILWAY_SERVICE_ID'),  # Railway服务ID
        os.environ.get('PORT'),  # 云平台通常设置PORT环境变量
        os.path.exists('/.dockerenv'),  # Docker容器标识文件
        os.environ.get('CONTAINER'),  # 通用容器环境变量
        os.environ.get('KUBERNETES_SERVICE_HOST'),  # Kubernetes环境
    ]
    return any(indicators)

if is_container_environment():
    # 容器/云环境，直接使用load_config避免循环导入
    from load_config import Config
    print("✅ 容器环境：使用load_config模块导入Config")

    # 检查MYSQL_URL环境变量
    mysql_url = os.environ.get('MYSQL_URL')
    database_url=os.environ.get('DATABASE_URL')
    if mysql_url :
        print(f"✅ 检测到MYSQL_URL: {mysql_url}...")
    else:
        print(f"✅ 检测到DATABASE_URL: {database_url}...")
else:
    # 本地开发环境，尝试使用config模块
    try:
        from config import Config
        print("✅ 本地环境：成功从config模块导入Config")
    except ImportError as e:
        print(f"❌ 从config模块导入失败: {e}")
        # 备用方案
        from load_config import Config
        print("✅ 备用方案：使用load_config模块导入Config")
from models.models import init_db
from utils.logger import setup_logger
from utils.auth import init_auth
from utils.db_monitor import init_db_monitor
from utils.system_monitor import init_system_monitor

# 导入路由模块
from routes.auth import auth_bp
from routes.questions import questions_bp
from routes.question_management import question_management_bp
from routes.api_proxy_management import api_proxy_management_bp
from routes.proxy_pool import proxy_pool_bp
from routes.concurrent_management import concurrent_management_bp
from routes.logs import logs_bp
from routes.settings import settings_bp
from routes.cache_management import cache_bp
from routes.db_monitor import db_monitor_bp
from routes.system_monitor import system_monitor_bp
from routes.table_management import table_management_bp

# 导入服务
from services.cache import get_cache
from services.search_service import get_search_service
from services.api_proxy_pool import get_api_proxy_pool

def create_app():
    """创建Flask应用实例"""
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(Config)

    # 设置请求超时配置
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1小时

    # 启用CORS - 搜题接口完全开放
    CORS(app, resources={
        # 搜题接口 - 完全开放，无需token
        r"/api/questions/search": {
            "origins": "*",  # 允许所有域名
            "methods": ["POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Origin", "Accept", "Authorization", "X-Access-Token"],
            "supports_credentials": False,  # 不需要凭证
            "max_age": 86400
        },
        # 其他API接口 - 需要认证
        r"/api/*": {
            "origins": [
                # 本地开发环境
                "http://localhost:3000",
                "http://localhost:8080",
                "http://localhost:8080",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8080",
                "http://127.0.0.1:8080",
                # 在线教育平台
                "https://www.icourse163.org",
                "https://icourse163.org",
                "https://www.xuetangx.com",
                "https://xuetangx.com",
                "https://www.zhihuishu.com",
                "https://zhihuishu.com",
                "https://www.chaoxing.com",
                "https://chaoxing.com"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-Access-Token",
                "Origin",
                "Accept"
            ],
            "supports_credentials": True,
            "max_age": 86400
        }
    })

    # 简化的OPTIONS处理 - 搜题接口无需token验证
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = make_response()

            # 对搜题接口完全开放
            if request.path.startswith('/api/questions/search'):
                response.headers.add("Access-Control-Allow-Origin", "*")
                response.headers.add('Access-Control-Allow-Headers', "Content-Type,Origin,Accept,Authorization,X-Access-Token")
                response.headers.add('Access-Control-Allow-Methods', "POST,OPTIONS")
                response.headers.add('Access-Control-Max-Age', '86400')
                return response

            # 其他API接口的CORS处理
            origin = request.headers.get('Origin')
            allowed_origins = [
                "http://localhost:3000", "http://localhost:8080", "http://localhost:8081",
                "http://127.0.0.1:3000", "http://127.0.0.1:8080", "http://127.0.0.1:8081",
                "https://www.icourse163.org", "https://icourse163.org",
                "https://www.xuetangx.com", "https://xuetangx.com",
                "https://www.zhihuishu.com", "https://zhihuishu.com",
                "https://www.chaoxing.com", "https://chaoxing.com"
            ]

            if origin in allowed_origins:
                response.headers.add("Access-Control-Allow-Origin", origin)
                response.headers.add('Access-Control-Allow-Headers',
                    "Content-Type,Authorization,X-Requested-With,X-Access-Token,Origin,Accept")
                response.headers.add('Access-Control-Allow-Methods',
                    "GET,POST,PUT,DELETE,OPTIONS,HEAD")
                response.headers.add('Access-Control-Allow-Credentials', 'true')
                response.headers.add('Access-Control-Max-Age', '86400')

            return response

    # 设置日志
    setup_logger(app)

    # 初始化数据库
    init_db(app)

    # 初始化数据库监控
    with app.app_context():
        from models.models import db
        db_monitor = init_db_monitor(db)
        # 使用 print 确保正确的日志级别
        print("✅ 数据库连接池监控器已启动")
        app.logger.info("数据库连接池监控器已启动")

    # 初始化系统监控
    system_monitor = init_system_monitor()
    print("✅ 系统性能监控器已启动")
    app.logger.info("系统性能监控器已启动")

    # 初始化认证
    init_auth(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册额外路由
    register_additional_routes(app)

    # 注册错误处理器
    register_error_handlers(app)

    # 注册中间件
    register_middleware(app)

    # 记录系统启动日志
    with app.app_context():
        from routes.logs import add_system_log
        add_system_log(
            level='info',
            source='system',
            message='系统启动完成',
            context={'version': '1.0.0', 'environment': app.config.get('ENV', 'development')}
        )

    return app

def init_services(app):
    """初始化服务"""
    with app.app_context():
        # 初始化缓存服务
        cache = get_cache()
        app.logger.info(f"缓存服务初始化完成: {cache.get_stats()}")

        # 初始化搜索服务
        search_service = get_search_service()
        app.logger.info("搜索服务初始化完成")

        # 初始化API代理池
        proxy_pool = get_api_proxy_pool()
        app.logger.info(f"API代理池初始化完成: {proxy_pool.get_pool_status()}")

def register_blueprints(app):
    """注册所有蓝图"""
    # API路由
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(questions_bp, url_prefix='/api/questions')
    app.register_blueprint(question_management_bp, url_prefix='/api/question-management')
    app.register_blueprint(api_proxy_management_bp, url_prefix='/api/api-proxy-management')
    app.register_blueprint(proxy_pool_bp, url_prefix='/api/proxy-pool')
    app.register_blueprint(concurrent_management_bp, url_prefix='/api/concurrent')
    app.register_blueprint(logs_bp, url_prefix='/api/logs')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(cache_bp, url_prefix='/api/cache')
    app.register_blueprint(db_monitor_bp, url_prefix='/api/db-monitor')
    app.register_blueprint(system_monitor_bp, url_prefix='/api/system-monitor')
    app.register_blueprint(table_management_bp, url_prefix='/api/table-management')

    # API 文档数据接口
    @app.route('/api/docs-info')
    def api_docs_info():
        """API 文档信息 - 供前端使用"""
        return {
            'title': 'EduBrain AI 数据库管理 API',
            'version': '1.0.0',
            'description': '完整的数据库管理和监控 API',
            'base_url': request.host_url.rstrip('/'),
            'total_endpoints': 23,
            'categories': [
                {
                    'name': '数据库监控',
                    'description': '数据库连接、统计、健康检查等监控功能',
                    'endpoint_count': 8
                },
                {
                    'name': '表管理',
                    'description': '数据表的查看、管理、查询、维护等功能',
                    'endpoint_count': 15
                }
            ],
            'authentication': {
                'required': False,
                'type': 'none',
                'note': '当前所有接口无需认证（测试模式）'
            },
            'database': {
                'type': 'MySQL',
                'provider': 'Railway',
                'connection': '100% 真实数据库对接'
            }
        }

    @app.route('/api/docs-endpoints')
    def api_docs_endpoints():
        """API 接口列表 - 供前端使用"""
        return {
            'db_monitor': [
                {
                    'method': 'POST',
                    'path': '/api/db-monitor/test-connection',
                    'name': '测试数据库连接',
                    'description': '测试数据库连接状态，获取连接信息和性能指标',
                    'auth_required': False,
                    'parameters': [],
                    'response_example': {
                        'success': True,
                        'data': {
                            'database_info': {
                                'host': 'interchange.proxy.rlwy.net',
                                'port': 49225,
                                'database': 'railway'
                            },
                            'connection_time': 45.67,
                            'database_version': '8.0.35',
                            'connection_status': 'success'
                        }
                    }
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/stats',
                    'name': '获取数据库统计',
                    'description': '获取数据库连接池统计、查询统计和性能指标',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/health',
                    'name': '数据库健康检查',
                    'description': '检查数据库健康状态和连接质量',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/optimize',
                    'name': '获取优化建议',
                    'description': '基于实际数据库分析生成优化建议',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/query-stats',
                    'name': '查询统计信息',
                    'description': '获取详细的查询统计信息',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/pool-status',
                    'name': '连接池状态',
                    'description': '获取数据库连接池详细状态',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/db-monitor/railway-info',
                    'name': 'Railway 环境信息',
                    'description': '获取 Railway 环境和数据库配置信息',
                    'auth_required': False
                },
                {
                    'method': 'POST',
                    'path': '/api/db-monitor/reset-stats',
                    'name': '重置统计信息',
                    'description': '重置数据库监控统计数据',
                    'auth_required': False
                }
            ],
            'table_management': [
                {
                    'method': 'GET',
                    'path': '/api/table-management/tables',
                    'name': '获取所有表',
                    'description': '获取数据库中所有表的列表和基本信息',
                    'auth_required': False
                },
                {
                    'method': 'GET',
                    'path': '/api/table-management/tables/{table_name}/structure',
                    'name': '获取表结构',
                    'description': '获取指定表的结构信息',
                    'auth_required': False,
                    'parameters': [
                        {
                            'name': 'table_name',
                            'type': 'string',
                            'location': 'path',
                            'required': True,
                            'description': '表名'
                        }
                    ]
                },
                {
                    'method': 'GET',
                    'path': '/api/table-management/tables/{table_name}/data',
                    'name': '获取表数据',
                    'description': '获取指定表的数据（支持分页）',
                    'auth_required': False,
                    'parameters': [
                        {
                            'name': 'table_name',
                            'type': 'string',
                            'location': 'path',
                            'required': True,
                            'description': '表名'
                        },
                        {
                            'name': 'page',
                            'type': 'integer',
                            'location': 'query',
                            'required': False,
                            'default': 1,
                            'description': '页码'
                        },
                        {
                            'name': 'per_page',
                            'type': 'integer',
                            'location': 'query',
                            'required': False,
                            'default': 20,
                            'description': '每页数量'
                        }
                    ]
                },
                {
                    'method': 'POST',
                    'path': '/api/table-management/query',
                    'name': '执行SQL查询',
                    'description': '执行自定义的SELECT查询语句',
                    'auth_required': False,
                    'parameters': [
                        {
                            'name': 'sql',
                            'type': 'string',
                            'location': 'body',
                            'required': True,
                            'description': 'SQL查询语句（只支持SELECT）'
                        },
                        {
                            'name': 'limit',
                            'type': 'integer',
                            'location': 'body',
                            'required': False,
                            'default': 100,
                            'description': '结果限制数量'
                        }
                    ],
                    'request_example': {
                        'sql': 'SELECT * FROM information_schema.tables LIMIT 5',
                        'limit': 100
                    }
                }
            ]
        }

    @app.route('/api/docs-categories')
    def api_docs_categories():
        """API 分类列表 - 供前端使用"""
        return {
            'categories': [
                {
                    'id': 'db-monitor',
                    'name': '数据库监控',
                    'description': '数据库连接、统计、健康检查等监控功能',
                    'icon': '📊',
                    'color': '#007bff',
                    'endpoints': [
                        'test-connection', 'stats', 'health', 'optimize',
                        'query-stats', 'pool-status', 'railway-info', 'reset-stats'
                    ]
                },
                {
                    'id': 'table-management',
                    'name': '表管理',
                    'description': '数据表的查看、管理、查询、维护等功能',
                    'icon': '🗄️',
                    'color': '#28a745',
                    'endpoints': [
                        'tables', 'structure', 'columns', 'indexes', 'data',
                        'query', 'export', 'analyze', 'optimize', 'repair'
                    ]
                }
            ]
        }

    @app.route('/api/docs-endpoints/<category>')
    def api_docs_endpoints_by_category(category):
        """按分类获取接口列表 - 供前端使用"""
        all_endpoints = api_docs_endpoints().get_json()

        if category == 'db-monitor':
            return {'endpoints': all_endpoints.get('db_monitor', [])}
        elif category == 'table-management':
            return {'endpoints': all_endpoints.get('table_management', [])}
        else:
            return {'error': 'Category not found'}, 404

    @app.route('/api/docs-search')
    def api_docs_search():
        """搜索 API 接口 - 供前端使用"""
        query = request.args.get('q', '').lower()
        if not query:
            return {'results': []}

        all_endpoints = api_docs_endpoints().get_json()
        results = []

        # 搜索数据库监控接口
        for endpoint in all_endpoints.get('db_monitor', []):
            if (query in endpoint.get('name', '').lower() or
                query in endpoint.get('description', '').lower() or
                query in endpoint.get('path', '').lower()):
                endpoint['category'] = '数据库监控'
                results.append(endpoint)

        # 搜索表管理接口
        for endpoint in all_endpoints.get('table_management', []):
            if (query in endpoint.get('name', '').lower() or
                query in endpoint.get('description', '').lower() or
                query in endpoint.get('path', '').lower()):
                endpoint['category'] = '表管理'
                results.append(endpoint)

        return {
            'query': query,
            'total': len(results),
            'results': results
        }

    @app.route('/api/docs-examples')
    def api_docs_examples():
        """API 使用示例 - 供前端使用"""
        return {
            'javascript': {
                'test_connection': '''// 测试数据库连接
fetch('/api/db-monitor/test-connection', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
.then(response => response.json())
.then(data => console.log(data));''',

                'get_tables': '''// 获取所有表
fetch('/api/table-management/tables')
.then(response => response.json())
.then(data => console.log(data));''',

                'execute_query': '''// 执行查询
fetch('/api/table-management/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    sql: 'SELECT * FROM information_schema.tables LIMIT 5'
  })
})
.then(response => response.json())
.then(data => console.log(data));'''
            },
            'curl': {
                'test_connection': '''# 测试数据库连接
curl -X POST https://ocsjs-ai-backend-production.up.railway.app/api/db-monitor/test-connection \\
  -H "Content-Type: application/json"''',

                'get_tables': '''# 获取所有表
curl https://ocsjs-ai-backend-production.up.railway.app/api/table-management/tables''',

                'execute_query': '''# 执行查询
curl -X POST https://ocsjs-ai-backend-production.up.railway.app/api/table-management/query \\
  -H "Content-Type: application/json" \\
  -d '{"sql": "SELECT * FROM information_schema.tables LIMIT 5"}'
'''
            },
            'python': {
                'test_connection': '''# 测试数据库连接
import requests

response = requests.post(
    'https://ocsjs-ai-backend-production.up.railway.app/api/db-monitor/test-connection',
    headers={'Content-Type': 'application/json'}
)
print(response.json())''',

                'execute_query': '''# 执行查询
import requests

response = requests.post(
    'https://ocsjs-ai-backend-production.up.railway.app/api/table-management/query',
    headers={'Content-Type': 'application/json'},
    json={
        'sql': 'SELECT * FROM information_schema.tables LIMIT 5'
    }
)
print(response.json())'''
            }
        }

    @app.route('/api/docs-status')
    def api_docs_status():
        """API 状态信息 - 供前端使用"""
        return {
            'status': 'active',
            'version': '1.0.0',
            'last_updated': '2025-06-28',
            'total_endpoints': 23,
            'authentication_required': False,
            'database_connection': 'Railway MySQL',
            'features': [
                '100% 数据库对接',
                '无需认证访问',
                '实时数据查询',
                '表管理功能',
                '性能监控',
                '优化建议'
            ],
            'supported_operations': [
                'SELECT 查询',
                '表结构查看',
                '数据导出',
                '表优化',
                '连接监控'
            ]
        }

def register_error_handlers(app):
    """注册错误处理器"""

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/') or request.path.startswith('/logs/'):
            return jsonify({
                'success': False,
                'message': '接口不存在',
                'error': 'Not Found'
            }), 404
        # 对于非API请求，返回简单的404响应
        return jsonify({
            'success': False,
            'message': '页面不存在',
            'error': 'Not Found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'message': '服务器内部错误',
                'error': 'Internal Server Error'
            }), 500
        return render_template('error.html', error=error), 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'message': error.description,
                'error': error.name
            }), error.code
        return render_template('error.html', error=error), error.code

def register_middleware(app):
    """注册中间件"""

    @app.before_request
    def before_request():
        """请求前处理"""
        # 记录请求日志到控制台
        if not request.path.startswith('/static/'):
            app.logger.info(f"{request.method} {request.path} - {request.remote_addr}")

    @app.after_request
    def after_request(response):
        """请求后处理"""
        # 添加安全头
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # 记录响应日志到控制台和系统日志
        if not request.path.startswith('/static/') and not request.path.startswith('/api/logs/'):
            app.logger.info(f"{request.method} {request.path} - {response.status_code}")

            # 记录到系统日志（避免API请求日志无限循环）
            if not request.path.startswith('/api/logs/'):
                from routes.logs import add_system_log

                # 根据状态码确定日志级别
                if response.status_code >= 500:
                    level = 'error'
                elif response.status_code >= 400:
                    level = 'warn'
                else:
                    level = 'info'

                add_system_log(
                    level=level,
                    source='api',
                    message=f'{request.method} {request.path} - {response.status_code}',
                    ip_address=request.remote_addr,
                    context={
                        'method': request.method,
                        'path': request.path,
                        'status_code': response.status_code,
                        'user_agent': request.headers.get('User-Agent', '')
                    }
                )

        return response

def register_additional_routes(app):
    """注册额外的路由"""

    @app.route('/')
    def index():
        """主页"""
        return jsonify({
            'message': 'EduBrain AI - 智能题库系统',
            'version': '1.0.0',
            'status': 'running'
        })

    @app.route('/health')
    def health_check():
        """健康检查接口"""
        import time
        return jsonify({
            'status': 'healthy',
            'message': 'EduBrain AI服务运行正常',
            'timestamp': int(time.time())
        })

    @app.route('/api/system/info')
    def system_info():
        """系统信息接口"""
        import time
        import psutil
        import os

        try:
            # 获取系统根目录（Windows: C:\, Linux: /）
            if os.name == 'nt':  # Windows
                disk_path = 'C:\\'
            else:  # Linux/Unix
                disk_path = '/'

            # 添加超时保护
            cpu_percent = psutil.cpu_percent(interval=0.1)  # 快速获取CPU使用率
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage(disk_path)

            return jsonify({
                'success': True,
                'data': {
                    'system': {
                        'cpu_percent': round(cpu_percent, 1),
                        'memory_percent': round(memory_info.percent, 1),
                        'disk_percent': round(disk_info.percent, 1),
                        'uptime': round(time.time() - psutil.boot_time(), 0)
                    },
                    'application': {
                        'name': 'EduBrain AI',
                        'version': '1.0.0',
                        'environment': app.config.get('ENV', 'development')
                    }
                }
            })
        except Exception as e:
            # 如果获取系统信息失败，返回默认值
            return jsonify({
                'success': True,
                'data': {
                    'system': {
                        'cpu_percent': 0,
                        'memory_percent': 0,
                        'disk_percent': 0,
                        'uptime': 0
                    },
                    'application': {
                        'name': 'EduBrain AI',
                        'version': '1.0.0',
                        'environment': app.config.get('ENV', 'development')
                    },
                    'error': str(e)
                }
            })

if __name__ == '__main__':
    import time
    import os

    # 创建应用实例
    app = create_app()

    # 获取端口号，优先使用环境变量
    port = int(os.environ.get('PORT', 5000))

    # 开发环境配置
    if app.config.get('ENV') == 'development':
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True,
            load_dotenv=False  # 禁用自动加载.env文件
        )
    else:
        # 生产环境使用gunicorn等WSGI服务器
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,
            load_dotenv=False  # 禁用自动加载.env文件
        )
