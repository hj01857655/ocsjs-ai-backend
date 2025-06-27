# -*- coding: utf-8 -*-
"""
并发管理API路由 - 简化版本
"""
from flask import Blueprint, request, jsonify

from utils.auth import token_required
from utils.logger import get_logger

concurrent_management_bp = Blueprint('concurrent_management', __name__)
logger = get_logger(__name__)

@concurrent_management_bp.route('/status', methods=['GET'])
@token_required
def get_concurrent_status(current_user):
    """获取并发状态"""
    try:
        # 模拟并发状态
        status = {
            'active_requests': 23,
            'max_concurrent': 100,
            'queue_size': 5,
            'average_wait_time': 1.2,
            'throughput': 45.6
        }
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"获取并发状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取并发状态失败'
        }), 500
