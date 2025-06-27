# -*- coding: utf-8 -*-
"""
代理池API路由 - 简化版本
"""
from flask import Blueprint, request, jsonify

from utils.auth import token_required, admin_required
from utils.logger import get_logger
from services.api_proxy_pool import get_api_proxy_pool

proxy_pool_bp = Blueprint('proxy_pool', __name__)
logger = get_logger(__name__)

@proxy_pool_bp.route('/status', methods=['GET'])
@token_required
def get_proxy_pool_status(current_user):
    """获取代理池状态"""
    try:
        # 模拟代理池状态
        status = {
            'total_proxies': 156,
            'active_proxies': 134,
            'inactive_proxies': 22,
            'average_response_time': 245,
            'success_rate': 89.5,
            'last_check': '2024-01-15 10:30:00'
        }
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"获取代理池状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取代理池状态失败'
        }), 500

@proxy_pool_bp.route('/api/system/settings', methods=['GET'])
@admin_required
def get_system_settings(current_user):
    """获取系统设置"""
    try:
        proxy_pool = get_api_proxy_pool()
        settings = {
            'auto_recovery_enabled': proxy_pool.auto_recovery_enabled,
            'auto_recovery_interval': proxy_pool.auto_recovery_interval,
            'model_test_enabled': proxy_pool.model_test_enabled,
            'model_test_interval': proxy_pool.model_test_interval,
            'model_test_max_count': proxy_pool.model_test_max_count
        }
        
        return jsonify({
            'code': 0,
            'msg': '获取系统设置成功',
            'data': settings
        })
    except Exception as e:
        logger.error(f"获取系统设置异常: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': f'获取系统设置失败: {str(e)}'
        }), 500

@proxy_pool_bp.route('/api/system/settings', methods=['POST'])
@admin_required
def update_system_settings(current_user):
    """更新系统设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求数据格式错误'
            }), 400
        
        proxy_pool = get_api_proxy_pool()
        
        # 更新设置
        if 'auto_recovery_enabled' in data:
            proxy_pool.auto_recovery_enabled = bool(data['auto_recovery_enabled'])
        
        if 'auto_recovery_interval' in data:
            proxy_pool.auto_recovery_interval = int(data['auto_recovery_interval'])
        
        if 'model_test_enabled' in data:
            proxy_pool.model_test_enabled = bool(data['model_test_enabled'])
            
            # 如果启用了模型测试，但线程未运行，则启动线程
            if proxy_pool.model_test_enabled:
                proxy_pool.start_model_test()
            else:
                proxy_pool.stop_model_test()
        
        if 'model_test_interval' in data:
            proxy_pool.model_test_interval = int(data['model_test_interval'])
        
        if 'model_test_max_count' in data:
            proxy_pool.model_test_max_count = int(data['model_test_max_count'])
        
        logger.info(f"管理员 {current_user.username} 更新系统设置")
        
        return jsonify({
            'code': 0,
            'msg': '系统设置更新成功',
            'data': None
        })
    except Exception as e:
        logger.error(f"更新系统设置异常: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': f'更新系统设置失败: {str(e)}'
        }), 500
