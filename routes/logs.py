# -*- coding: utf-8 -*-
"""
系统日志API路由
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json

from models.models import db, SystemLog
from utils.auth import token_required, admin_required
from utils.logger import get_logger, get_log_manager
from utils.response_handler import success_response, error_response, handle_exception

logs_bp = Blueprint('logs', __name__)
logger = get_logger(__name__)

@logs_bp.route('/list', methods=['GET'])
@admin_required
def get_logs_list(current_user):
    """获取系统日志列表"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 50))
        level = request.args.get('level', '')
        source = request.args.get('source', '')
        keyword = request.args.get('keyword', '')
        start_time = request.args.get('start_time', '')
        end_time = request.args.get('end_time', '')
        
        # 构建查询
        query = SystemLog.query
        
        # 级别筛选
        if level:
            query = query.filter_by(level=level)
        
        # 来源筛选
        if source:
            query = query.filter_by(source=source)
        
        # 关键词搜索
        if keyword:
            query = query.filter(SystemLog.message.contains(keyword))
        
        # 时间范围筛选
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                query = query.filter(SystemLog.created_at >= start_dt)
            except ValueError:
                pass
        
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                query = query.filter(SystemLog.created_at <= end_dt)
            except ValueError:
                pass
        
        # 排序
        query = query.order_by(SystemLog.created_at.desc())
        
        # 分页
        total = query.count()
        logs = query.offset((page - 1) * size).limit(size).all()
        
        return jsonify({
            'success': True,
            'data': {
                'logs': [log.to_dict() for log in logs],
                'pagination': {
                    'page': page,
                    'size': size,
                    'total': total,
                    'pages': (total + size - 1) // size
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取日志列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取日志列表失败'
        }), 500

@logs_bp.route('/statistics', methods=['GET'])
@admin_required
def get_logs_statistics(current_user):
    """获取日志统计信息"""
    try:
        # 今日日志统计
        today = datetime.utcnow().date()
        today_logs = SystemLog.query.filter(
            SystemLog.created_at >= today
        ).count()
        
        # 各级别日志统计
        level_stats = db.session.query(
            SystemLog.level,
            db.func.count(SystemLog.id).label('count')
        ).group_by(SystemLog.level).all()
        
        # 各来源日志统计
        source_stats = db.session.query(
            SystemLog.source,
            db.func.count(SystemLog.id).label('count')
        ).group_by(SystemLog.source).all()
        
        # 最近7天日志趋势
        week_ago = datetime.utcnow() - timedelta(days=7)
        daily_stats = db.session.query(
            db.func.date(SystemLog.created_at).label('date'),
            db.func.count(SystemLog.id).label('count')
        ).filter(
            SystemLog.created_at >= week_ago
        ).group_by(
            db.func.date(SystemLog.created_at)
        ).order_by('date').all()
        
        return jsonify({
            'success': True,
            'data': {
                'overview': {
                    'today_logs': today_logs,
                    'total_logs': SystemLog.query.count()
                },
                'level_distribution': [
                    {'level': item[0], 'count': item[1]}
                    for item in level_stats
                ],
                'source_distribution': [
                    {'source': item[0], 'count': item[1]}
                    for item in source_stats
                ],
                'daily_trend': [
                    {'date': str(item[0]), 'count': item[1]}
                    for item in daily_stats
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"获取日志统计异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取日志统计失败'
        }), 500

@logs_bp.route('/clear', methods=['POST'])
@admin_required
def clear_logs(current_user):
    """清空日志"""
    try:
        data = request.get_json()
        days = data.get('days', 0) if data else 0
        
        if days > 0:
            # 删除指定天数前的日志
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            deleted_count = SystemLog.query.filter(
                SystemLog.created_at < cutoff_date
            ).delete()
        else:
            # 删除所有日志
            deleted_count = SystemLog.query.delete()
        
        db.session.commit()
        
        logger.info(f"管理员 {current_user.username} 清空日志: 删除{deleted_count}条")
        
        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 条日志',
            'data': {
                'deleted_count': deleted_count
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"清空日志异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '清空日志失败'
        }), 500

@logs_bp.route('/export/basic', methods=['POST'])
@admin_required
def export_basic_logs(current_user):
    """导出基础日志"""
    try:
        data = request.get_json()
        level = data.get('level', '') if data else ''
        source = data.get('source', '') if data else ''
        start_time = data.get('start_time', '') if data else ''
        end_time = data.get('end_time', '') if data else ''

        # 构建查询
        query = SystemLog.query

        if level:
            query = query.filter_by(level=level)
        if source:
            query = query.filter_by(source=source)
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                query = query.filter(SystemLog.created_at >= start_dt)
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                query = query.filter(SystemLog.created_at <= end_dt)
            except ValueError:
                pass

        # 限制导出数量
        logs = query.order_by(SystemLog.created_at.desc()).limit(10000).all()

        # 生成导出数据
        export_data = []
        for log in logs:
            export_data.append({
                'timestamp': log.created_at.isoformat() if log.created_at else '',
                'level': log.level,
                'source': log.source,
                'message': log.message,
                'user_id': log.user_id,
                'ip_address': log.ip_address,
                'request_id': log.request_id
            })

        logger.info(f"管理员 {current_user.username} 导出基础日志: {len(export_data)}条")

        return jsonify({
            'success': True,
            'message': f'成功导出 {len(export_data)} 条日志',
            'data': {
                'logs': export_data,
                'count': len(export_data)
            }
        })

    except Exception as e:
        logger.error(f"导出基础日志异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '导出基础日志失败'
        }), 500

def add_system_log(level, source, message, user_id=None, ip_address=None, request_id=None, context=None):
    """添加系统日志"""
    try:
        log = SystemLog(
            level=level,
            source=source,
            message=message,
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            context=json.dumps(context) if context else None,
            created_at=datetime.utcnow()
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"添加系统日志失败: {str(e)}")
        # 不抛出异常，避免影响主要业务流程

@logs_bp.route('/frontend', methods=['POST'])
def receive_frontend_logs():
    """接收前端日志"""
    try:
        data = request.get_json()
        logs = data.get('logs', [])

        for log_entry in logs:
            level = log_entry.get('level', 'info')
            message = log_entry.get('message', '')
            context = log_entry.get('context', {})

            # 添加到系统日志
            add_system_log(
                level=level,
                source='frontend',
                message=f'[前端] {message}',
                ip_address=request.remote_addr,
                context=context
            )

        return jsonify({
            'success': True,
            'message': f'成功接收 {len(logs)} 条前端日志'
        })

    except Exception as e:
        logger.error(f"接收前端日志异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '接收前端日志失败'
        }), 500

# 增强的日志管理接口

@logs_bp.route('/memory', methods=['GET'])
@admin_required
def get_memory_logs(current_user):
    """获取内存中的日志"""
    try:
        log_manager = get_log_manager()

        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level')

        # 限制查询数量
        if limit > 1000:
            limit = 1000

        logs = log_manager.get_recent_logs(limit=limit, level=level)

        return success_response(
            data=logs,
            message='获取内存日志成功',
            meta={'count': len(logs), 'limit': limit}
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_memory_logs',
            'user_id': current_user.id
        })

