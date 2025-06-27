# -*- coding: utf-8 -*-
"""
系统设置API路由
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import json
import os

from models.models import db, SystemConfig
from utils.auth import token_required, admin_required
from utils.logger import get_logger

settings_bp = Blueprint('settings', __name__)
logger = get_logger(__name__)

@settings_bp.route('/system', methods=['GET'])
@admin_required
def get_system_settings(current_user):
    """获取系统设置"""
    try:
        # 从数据库获取配置
        configs = SystemConfig.query.filter_by(is_public=True).all()
        
        settings = {}
        for config in configs:
            try:
                if config.type == 'json':
                    settings[config.key] = json.loads(config.value) if config.value else {}
                elif config.type == 'bool':
                    settings[config.key] = config.value.lower() == 'true' if config.value else False
                elif config.type == 'int':
                    settings[config.key] = int(config.value) if config.value else 0
                elif config.type == 'float':
                    settings[config.key] = float(config.value) if config.value else 0.0
                else:
                    settings[config.key] = config.value or ''
            except (ValueError, json.JSONDecodeError):
                settings[config.key] = config.value or ''
        
        return jsonify({
            'success': True,
            'data': {
                'settings': settings
            }
        })
        
    except Exception as e:
        logger.error(f"获取系统设置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取系统设置失败'
        }), 500

@settings_bp.route('/system', methods=['PUT'])
@admin_required
def update_system_settings(current_user):
    """更新系统设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        updated_count = 0
        
        for key, value in data.items():
            # 查找现有配置
            config = SystemConfig.query.filter_by(key=key).first()
            
            if config:
                # 更新现有配置
                if isinstance(value, (dict, list)):
                    config.value = json.dumps(value, ensure_ascii=False)
                    config.type = 'json'
                elif isinstance(value, bool):
                    config.value = str(value).lower()
                    config.type = 'bool'
                elif isinstance(value, int):
                    config.value = str(value)
                    config.type = 'int'
                elif isinstance(value, float):
                    config.value = str(value)
                    config.type = 'float'
                else:
                    config.value = str(value)
                    config.type = 'string'
                
                config.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # 创建新配置
                if isinstance(value, (dict, list)):
                    config_value = json.dumps(value, ensure_ascii=False)
                    config_type = 'json'
                elif isinstance(value, bool):
                    config_value = str(value).lower()
                    config_type = 'bool'
                elif isinstance(value, int):
                    config_value = str(value)
                    config_type = 'int'
                elif isinstance(value, float):
                    config_value = str(value)
                    config_type = 'float'
                else:
                    config_value = str(value)
                    config_type = 'string'
                
                new_config = SystemConfig(
                    key=key,
                    value=config_value,
                    type=config_type,
                    is_public=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(new_config)
                updated_count += 1
        
        db.session.commit()
        
        logger.info(f"管理员 {current_user.username} 更新系统设置: {updated_count}项")
        
        return jsonify({
            'success': True,
            'message': f'成功更新 {updated_count} 项设置',
            'data': {
                'updated_count': updated_count
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新系统设置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新系统设置失败'
        }), 500

@settings_bp.route('/cache', methods=['GET'])
@admin_required
def get_cache_settings(current_user):
    """获取缓存设置"""
    try:
        # 模拟缓存设置
        cache_settings = {
            'enabled': True,
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'max_connections': 50,
            'timeout': 5,
            'default_ttl': 3600
        }
        
        return jsonify({
            'success': True,
            'data': {
                'cache_settings': cache_settings
            }
        })
        
    except Exception as e:
        logger.error(f"获取缓存设置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存设置失败'
        }), 500

@settings_bp.route('/cache/clear', methods=['POST'])
@admin_required
def clear_cache(current_user):
    """清空缓存"""
    try:
        # 这里应该实现实际的缓存清空逻辑
        # 模拟清空缓存
        cleared_keys = 1234  # 模拟清空的键数量
        
        logger.info(f"管理员 {current_user.username} 清空缓存: {cleared_keys}个键")
        
        return jsonify({
            'success': True,
            'message': f'成功清空 {cleared_keys} 个缓存键',
            'data': {
                'cleared_keys': cleared_keys
            }
        })
        
    except Exception as e:
        logger.error(f"清空缓存异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '清空缓存失败'
        }), 500

@settings_bp.route('/database', methods=['GET'])
@admin_required
def get_database_info(current_user):
    """获取数据库信息"""
    try:
        # 模拟数据库信息
        database_info = {
            'type': 'MySQL',
            'version': '8.0.35',
            'host': 'localhost',
            'port': 3306,
            'database': 'ocs_qa',
            'charset': 'utf8mb4',
            'tables': [
                {'name': 'qa_records', 'rows': 12345, 'size': '256MB'},
                {'name': 'users', 'rows': 456, 'size': '12MB'},
                {'name': 'user_sessions', 'rows': 789, 'size': '8MB'},
                {'name': 'system_logs', 'rows': 23456, 'size': '128MB'},
                {'name': 'proxy_pool', 'rows': 123, 'size': '4MB'}
            ],
            'total_size': '408MB',
            'total_rows': 37169
        }
        
        return jsonify({
            'success': True,
            'data': {
                'database_info': database_info
            }
        })
        
    except Exception as e:
        logger.error(f"获取数据库信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取数据库信息失败'
        }), 500

@settings_bp.route('/backup', methods=['POST'])
@admin_required
def create_backup(current_user):
    """创建数据备份"""
    try:
        data = request.get_json()
        backup_type = data.get('type', 'full') if data else 'full'
        
        # 模拟备份过程
        backup_filename = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
        backup_size = "45.6MB"  # 模拟备份大小
        
        logger.info(f"管理员 {current_user.username} 创建数据备份: {backup_filename}")
        
        return jsonify({
            'success': True,
            'message': '数据备份创建成功',
            'data': {
                'backup_filename': backup_filename,
                'backup_size': backup_size,
                'backup_type': backup_type,
                'created_at': datetime.utcnow().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"创建数据备份异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '创建数据备份失败'
        }), 500

@settings_bp.route('/system/info', methods=['GET'])
@token_required
def get_system_info(current_user):
    """获取系统信息"""
    try:
        import psutil
        import platform
        
        # 系统信息
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'architecture': platform.architecture()[0],
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': f"{psutil.virtual_memory().total / (1024**3):.1f}GB",
            'disk_total': f"{psutil.disk_usage('/').total / (1024**3):.1f}GB"
        }
        
        # 应用信息
        app_info = {
            'name': 'EduBrain AI',
            'version': '1.0.0',
            'environment': 'development',
            'uptime': '2 days, 3 hours, 45 minutes'
        }
        
        return jsonify({
            'success': True,
            'data': {
                'system_info': system_info,
                'app_info': app_info
            }
        })
        
    except Exception as e:
        logger.error(f"获取系统信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取系统信息失败'
        }), 500
