# -*- coding: utf-8 -*-
"""
缓存管理路由
"""
from flask import Blueprint, request, jsonify
import time
from datetime import datetime
import json

from utils.auth import token_required, admin_required
from utils.logger import get_logger
from services.cache import get_cache
from routes.logs import add_system_log

cache_bp = Blueprint('cache', __name__)
logger = get_logger(__name__)

@cache_bp.route('/status', methods=['GET'])
@token_required
def get_cache_status(current_user):
    """获取缓存状态"""
    try:
        cache = get_cache()
        stats = cache.get_stats()
        
        # 计算命中率
        total_requests = stats['hits'] + stats['misses']
        hit_rate = (stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # 获取连接状态
        is_connected = cache.is_connected()
        
        # 获取缓存大小
        cache_size = cache.size
        
        # 获取内存使用情况（如果可用）
        memory_usage = cache.get_memory_usage() if hasattr(cache, 'get_memory_usage') else None
        
        return jsonify({
            'success': True,
            'data': {
                'stats': stats,
                'hit_rate': round(hit_rate, 2),
                'cache_size': cache_size,
                'is_connected': is_connected,
                'memory_usage': memory_usage,
                'timestamp': int(time.time())
            }
        })
    except Exception as e:
        logger.error(f"获取缓存状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存状态失败'
        }), 500

@cache_bp.route('/clear', methods=['POST'])
@admin_required
def clear_cache(current_user):
    """清除所有缓存"""
    try:
        cache = get_cache()
        count = cache.clear()

        # 记录系统日志
        add_system_log(
            level='info',
            source='cache',
            message=f'清除缓存: 成功清除 {count} 个缓存项',
            user_id=current_user.id,
            ip_address=request.remote_addr,
            context={'cleared_count': count}
        )

        logger.info(f"管理员 {current_user.username} 清除了 {count} 个缓存项")
        
        return jsonify({
            'success': True,
            'message': f'成功清除 {count} 个缓存项',
            'data': {
                'cleared_count': count
            }
        })
    except Exception as e:
        logger.error(f"清除缓存异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '清除缓存失败'
        }), 500

@cache_bp.route('/keys', methods=['GET'])
@token_required
def get_cache_keys(current_user):
    """获取缓存键列表"""
    try:
        cache = get_cache()
        
        # 获取查询参数
        pattern = request.args.get('pattern', 'qa_cache:*')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # 获取所有匹配的键
        all_keys = cache.get_keys(pattern)
        
        # 分页
        total = len(all_keys)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_keys = all_keys[start:end]
        
        # 获取每个键的详细信息
        keys_info = []
        for key in paginated_keys:
            key_info = cache.get_key_info(key)
            if key_info:
                keys_info.append(key_info)
        
        return jsonify({
            'success': True,
            'data': {
                'keys': keys_info,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        })
    except Exception as e:
        logger.error(f"获取缓存键列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存键列表失败'
        }), 500

@cache_bp.route('/keys/<key>', methods=['GET'])
@token_required
def get_cache_key_detail(current_user, key):
    """获取缓存键详情"""
    try:
        cache = get_cache()
        key_info = cache.get_key_info(key)
        
        if not key_info:
            return jsonify({
                'success': False,
                'message': '缓存键不存在'
            }), 404
        
        # 获取缓存值
        value = cache.get_raw(key)
        key_info['value'] = value
        
        return jsonify({
            'success': True,
            'data': key_info
        })
    except Exception as e:
        logger.error(f"获取缓存键详情异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存键详情失败'
        }), 500

@cache_bp.route('/keys/<key>', methods=['DELETE'])
@admin_required
def delete_cache_key(current_user, key):
    """删除指定缓存键"""
    try:
        cache = get_cache()
        result = cache.delete_key(key)
        
        if result:
            logger.info(f"管理员 {current_user.username} 删除了缓存键: {key}")
            return jsonify({
                'success': True,
                'message': '缓存键删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '缓存键不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除缓存键异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '删除缓存键失败'
        }), 500

@cache_bp.route('/hot', methods=['GET'])
@token_required
def get_hot_cache(current_user):
    """获取热门缓存项"""
    try:
        cache = get_cache()
        limit = int(request.args.get('limit', 10))
        
        hot_items = cache.get_hot_questions(limit)
        
        return jsonify({
            'success': True,
            'data': hot_items
        })
    except Exception as e:
        logger.error(f"获取热门缓存异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取热门缓存失败'
        }), 500