@logs_bp.route('/search', methods=['GET'])
@admin_required
def search_logs(current_user):
    """搜索日志"""
    try:
        query = request.args.get('query', '').strip()
        if not query:
            return error_response('搜索关键词不能为空', status_code=400)

        limit = request.args.get('limit', 100, type=int)
        if limit > 500:
            limit = 500

        log_manager = get_log_manager()
        logs = log_manager.search_logs(query=query, limit=limit)

        return success_response(
            data=logs,
            message=f'搜索到 {len(logs)} 条日志',
            meta={'query': query, 'count': len(logs)}
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'search_logs',
            'user_id': current_user.id,
            'query': request.args.get('query')
        })

@logs_bp.route('/stats/enhanced', methods=['GET'])
@admin_required
def get_enhanced_log_stats(current_user):
    """获取增强的日志统计"""
    try:
        log_manager = get_log_manager()
        stats = log_manager.get_log_stats()

        # 添加数据库日志统计
        db_stats = {
            'total_db_logs': SystemLog.query.count(),
            'today_db_logs': SystemLog.query.filter(
                SystemLog.created_at >= datetime.utcnow().date()
            ).count(),
            'error_db_logs': SystemLog.query.filter(
                SystemLog.level == 'ERROR'
            ).count()
        }

        combined_stats = {
            'memory_logs': stats,
            'database_logs': db_stats,
            'system_info': {
                'memory_log_capacity': log_manager.max_memory_logs,
                'compression_enabled': log_manager.compression_enabled,
                'compression_age_days': log_manager.compression_age_days
            }
        }

        return success_response(
            data=combined_stats,
            message='获取增强日志统计成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_enhanced_log_stats',
            'user_id': current_user.id
        })

