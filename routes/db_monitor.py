# -*- coding: utf-8 -*-
"""
数据库监控API路由
"""
from flask import Blueprint, jsonify, request
from utils.auth import token_required
from utils.db_monitor import get_db_monitor
from utils.response_handler import success_response, error_response, handle_exception
from utils.logger import get_logger

logger = get_logger(__name__)

db_monitor_bp = Blueprint('db_monitor', __name__, url_prefix='/api/db-monitor')

@db_monitor_bp.route('/stats', methods=['GET'])
@token_required
def get_db_stats(current_user):
    """获取数据库连接池统计信息"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        stats = monitor.get_stats()
        return success_response(data=stats, message='获取数据库统计成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_db_stats',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/health', methods=['GET'])
@token_required
def get_db_health(current_user):
    """获取数据库健康状态"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        stats = monitor.get_stats()
        health_status = stats.get('health_status', 'unknown')
        
        # 构建健康状态响应
        health_data = {
            'status': health_status,
            'pool_utilization': stats['pool_stats']['active_connections'] / max(stats['pool_stats']['pool_size'], 1),
            'query_success_rate': 1 - (stats['query_stats']['failed_queries'] / max(stats['query_stats']['total_queries'], 1)),
            'avg_query_time': stats['query_stats']['avg_query_time'],
            'recommendations': monitor.optimize_pool()
        }
        
        return success_response(data=health_data, message='获取数据库健康状态成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_db_health',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/optimize', methods=['GET'])
@token_required
def get_optimization_recommendations(current_user):
    """获取数据库优化建议"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        recommendations = monitor.optimize_pool()
        stats = monitor.get_stats()
        
        optimization_data = {
            'recommendations': recommendations,
            'current_config': {
                'pool_size': stats['pool_stats']['pool_size'],
                'active_connections': stats['pool_stats']['active_connections'],
                'overflow_connections': stats['pool_stats']['overflow_connections']
            },
            'performance_metrics': {
                'total_queries': stats['query_stats']['total_queries'],
                'slow_queries': stats['query_stats']['slow_queries'],
                'failed_queries': stats['query_stats']['failed_queries'],
                'avg_query_time': stats['query_stats']['avg_query_time']
            }
        }
        
        return success_response(data=optimization_data, message='获取优化建议成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_optimization_recommendations',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/reset-stats', methods=['POST'])
@token_required
def reset_db_stats(current_user):
    """重置数据库统计信息"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        monitor.reset_stats()
        
        logger.info(f"用户 {current_user.username} 重置了数据库统计信息")
        
        return success_response(message='数据库统计信息已重置')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'reset_db_stats',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/test-connection', methods=['POST'])
@token_required
def test_db_connection(current_user):
    """测试数据库连接"""
    try:
        from config.config import SQLALCHEMY_DATABASE_URI, DB_HOST, DB_PORT, DB_NAME, DB_USER
        from sqlalchemy import create_engine, text
        import time

        # 获取数据库配置信息
        db_info = {
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_NAME,
            'user': DB_USER,
            'connection_string': SQLALCHEMY_DATABASE_URI.split('@')[1] if '@' in SQLALCHEMY_DATABASE_URI else 'Railway DB'
        }

        # 测试连接
        start_time = time.time()
        engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)

        with engine.connect() as conn:
            # 执行简单查询测试
            result = conn.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()

            # 获取数据库版本
            version_result = conn.execute(text("SELECT VERSION() as version"))
            db_version = version_result.fetchone()[0]

        connection_time = time.time() - start_time

        # 测试监控器
        monitor = get_db_monitor()
        monitor_status = "已初始化" if monitor else "未初始化"

        return success_response(
            data={
                'database_info': db_info,
                'connection_time': round(connection_time * 1000, 2),  # 毫秒
                'database_version': db_version,
                'test_query_result': test_result[0] if test_result else None,
                'monitor_status': monitor_status,
                'connection_status': 'success'
            },
            message='数据库连接测试成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'test_db_connection',
            'user_id': current_user.id if current_user else None,
            'error_details': str(e)
        })