@cache_bp.route('/preload', methods=['POST'])
@admin_required
def preload_cache(current_user):
    """缓存预热"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        # 获取预热数据
        questions_data = data.get('questions', [])
        if not questions_data:
            return jsonify({
                'success': False,
                'message': '预热数据为空'
            }), 400
        
        cache = get_cache()
        result = cache.preload_cache(questions_data)
        
        logger.info(f"管理员 {current_user.username} 执行缓存预热，预热了 {result['success_count']} 个问题")
        
        return jsonify({
            'success': True,
            'message': f'缓存预热完成，成功: {result["success_count"]}，失败: {result["failed_count"]}',
            'data': result
        })
    except Exception as e:
        logger.error(f"缓存预热异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '缓存预热失败'
        }), 500

@cache_bp.route('/config', methods=['GET'])
@token_required
def get_cache_config(current_user):
    """获取缓存配置"""
    try:
        cache = get_cache()
        config = {
            'expiration': cache.expiration,
            'cache_levels': cache.cache_levels,
            'auto_cleanup': getattr(cache, 'auto_cleanup', False),
            'cleanup_interval': getattr(cache, 'cleanup_interval', 600),
            'max_keys': getattr(cache, 'max_keys', 10000)
        }
        
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"获取缓存配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存配置失败'
        }), 500

@cache_bp.route('/config', methods=['PUT'])
@admin_required
def update_cache_config(current_user):
    """更新缓存配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        cache = get_cache()
        
        # 更新配置
        if 'expiration' in data:
            cache.expiration = int(data['expiration'])
        
        if 'cache_levels' in data and isinstance(data['cache_levels'], dict):
            cache.cache_levels = data['cache_levels']
        
        if 'auto_cleanup' in data:
            setattr(cache, 'auto_cleanup', bool(data['auto_cleanup']))
        
        if 'cleanup_interval' in data:
            setattr(cache, 'cleanup_interval', int(data['cleanup_interval']))
        
        if 'max_keys' in data:
            setattr(cache, 'max_keys', int(data['max_keys']))
        
        # 保存配置（如果需要）
        if hasattr(cache, 'save_config'):
            cache.save_config()
        
        logger.info(f"管理员 {current_user.username} 更新了缓存配置")
        
        return jsonify({
            'success': True,
            'message': '缓存配置更新成功'
        })
    except Exception as e:
        logger.error(f"更新缓存配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新缓存配置失败'
        }), 500

@cache_bp.route('/stats/history', methods=['GET'])
@token_required
def get_cache_stats_history(current_user):
    """获取缓存统计历史数据"""
    try:
        period = request.args.get('period', '24h')
        
        # 从Redis获取实际的历史数据
        cache = get_cache()
        
        # 根据period确定键名和数据点数量
        if period == '1h':
            history_key = "cache:stats:history:1h"
            points = 12
            interval = 5 * 60  # 5分钟
        elif period == '24h':
            history_key = "cache:stats:history:24h"
            points = 24
            interval = 60 * 60  # 1小时
        else:  # 7d
            history_key = "cache:stats:history:7d"
            points = 7
            interval = 24 * 60 * 60  # 1天
        
        history = []
        
        # 尝试从Redis获取历史数据
        if hasattr(cache, 'redis') and cache.redis:
            try:
                # 获取历史数据
                history_data = cache.redis.lrange(history_key, 0, -1)
                
                if history_data and len(history_data) > 0:
                    for item in history_data:
                        try:
                            data = json.loads(item)
                            history.append(data)
                        except:
                            pass
                
                # 如果没有足够的数据点，生成部分模拟数据补充
                if len(history) < points:
                    now = int(time.time())
                    existing_timestamps = [item.get('timestamp') for item in history]
                    
                    for i in range(points):
                        timestamp = now - (points - i - 1) * interval
                        
                        # 如果这个时间点没有数据，添加模拟数据
                        if timestamp not in existing_timestamps:
                            # 使用平均值或默认值
                            avg_hit_rate = sum([item.get('hit_rate', 0) for item in history]) / len(history) if history else 70
                            avg_requests = sum([item.get('requests', 0) for item in history]) / len(history) if history else 100
                            
                            history.append({
                                'timestamp': timestamp,
                                'hit_rate': round(avg_hit_rate, 2),
                                'requests': int(avg_requests),
                                'time_str': datetime.fromtimestamp(timestamp).strftime('%H:%M' if period != '7d' else '%m-%d')
                            })
                
                # 按时间戳排序
                history.sort(key=lambda x: x.get('timestamp', 0))
                
                # 只保留最近的points个数据点
                history = history[-points:]
            except Exception as e:
                logger.error(f"从Redis获取缓存历史数据失败: {str(e)}")
                # 如果获取失败，使用模拟数据
                history = _generate_mock_history_data(period, points, interval)
        else:
            # 内存缓存模式，使用模拟数据
            history = _generate_mock_history_data(period, points, interval)
        
        return jsonify({
            'success': True,
            'data': {
                'period': period,
                'history': history
            }
        })
    except Exception as e:
        logger.error(f"获取缓存统计历史数据异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取缓存统计历史数据失败'
        }), 500

def _generate_mock_history_data(period, points, interval):
    """生成模拟的历史数据"""
    now = int(time.time())
    history = []
    
    for i in range(points):
        timestamp = now - (points - i - 1) * interval
        hit_rate = 70 + (i % 3) * 10  # 模拟数据
        requests = 100 + (i % 5) * 50  # 模拟数据
        
        history.append({
            'timestamp': timestamp,
            'hit_rate': hit_rate,
            'requests': requests,
            'time_str': datetime.fromtimestamp(timestamp).strftime('%H:%M' if period != '7d' else '%m-%d')
        })
    
    return history 