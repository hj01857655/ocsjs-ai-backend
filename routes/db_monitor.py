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
    """获取数据库优化建议（基于实际数据库查询）"""
    try:
        from sqlalchemy import text

        recommendations = []
        optimization_score = 100
        database_analysis = {}

        with db.engine.connect() as conn:
            # 1. 检查表状态和大小
            tables_query = text("""
                SELECT
                    table_name,
                    table_rows,
                    data_length,
                    index_length,
                    (data_length + index_length) as total_size,
                    data_free
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY (data_length + index_length) DESC
                LIMIT 10
            """)

            tables_result = conn.execute(tables_query)
            large_tables = []
            total_fragmentation = 0

            for row in tables_result.fetchall():
                table_info = {
                    'name': row[0],
                    'rows': row[1] or 0,
                    'data_size': row[2] or 0,
                    'index_size': row[3] or 0,
                    'total_size': row[4] or 0,
                    'fragmentation': row[5] or 0
                }
                large_tables.append(table_info)
                total_fragmentation += table_info['fragmentation']

                # 检查大表
                if table_info['total_size'] > 100 * 1024 * 1024:  # 100MB
                    recommendations.append(f"表 {table_info['name']} 较大({table_info['total_size']//1024//1024}MB)，建议考虑分区或归档")
                    optimization_score -= 5

                # 检查碎片
                if table_info['fragmentation'] > 10 * 1024 * 1024:  # 10MB
                    recommendations.append(f"表 {table_info['name']} 存在碎片({table_info['fragmentation']//1024//1024}MB)，建议执行 OPTIMIZE TABLE")
                    optimization_score -= 3

            # 2. 检查数据库配置
            variables_query = text("""
                SHOW VARIABLES WHERE Variable_name IN (
                    'innodb_buffer_pool_size',
                    'query_cache_size',
                    'max_connections',
                    'innodb_log_file_size',
                    'key_buffer_size'
                )
            """)

            variables_result = conn.execute(variables_query)
            db_config = {}

            for row in variables_result.fetchall():
                db_config[row[0]] = row[1]

            # 分析配置
            if 'innodb_buffer_pool_size' in db_config:
                buffer_pool_size = int(db_config['innodb_buffer_pool_size'])
                if buffer_pool_size < 128 * 1024 * 1024:  # 128MB
                    recommendations.append("InnoDB缓冲池大小较小，建议增加 innodb_buffer_pool_size")
                    optimization_score -= 10

            if 'max_connections' in db_config:
                max_conn = int(db_config['max_connections'])
                if max_conn > 1000:
                    recommendations.append("最大连接数设置过高，可能消耗过多内存")
                    optimization_score -= 5

            database_analysis = {
                'large_tables': large_tables[:5],  # 只返回前5个大表
                'total_fragmentation_mb': total_fragmentation // 1024 // 1024,
                'database_config': db_config
            }

        # 如果没有发现问题，给出一般性建议
        if not recommendations:
            recommendations = [
                "数据库状态良好，建议定期监控性能指标",
                "考虑定期备份重要数据",
                "监控连接池使用情况"
            ]

        optimization_data = {
            'recommendations': recommendations,
            'optimization_score': max(optimization_score, 0),
            'database_analysis': database_analysis,
            'last_analyzed': datetime.now().isoformat(),
            'total_recommendations': len(recommendations)
        }

        return success_response(data=optimization_data, message='获取数据库优化建议成功')

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
def test_db_connection():
    """测试数据库连接"""
    try:
        import time
        from sqlalchemy import create_engine, text
        import urllib.parse as urlparse

        # 获取数据库连接字符串
        try:
            from config.config import SQLALCHEMY_DATABASE_URI
            if not SQLALCHEMY_DATABASE_URI:
                return error_response('数据库连接字符串未配置', status_code=500)
            logger.info(f"成功获取数据库配置")
        except Exception as e:
            logger.error(f"获取数据库配置失败: {str(e)}")
            return error_response(f'数据库配置获取失败: {str(e)}', status_code=500)

        # 从连接字符串解析数据库信息
        try:
            url = urlparse.urlparse(SQLALCHEMY_DATABASE_URI)
            db_info = {
                'host': url.hostname or 'Unknown',
                'port': url.port or 'Unknown',
                'database': url.path[1:] if url.path else 'Unknown',
                'user': url.username or 'Unknown',
                'connection_string': f"{url.hostname}:{url.port}{url.path}" if url.hostname else 'Unknown'
            }
        except Exception as parse_error:
            logger.error(f"解析连接字符串失败: {str(parse_error)}")
            db_info = {
                'host': 'Unknown',
                'port': 'Unknown',
                'database': 'Unknown',
                'user': 'Unknown',
                'connection_string': 'Parse Error'
            }

        logger.info(f"开始测试数据库连接: {db_info['host']}:{db_info['port']}")

        # 测试连接
        start_time = time.time()

        try:
            engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)

            with engine.connect() as conn:
                # 执行简单查询测试
                result = conn.execute(text("SELECT 1 as test"))
                test_result = result.fetchone()

                # 获取数据库版本
                version_result = conn.execute(text("SELECT VERSION() as version"))
                db_version = version_result.fetchone()[0]

            connection_time = time.time() - start_time
            logger.info(f"数据库连接测试成功，耗时: {connection_time:.3f}秒")

        except Exception as db_error:
            connection_time = time.time() - start_time
            logger.error(f"数据库连接失败: {str(db_error)}")
            return error_response(
                f'数据库连接失败: {str(db_error)}',
                status_code=500,
                data={
                    'database_info': db_info,
                    'connection_time': round(connection_time * 1000, 2),
                    'error_details': str(db_error),
                    'connection_status': 'failed'
                }
            )

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
        logger.error(f"数据库连接测试异常: {str(e)}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")

        return error_response(
            f'数据库连接测试失败: {str(e)}',
            status_code=500,
            data={
                'error_details': str(e),
                'connection_status': 'error'
            }
        )

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
    """获取 Railway 环境信息（包含数据库连接验证）"""
    try:
        import os
        from sqlalchemy import text

        # 检测是否在 Railway 环境
        is_railway = bool(
            os.environ.get('RAILWAY_PROJECT_ID') or
            os.environ.get('RAILWAY_ENVIRONMENT_ID')
        )

        # 查询数据库获取实际连接信息
        database_info = {}
        try:
            with db.engine.connect() as conn:
                # 获取数据库连接信息
                connection_info = text("""
                    SELECT
                        USER() as current_user,
                        DATABASE() as current_database,
                        CONNECTION_ID() as connection_id,
                        VERSION() as version
                """)

                result = conn.execute(connection_info)
                row = result.fetchone()

                if row:
                    database_info = {
                        'connected_user': row[0],
                        'current_database': row[1],
                        'connection_id': row[2],
                        'mysql_version': row[3],
                        'connection_status': 'connected'
                    }

                # 获取当前连接的主机信息
                host_info = text("SHOW VARIABLES WHERE Variable_name IN ('hostname', 'port')")
                host_result = conn.execute(host_info)

                for row in host_result.fetchall():
                    if row[0] == 'hostname':
                        database_info['server_hostname'] = row[1]
                    elif row[0] == 'port':
                        database_info['server_port'] = row[1]

        except Exception as db_error:
            database_info = {
                'connection_status': 'failed',
                'error': str(db_error)
            }

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
                'public_domain': os.environ.get('RAILWAY_PUBLIC_DOMAIN'),
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
                },
                'database_connection': database_info
            }
        else:
            railway_info = {
                'environment': 'Local',
                'message': '当前运行在本地环境',
                'database_connection': database_info
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