@logs_bp.route('/export', methods=['POST'])
@admin_required
def export_logs(current_user):
    """导出日志"""
    try:
        data = request.get_json() or {}

        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        export_type = data.get('type', 'memory')  # memory 或 database

        start_time = None
        end_time = None

        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        if end_time_str:
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

        if export_type == 'memory':
            log_manager = get_log_manager()
            logs = log_manager.export_logs(start_time=start_time, end_time=end_time)
        else:
            # 从数据库导出
            query = SystemLog.query

            if start_time:
                query = query.filter(SystemLog.created_at >= start_time)
            if end_time:
                query = query.filter(SystemLog.created_at <= end_time)

            db_logs = query.order_by(SystemLog.created_at.desc()).limit(10000).all()
            logs = []
            for log in db_logs:
                logs.append({
                    'timestamp': log.created_at.isoformat(),
                    'level': log.level,
                    'message': log.message,
                    'source': log.source,
                    'user_id': log.user_id,
                    'ip_address': log.ip_address,
                    'context': json.loads(log.context) if log.context else {}
                })

        return success_response(
            data=logs,
            message=f'导出 {len(logs)} 条日志',
            meta={
                'export_type': export_type,
                'start_time': start_time_str,
                'end_time': end_time_str,
                'count': len(logs)
            }
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'export_logs',
            'user_id': current_user.id,
            'data': request.get_json()
        })

@logs_bp.route('/config', methods=['GET'])
@admin_required
def get_log_config(current_user):
    """获取日志配置"""
    try:
        log_manager = get_log_manager()

        config = {
            'max_memory_logs': log_manager.max_memory_logs,
            'compression_enabled': log_manager.compression_enabled,
            'compression_age_days': log_manager.compression_age_days,
            'current_memory_logs': len(log_manager.memory_logs),
            'log_stats': log_manager.get_log_stats()
        }

        return success_response(data=config, message='获取日志配置成功')

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_log_config',
            'user_id': current_user.id
        })

@logs_bp.route('/config', methods=['PUT'])
@admin_required
def update_log_config(current_user):
    """更新日志配置"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据不能为空', status_code=400)

        log_manager = get_log_manager()
        updated_fields = []

        if 'compression_enabled' in data:
            log_manager.compression_enabled = bool(data['compression_enabled'])
            updated_fields.append('compression_enabled')

        if 'compression_age_days' in data:
            age_days = int(data['compression_age_days'])
            if 1 <= age_days <= 365:
                log_manager.compression_age_days = age_days
                updated_fields.append('compression_age_days')
            else:
                return error_response('压缩天数必须在1-365之间', status_code=400)

        logger.info(f"用户 {current_user.username} 更新了日志配置: {updated_fields}")

        return success_response(
            message=f'已更新 {len(updated_fields)} 个配置项',
            meta={'updated_fields': updated_fields}
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'update_log_config',
            'user_id': current_user.id,
            'data': request.get_json()
        })
