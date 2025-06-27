# -*- coding: utf-8 -*-
"""
系统监控API路由
"""
from flask import Blueprint, jsonify, request
from utils.auth import token_required
from utils.system_monitor import get_system_monitor
from utils.response_handler import success_response, error_response, handle_exception
from utils.logger import get_logger

logger = get_logger(__name__)

system_monitor_bp = Blueprint('system_monitor', __name__, url_prefix='/api/system-monitor')

@system_monitor_bp.route('/stats', methods=['GET'])
@token_required
def get_system_stats(current_user):
    """获取当前系统状态"""
    try:
        monitor = get_system_monitor()
        stats = monitor.get_current_stats()
        
        return success_response(data=stats, message='获取系统状态成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_system_stats',
            'user_id': current_user.id if current_user else None
        })

@system_monitor_bp.route('/history', methods=['GET'])
@token_required
def get_system_history(current_user):
    """获取系统历史数据"""
    try:
        minutes = request.args.get('minutes', 60, type=int)
        
        # 限制查询范围
        if minutes > 1440:  # 最多24小时
            minutes = 1440
        elif minutes < 5:   # 最少5分钟
            minutes = 5
        
        monitor = get_system_monitor()
        history = monitor.get_history_stats(minutes)
        
        return success_response(
            data=history, 
            message=f'获取{minutes}分钟历史数据成功',
            meta={'minutes': minutes, 'data_points': len(history.get('cpu', []))}
        )
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_system_history',
            'user_id': current_user.id if current_user else None,
            'minutes': request.args.get('minutes')
        })

@system_monitor_bp.route('/summary', methods=['GET'])
@token_required
def get_system_summary(current_user):
    """获取系统汇总统计"""
    try:
        monitor = get_system_monitor()
        summary = monitor.get_summary_stats()
        
        return success_response(data=summary, message='获取系统汇总统计成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_system_summary',
            'user_id': current_user.id if current_user else None
        })

@system_monitor_bp.route('/alerts', methods=['GET'])
@token_required
def get_system_alerts(current_user):
    """获取系统告警"""
    try:
        monitor = get_system_monitor()
        alerts = list(monitor.active_alerts.values())
        
        # 按严重程度排序
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: severity_order.get(x.get('level', 'info'), 3))
        
        return success_response(
            data=alerts, 
            message='获取系统告警成功',
            meta={'alert_count': len(alerts)}
        )
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_system_alerts',
            'user_id': current_user.id if current_user else None
        })

@system_monitor_bp.route('/alerts/clear', methods=['POST'])
@token_required
def clear_system_alerts(current_user):
    """清除系统告警"""
    try:
        data = request.get_json() or {}
        alert_type = data.get('alert_type')
        
        monitor = get_system_monitor()
        
        if alert_type:
            # 清除特定类型的告警
            if alert_type in monitor.active_alerts:
                del monitor.active_alerts[alert_type]
                logger.info(f"用户 {current_user.username} 清除了告警: {alert_type}")
                return success_response(message=f'已清除 {alert_type} 告警')
            else:
                return error_response(f'告警类型 {alert_type} 不存在', status_code=404)
        else:
            # 清除所有告警
            cleared_count = len(monitor.active_alerts)
            monitor.active_alerts.clear()
            logger.info(f"用户 {current_user.username} 清除了所有告警")
            return success_response(message=f'已清除 {cleared_count} 个告警')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'clear_system_alerts',
            'user_id': current_user.id if current_user else None,
            'alert_type': request.get_json().get('alert_type') if request.get_json() else None
        })

@system_monitor_bp.route('/thresholds', methods=['GET'])
@token_required
def get_alert_thresholds(current_user):
    """获取告警阈值配置"""
    try:
        monitor = get_system_monitor()
        thresholds = monitor.alert_thresholds.copy()
        
        return success_response(data=thresholds, message='获取告警阈值成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_alert_thresholds',
            'user_id': current_user.id if current_user else None
        })

@system_monitor_bp.route('/thresholds', methods=['PUT'])
@token_required
def update_alert_thresholds(current_user):
    """更新告警阈值配置"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据不能为空', status_code=400)
        
        monitor = get_system_monitor()
        
        # 验证和更新阈值
        valid_keys = ['cpu_percent', 'memory_percent', 'disk_percent', 'network_error_rate']
        updated_keys = []
        
        for key, value in data.items():
            if key in valid_keys:
                if isinstance(value, (int, float)) and 0 <= value <= 100:
                    monitor.alert_thresholds[key] = float(value)
                    updated_keys.append(key)
                else:
                    return error_response(f'阈值 {key} 必须是0-100之间的数字', status_code=400)
            else:
                return error_response(f'无效的阈值配置项: {key}', status_code=400)
        
        if updated_keys:
            logger.info(f"用户 {current_user.username} 更新了告警阈值: {updated_keys}")
            return success_response(
                data=monitor.alert_thresholds,
                message=f'已更新 {len(updated_keys)} 个阈值配置'
            )
        else:
            return error_response('没有有效的阈值配置需要更新', status_code=400)
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'update_alert_thresholds',
            'user_id': current_user.id if current_user else None,
            'data': request.get_json() if request.get_json() else None
        })

@system_monitor_bp.route('/health', methods=['GET'])
def get_system_health():
    """获取系统健康状态（无需认证）"""
    try:
        monitor = get_system_monitor()
        current_stats = monitor.get_current_stats()
        
        # 计算健康分数
        health_score = 100
        issues = []
        
        if 'cpu' in current_stats and 'cpu_percent' in current_stats['cpu']:
            cpu_percent = current_stats['cpu']['cpu_percent']
            if cpu_percent > 90:
                health_score -= 30
                issues.append(f'CPU使用率过高: {cpu_percent:.1f}%')
            elif cpu_percent > 70:
                health_score -= 15
                issues.append(f'CPU使用率较高: {cpu_percent:.1f}%')
        
        if 'memory' in current_stats and 'memory_percent' in current_stats['memory']:
            memory_percent = current_stats['memory']['memory_percent']
            if memory_percent > 90:
                health_score -= 30
                issues.append(f'内存使用率过高: {memory_percent:.1f}%')
            elif memory_percent > 80:
                health_score -= 15
                issues.append(f'内存使用率较高: {memory_percent:.1f}%')
        
        if 'disk' in current_stats and 'disk_percent' in current_stats['disk']:
            disk_percent = current_stats['disk']['disk_percent']
            if disk_percent > 95:
                health_score -= 40
                issues.append(f'磁盘使用率过高: {disk_percent:.1f}%')
            elif disk_percent > 85:
                health_score -= 20
                issues.append(f'磁盘使用率较高: {disk_percent:.1f}%')
        
        # 确定健康状态
        if health_score >= 80:
            status = 'healthy'
        elif health_score >= 60:
            status = 'warning'
        else:
            status = 'critical'
        
        health_data = {
            'status': status,
            'score': max(0, health_score),
            'issues': issues,
            'active_alerts': len(monitor.active_alerts),
            'timestamp': current_stats.get('cpu', {}).get('timestamp')
        }
        
        return success_response(data=health_data, message='获取系统健康状态成功')
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_system_health'
        })

# 注册错误处理器
@system_monitor_bp.errorhandler(Exception)
def handle_system_monitor_error(error):
    """处理系统监控相关错误"""
    logger.error(f"系统监控API错误: {str(error)}")
    return error_response('系统监控服务异常', status_code=500)