@db_monitor_bp.route('/query-stats', methods=['GET'])
@token_required
def get_query_stats(current_user):
    """获取查询统计信息"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        stats = monitor.get_stats()
        query_stats = stats['query_stats']
        
        # 计算额外的统计信息
        total_queries = query_stats['total_queries']
        if total_queries > 0:
            slow_query_rate = query_stats['slow_queries'] / total_queries
            failure_rate = query_stats['failed_queries'] / total_queries
        else:
            slow_query_rate = 0
            failure_rate = 0
        
        enhanced_stats = {
            **query_stats,
            'slow_query_rate': slow_query_rate,
            'failure_rate': failure_rate,
            'success_rate': 1 - failure_rate
        }
        
        return success_response(data=enhanced_stats, message='获取查询统计成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_query_stats',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/pool-status', methods=['GET'])
@token_required
def get_pool_status(current_user):
    """获取连接池状态"""
    try:
        monitor = get_db_monitor()
        if not monitor:
            return error_response('数据库监控器未初始化', status_code=503)
        
        stats = monitor.get_stats()
        pool_stats = stats['pool_stats']
        
        # 计算利用率
        pool_utilization = pool_stats['active_connections'] / max(pool_stats['pool_size'], 1)
        
        # 状态分类
        if pool_utilization > 0.9:
            status = 'critical'
        elif pool_utilization > 0.7:
            status = 'warning'
        else:
            status = 'normal'
        
        pool_status = {
            **pool_stats,
            'utilization': pool_utilization,
            'status': status,
            'has_overflow': pool_stats['overflow_connections'] > 0
        }
        
        return success_response(data=pool_status, message='获取连接池状态成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_pool_status',
            'user_id': current_user.id if current_user else None
        })

@db_monitor_bp.route('/railway-info', methods=['GET'])
@token_required
def get_railway_info(current_user):
    """获取 Railway 环境信息"""
    try:
        import os

        # 检测是否在 Railway 环境
        is_railway = bool(
            os.environ.get('RAILWAY_PROJECT_ID') or
            os.environ.get('RAILWAY_ENVIRONMENT_ID')
        )

        if is_railway:
            railway_info = {
                'environment': 'Railway',
                'project_name': os.environ.get('RAILWAY_PROJECT_NAME'),
                'project_id': os.environ.get('RAILWAY_PROJECT_ID'),
                'environment_name': os.environ.get('RAILWAY_ENVIRONMENT_NAME'),
                'environment_id': os.environ.get('RAILWAY_ENVIRONMENT_ID'),
                'service_name': os.environ.get('RAILWAY_SERVICE_NAME'),
                'service_id': os.environ.get('RAILWAY_SERVICE_ID'),
                'tcp_proxy_domain': os.environ.get('RAILWAY_TCP_PROXY_DOMAIN'),
                'tcp_proxy_port': os.environ.get('RAILWAY_TCP_PROXY_PORT'),
                'private_domain': os.environ.get('RAILWAY_PRIVATE_DOMAIN'),
                'volume_info': {
                    'volume_id': os.environ.get('RAILWAY_VOLUME_ID'),
                    'volume_name': os.environ.get('RAILWAY_VOLUME_NAME'),
                    'mount_path': os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
                },
                'mysql_vars': {
                    'mysql_database': os.environ.get('MYSQL_DATABASE'),
                    'mysql_user': os.environ.get('MYSQLUSER'),
                    'mysql_host': os.environ.get('MYSQLHOST'),
                    'mysql_port': os.environ.get('MYSQLPORT'),
                    'has_mysql_url': bool(os.environ.get('MYSQL_URL')),
                    'has_database_url': bool(os.environ.get('DATABASE_URL'))
                }
            }
        else:
            railway_info = {
                'environment': 'Local',
                'message': '当前运行在本地环境'
            }

        return success_response(data=railway_info, message='获取环境信息成功')

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_railway_info',
            'user_id': current_user.id if current_user else None
        })

# 注册错误处理器
@db_monitor_bp.errorhandler(Exception)
def handle_db_monitor_error(error):
    """处理数据库监控相关错误"""
    logger.error(f"数据库监控API错误: {str(error)}")
    return error_response('数据库监控服务异常', status_code=500)
