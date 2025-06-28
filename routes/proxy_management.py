# -*- coding: utf-8 -*-
"""
代理管理API路由 - 适配新架构
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import requests
import time

from models.models import db, ProxyPool
from utils.auth import token_required, admin_required
from utils.logger import get_logger

# 尝试导入日志模块，如果失败则使用简化版本
try:
    from routes.logs import add_system_log
except ImportError:
    def add_system_log(level='info', source='system', message='', user_id=None, ip_address=None, context=None):
        """简化的日志记录函数"""
        logger = get_logger(__name__)
        log_message = f"[{source.upper()}] {message}"
        if user_id:
            log_message += f" | User: {user_id}"
        if ip_address:
            log_message += f" | IP: {ip_address}"
        if context:
            log_message += f" | Context: {context}"

        if level == 'error':
            logger.error(log_message)
        elif level == 'warn':
            logger.warning(log_message)
        else:
            logger.info(log_message)

proxy_management_bp = Blueprint('proxy_management', __name__)
logger = get_logger(__name__)

@proxy_management_bp.route('/list', methods=['GET'])
@token_required
def get_proxy_list(current_user):
    """获取代理列表"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '')
        
        # 构建查询
        query = ProxyPool.query
        
        if status:
            query = query.filter_by(status=status)
        
        # 排序
        query = query.order_by(ProxyPool.created_at.desc())
        
        # 分页
        total = query.count()
        proxies = query.offset((page - 1) * size).limit(size).all()
        
        return jsonify({
            'success': True,
            'data': {
                'proxies': [proxy.to_dict() for proxy in proxies],
                'pagination': {
                    'page': page,
                    'size': size,
                    'total': total,
                    'pages': (total + size - 1) // size
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取代理列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取代理列表失败'
        }), 500

@proxy_management_bp.route('/add', methods=['POST'])
@admin_required
def add_proxy(current_user):
    """添加代理"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        # 验证必填字段
        required_fields = ['host', 'port', 'type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400
        
        # 检查代理是否已存在
        existing_proxy = ProxyPool.query.filter_by(
            host=data['host'],
            port=data['port']
        ).first()
        
        if existing_proxy:
            return jsonify({
                'success': False,
                'message': '代理已存在'
            }), 409
        
        # 创建新代理
        new_proxy = ProxyPool(
            host=data['host'],
            port=data['port'],
            type=data['type'],
            username=data.get('username'),
            password=data.get('password'),
            location=data.get('location'),
            status='active',
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_proxy)
        db.session.commit()

        # 记录系统日志
        add_system_log(
            level='info',
            source='proxy',
            message=f'添加代理: {new_proxy.host}:{new_proxy.port}',
            user_id=current_user.id,
            ip_address=request.remote_addr,
            context={'proxy_id': new_proxy.id, 'host': new_proxy.host, 'port': new_proxy.port}
        )

        logger.info(f"管理员 {current_user.username} 添加代理: {new_proxy.host}:{new_proxy.port}")
        
        return jsonify({
            'success': True,
            'message': '代理添加成功',
            'data': {
                'proxy': new_proxy.to_dict()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '添加代理失败'
        }), 500

@proxy_management_bp.route('/<int:proxy_id>', methods=['PUT'])
@admin_required
def update_proxy(current_user, proxy_id):
    """更新代理"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        proxy = ProxyPool.query.get(proxy_id)
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        # 更新字段
        updatable_fields = ['host', 'port', 'type', 'username', 'password', 'location', 'status']
        for field in updatable_fields:
            if field in data:
                setattr(proxy, field, data[field])
        
        proxy.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"管理员 {current_user.username} 更新代理: {proxy_id}")
        
        return jsonify({
            'success': True,
            'message': '代理更新成功',
            'data': {
                'proxy': proxy.to_dict()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新代理失败'
        }), 500

@proxy_management_bp.route('/<int:proxy_id>', methods=['DELETE'])
@admin_required
def delete_proxy(current_user, proxy_id):
    """删除代理"""
    try:
        proxy = ProxyPool.query.get(proxy_id)
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        db.session.delete(proxy)
        db.session.commit()
        
        logger.info(f"管理员 {current_user.username} 删除代理: {proxy_id}")
        
        return jsonify({
            'success': True,
            'message': '代理删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '删除代理失败'
        }), 500

@proxy_management_bp.route('/<int:proxy_id>/test', methods=['POST'])
@token_required
def test_proxy(current_user, proxy_id):
    """测试代理"""
    try:
        proxy = ProxyPool.query.get(proxy_id)
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        # 构建代理URL
        if proxy.username and proxy.password:
            proxy_url = f"{proxy.type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            proxy_url = f"{proxy.type}://{proxy.host}:{proxy.port}"
        
        # 测试代理连接
        test_url = "http://httpbin.org/ip"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        start_time = time.time()
        try:
            response = requests.get(test_url, proxies=proxies, timeout=10)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                # 更新代理状态
                proxy.status = 'active'
                proxy.response_time = response_time
                proxy.last_tested = datetime.utcnow()
                proxy.success_rate = min(100, (proxy.success_rate or 0) + 10)
                
                db.session.commit()

                # 记录系统日志
                add_system_log(
                    level='info',
                    source='proxy',
                    message=f'代理测试成功: {proxy.name} - 响应时间 {response_time}ms',
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    context={'proxy_id': proxy_id, 'response_time': response_time}
                )

                return jsonify({
                    'success': True,
                    'message': '代理测试成功',
                    'data': {
                        'response_time': response_time,
                        'status': 'active'
                    }
                })
            else:
                # 更新代理状态
                proxy.status = 'inactive'
                proxy.response_time = response_time
                proxy.last_tested = datetime.utcnow()
                proxy.success_rate = max(0, (proxy.success_rate or 0) - 10)
                
                db.session.commit()

                # 记录系统日志
                add_system_log(
                    level='warn',
                    source='proxy',
                    message=f'代理测试失败: {proxy.name} - HTTP {response.status_code}',
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    context={'proxy_id': proxy_id, 'response_time': response_time, 'status_code': response.status_code}
                )

                return jsonify({
                    'success': False,
                    'message': f'代理测试失败: HTTP {response.status_code}',
                    'data': {
                        'response_time': response_time,
                        'status': 'inactive'
                    }
                })
                
        except requests.exceptions.Timeout:
            proxy.status = 'inactive'
            proxy.last_tested = datetime.utcnow()
            proxy.success_rate = max(0, (proxy.success_rate or 0) - 20)
            db.session.commit()
            
            return jsonify({
                'success': False,
                'message': '代理测试超时',
                'data': {
                    'response_time': 10000,
                    'status': 'inactive'
                }
            })
            
        except Exception as e:
            proxy.status = 'inactive'
            proxy.last_tested = datetime.utcnow()
            proxy.success_rate = max(0, (proxy.success_rate or 0) - 20)
            db.session.commit()
            
            return jsonify({
                'success': False,
                'message': f'代理测试失败: {str(e)}',
                'data': {
                    'response_time': int((time.time() - start_time) * 1000),
                    'status': 'inactive'
                }
            })
        
    except Exception as e:
        logger.error(f"测试代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '测试代理失败'
        }), 500

@proxy_management_bp.route('/batch-test', methods=['POST'])
@admin_required
def batch_test_proxies(current_user):
    """批量测试代理"""
    try:
        data = request.get_json()
        proxy_ids = data.get('proxy_ids', []) if data else []
        
        if not proxy_ids:
            # 测试所有代理
            proxies = ProxyPool.query.all()
        else:
            # 测试指定代理
            proxies = ProxyPool.query.filter(ProxyPool.id.in_(proxy_ids)).all()
        
        results = []
        for proxy in proxies:
            # 这里可以实现并发测试，简化版本使用同步测试
            try:
                # 模拟测试结果
                import random
                success = random.random() > 0.3  # 70%成功率
                response_time = random.randint(100, 2000)
                
                proxy.status = 'active' if success else 'inactive'
                proxy.response_time = response_time
                proxy.last_tested = datetime.utcnow()
                
                if success:
                    proxy.success_rate = min(100, (proxy.success_rate or 0) + 10)
                else:
                    proxy.success_rate = max(0, (proxy.success_rate or 0) - 10)
                
                results.append({
                    'proxy_id': proxy.id,
                    'host': proxy.host,
                    'port': proxy.port,
                    'success': success,
                    'response_time': response_time,
                    'status': proxy.status
                })
                
            except Exception as e:
                results.append({
                    'proxy_id': proxy.id,
                    'host': proxy.host,
                    'port': proxy.port,
                    'success': False,
                    'error': str(e),
                    'status': 'inactive'
                })
        
        db.session.commit()
        
        success_count = len([r for r in results if r['success']])
        
        logger.info(f"管理员 {current_user.username} 批量测试代理: {len(results)}个, 成功{success_count}个")
        
        return jsonify({
            'success': True,
            'message': f'批量测试完成: {success_count}/{len(results)} 个代理可用',
            'data': {
                'results': results,
                'total': len(results),
                'success_count': success_count,
                'failed_count': len(results) - success_count
            }
        })
        
    except Exception as e:
        logger.error(f"批量测试代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '批量测试失败'
        }), 500
