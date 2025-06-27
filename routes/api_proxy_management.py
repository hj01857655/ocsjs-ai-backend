# -*- coding: utf-8 -*-
"""
API代理管理路由
"""
from flask import Blueprint, request, jsonify, send_file
import json
import os
import time
import tempfile
import requests

from utils.auth import token_required, admin_required
from utils.logger import get_logger
from services.api_proxy_pool import get_api_proxy_pool, reload_proxy_pool, save_proxy_config
from constants import SYSTEM_PROMPT, TEST_QUESTIONS
import random

api_proxy_management_bp = Blueprint('api_proxy_management', __name__)
logger = get_logger(__name__)

@api_proxy_management_bp.route('/test-status', methods=['GET'])
def test_proxy_pool_status():
    """测试代理池状态（无需认证）"""
    try:
        proxy_pool = get_api_proxy_pool()
        return jsonify({
            'success': True,
            'data': {
                'config_file': proxy_pool.config_file,
                'proxy_count': len(proxy_pool.proxies),
                'proxies': [
                    {
                        'name': proxy.name,
                        'api_base': proxy.api_base,
                        'is_active': proxy.is_active,
                        'model_count': len(proxy.models)
                    } for proxy in proxy_pool.proxies[:5]  # 只显示前5个
                ]
            }
        })
    except Exception as e:
        logger.error(f"测试代理池状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'测试失败: {str(e)}'
        }), 500

def _make_proxy_request(proxy, model, messages, timeout=15, max_tokens=50):
    """统一的代理API请求方法"""
    import requests

    # 构建请求
    url = f"{proxy.api_base}/v1/chat/completions"
    headers = {
        'Authorization': f'Bearer {proxy.get_current_key()}',
        'Content-Type': 'application/json'
    }

    # 构建请求数据
    data = {
        'model': model,
        'messages': messages,
        'temperature': 0.3,
        'max_tokens': max_tokens
    }

    # 发送请求
    return requests.post(url, headers=headers, json=data, timeout=timeout, verify=False)

@api_proxy_management_bp.route('/status', methods=['GET'])
@token_required
def get_api_proxy_status(current_user):
    """获取API代理池状态"""
    try:
        proxy_pool = get_api_proxy_pool()
        status = proxy_pool.get_pool_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"获取API代理池状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取API代理池状态失败'
        }), 500

@api_proxy_management_bp.route('/list', methods=['GET'])
@token_required
def get_api_proxy_list(current_user):
    """获取API代理列表"""
    try:
        proxy_pool = get_api_proxy_pool()
        proxies = proxy_pool.proxies
        
        # 获取查询参数
        status_filter = request.args.get('status', 'all')  # all, active, inactive, healthy
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        # 过滤代理
        filtered_proxies = []
        for proxy in proxies:
            # 状态过滤
            if status_filter == 'active' and not proxy.is_active:
                continue
            elif status_filter == 'inactive' and proxy.is_active:
                continue
            elif status_filter == 'healthy' and not proxy.is_healthy():
                continue
            
            # 搜索过滤
            if search and search.lower() not in proxy.name.lower() and search.lower() not in proxy.api_base.lower():
                continue
                
            filtered_proxies.append(proxy)
        
        # 分页
        total = len(filtered_proxies)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_proxies = filtered_proxies[start:end]
        
        return jsonify({
            'success': True,
            'data': {
                'proxies': [proxy.to_dict() for proxy in paginated_proxies],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取API代理列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取API代理列表失败'
        }), 500

@api_proxy_management_bp.route('/add', methods=['POST'])
@admin_required
def add_api_proxy(current_user):
    """添加API代理"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        # 验证必填字段
        required_fields = ['name', 'api_base', 'api_keys', 'model', 'models']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400
        
        proxy_pool = get_api_proxy_pool()
        
        # 添加代理
        success = proxy_pool.add_proxy(
            name=data['name'],
            api_base=data['api_base'],
            api_keys=data['api_keys'],
            model=data['model'],
            models=data['models'],
            is_active=data.get('is_active', True),
            priority=data.get('priority', 1)
        )
        
        if not success:
            return jsonify({
                'success': False,
                'message': '代理已存在或添加失败'
            }), 409
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但代理已添加到内存中")
        
        logger.info(f"管理员 {current_user.username} 添加API代理: {data['name']}")
        
        return jsonify({
            'success': True,
            'message': 'API代理添加成功'
        })
        
    except Exception as e:
        logger.error(f"添加API代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '添加API代理失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>', methods=['DELETE'])
@admin_required
def delete_api_proxy(current_user, proxy_name):
    """删除API代理"""
    try:
        proxy_pool = get_api_proxy_pool()
        
        success = proxy_pool.remove_proxy(proxy_name)
        if not success:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但代理已从内存中移除")
        
        logger.info(f"管理员 {current_user.username} 删除API代理: {proxy_name}")
        
        return jsonify({
            'success': True,
            'message': 'API代理删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除API代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '删除API代理失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>', methods=['PUT'])
@admin_required
def update_api_proxy(current_user, proxy_name):
    """更新API代理"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        # 验证必填字段
        required_fields = ['api_base', 'api_keys', 'model', 'models']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400
                
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 更新代理信息
        proxy.api_base = data['api_base'].rstrip('/')
        proxy.api_keys = data['api_keys']
        proxy.model = data['model']
        proxy.models = data['models']
        
        # 如果提供了这些可选字段，就更新它们
        if 'is_active' in data:
            proxy.is_active = bool(data['is_active'])
        
        if 'priority' in data:
            try:
                priority = int(data['priority'])
                if priority < 1:
                    return jsonify({
                        'success': False,
                        'message': '优先级必须大于等于1'
                    }), 400
                proxy.priority = priority
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'message': '优先级必须是整数'
                }), 400
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但代理已更新到内存中")
        
        logger.info(f"管理员 {current_user.username} 更新API代理: {proxy_name}")
        
        return jsonify({
            'success': True,
            'message': 'API代理更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新API代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新API代理失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/status', methods=['PUT'])
@admin_required
def update_api_proxy_status(current_user, proxy_name):
    """更新API代理状态"""
    try:
        data = request.get_json()
        if not data or 'is_active' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        is_active = bool(data['is_active'])
        proxy_pool = get_api_proxy_pool()
        
        success = proxy_pool.update_proxy_status(proxy_name, is_active)
        if not success:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但代理状态已更新")
        
        logger.info(f"管理员 {current_user.username} 更新API代理状态: {proxy_name} -> {'活跃' if is_active else '非活跃'}")
        
        return jsonify({
            'success': True,
            'message': f"API代理已{'启用' if is_active else '禁用'}"
        })
        
    except Exception as e:
        logger.error(f"更新API代理状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新API代理状态失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/priority', methods=['PUT'])
@admin_required
def update_api_proxy_priority(current_user, proxy_name):
    """更新API代理优先级"""
    try:
        data = request.get_json()
        if not data or 'priority' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        priority = int(data['priority'])
        if priority < 1:
            return jsonify({
                'success': False,
                'message': '优先级必须大于等于1'
            }), 400
            
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 更新优先级
        proxy.priority = priority
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但代理优先级已更新")
        
        logger.info(f"管理员 {current_user.username} 更新API代理优先级: {proxy_name} -> {priority}")
        
        return jsonify({
            'success': True,
            'message': f"API代理优先级已更新为 {priority}"
        })
        
    except Exception as e:
        logger.error(f"更新API代理优先级异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新API代理优先级失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/reset', methods=['POST'])
@admin_required
def reset_api_proxy_errors(current_user, proxy_name):
    """重置API代理错误计数"""
    try:
        proxy_pool = get_api_proxy_pool()
        success = proxy_pool.reset_proxy_errors(proxy_name)
        
        if not success:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
        
        logger.info(f"管理员 {current_user.username} 重置API代理错误计数: {proxy_name}")
        
        return jsonify({
            'success': True,
            'message': 'API代理错误计数已重置'
        })
        
    except Exception as e:
        logger.error(f"重置API代理错误计数异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '重置API代理错误计数失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/test', methods=['POST'])
@token_required
def test_api_proxy(current_user, proxy_name):
    """测试API代理连接"""
    try:
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)

        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404

        # 执行测试请求，使用chat/completions接口
        import time
        start_time = time.time()

        try:
            # 获取请求中指定的模型，如果没有则使用代理默认模型
            request_data = request.get_json() or {}
            model = request_data.get('model')
            
            # 如果没有指定模型或指定的模型不在支持列表中，则使用代理默认模型
            if not model or (len(proxy.models) > 0 and model not in proxy.models):
                model = proxy.model
            
            # 使用统一的API请求方法，使用真实的考试题目
            test_question = random.choice(TEST_QUESTIONS)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": test_question}
            ]

            logger.info(f"测试API代理 {proxy_name}，使用模型: {model}")
            response = _make_proxy_request(proxy, model, messages, timeout=15, max_tokens=50)
            response_time = round((time.time() - start_time) * 1000, 2)

            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                proxy.record_success(response_time / 1000)
                return jsonify({
                    'success': True,
                    'message': 'API代理测试成功',
                    'data': {
                        'response_time': response_time,
                        'status_code': response.status_code,
                        'model': model,
                        'content': content
                    }
                })
            else:
                proxy.record_error()
                error_message = f'API代理测试失败: HTTP {response.status_code}'
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_message += f" - {error_data['error'].get('message', '')}"
                except:
                    pass
                
                return jsonify({
                    'success': False,
                    'message': error_message,
                    'data': {
                        'response_time': response_time,
                        'status_code': response.status_code,
                        'model': model
                    }
                })

        except Exception as e:
            proxy.record_error()
            return jsonify({
                'success': False,
                'message': f'API代理测试失败: {str(e)}',
                'data': {
                    'response_time': round((time.time() - start_time) * 1000, 2)
                }
            })

    except Exception as e:
        logger.error(f"测试API代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '测试API代理失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>', methods=['GET'])
@token_required
def get_api_proxy_detail(current_user, proxy_name):
    """获取API代理详情"""
    try:
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)

        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404

        # 获取详细信息，包括完整的 API 密钥
        proxy_data = proxy.to_dict()
        # 添加完整的 API 密钥信息
        proxy_data['api_keys'] = proxy.api_keys

        return jsonify({
            'success': True,
            'data': proxy_data
        })

    except Exception as e:
        logger.error(f"获取API代理详情异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取API代理详情失败'
        }), 500

@api_proxy_management_bp.route('/reload', methods=['POST'])
@admin_required
def reload_api_proxy_config(current_user):
    """重新加载API代理配置"""
    try:
        reload_proxy_pool()

        logger.info(f"管理员 {current_user.username} 重新加载API代理配置")

        return jsonify({
            'success': True,
            'message': 'API代理配置已重新加载'
        })

    except Exception as e:
        logger.error(f"重新加载API代理配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '重新加载API代理配置失败'
        }), 500


@api_proxy_management_bp.route('/batch', methods=['POST'])
@admin_required
def batch_api_proxy_operation(current_user):
    """批量操作API代理"""
    try:
        data = request.get_json()
        if not data or 'action' not in data or 'names' not in data:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400

        action = data['action']
        names = data['names']

        if not isinstance(names, list) or len(names) == 0:
            return jsonify({
                'success': False,
                'message': '代理名称列表不能为空'
            }), 400

        proxy_pool = get_api_proxy_pool()
        results = []

        for name in names:
            try:
                if action == 'activate':
                    success = proxy_pool.update_proxy_status(name, True)
                elif action == 'deactivate':
                    success = proxy_pool.update_proxy_status(name, False)
                elif action == 'reset':
                    success = proxy_pool.reset_proxy_errors(name)
                else:
                    success = False

                results.append({
                    'name': name,
                    'success': success,
                    'message': '操作成功' if success else '代理不存在'
                })
            except Exception as e:
                results.append({
                    'name': name,
                    'success': False,
                    'message': str(e)
                })

        # 保存配置
        save_proxy_config(proxy_pool)

        success_count = sum(1 for r in results if r['success'])

        logger.info(f"管理员 {current_user.username} 批量{action}操作: {success_count}/{len(names)} 成功")

        return jsonify({
            'success': True,
            'message': f'批量操作完成: {success_count}/{len(names)} 成功',
            'data': {
                'results': results,
                'success_count': success_count,
                'total_count': len(names)
            }
        })

    except Exception as e:
        logger.error(f"批量操作API代理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '批量操作失败'
        }), 500

@api_proxy_management_bp.route('/health-check', methods=['POST'])
@admin_required
def trigger_health_check(current_user):
    """触发健康检查"""
    try:
        proxy_pool = get_api_proxy_pool()

        # 手动触发所有代理的健康检查
        results = []
        for proxy in proxy_pool.proxies:
            try:
                proxy_pool._perform_health_check(proxy)
                results.append({
                    'name': proxy.name,
                    'success': True,
                    'is_healthy': proxy.is_healthy(),
                    'is_active': proxy.is_active
                })
            except Exception as e:
                results.append({
                    'name': proxy.name,
                    'success': False,
                    'error': str(e)
                })

        healthy_count = sum(1 for r in results if r.get('is_healthy', False))

        logger.info(f"管理员 {current_user.username} 触发健康检查: {healthy_count}/{len(results)} 健康")

        return jsonify({
            'success': True,
            'message': f'健康检查完成: {healthy_count}/{len(results)} 健康',
            'data': {
                'results': results,
                'healthy_count': healthy_count,
                'total_count': len(results)
            }
        })

    except Exception as e:
        logger.error(f"触发健康检查异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '健康检查失败'
        }), 500

@api_proxy_management_bp.route('/models/discover', methods=['POST'])
@admin_required
def discover_models_from_api(current_user):
    """根据API和密钥自动发现支持的模型"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        api_base = data.get('api_base', '').strip()
        api_key = data.get('api_key', '').strip()

        if not api_base or not api_key:
            return jsonify({
                'success': False,
                'message': '请提供API地址和密钥'
            }), 400

        # 确保API地址格式正确
        if not api_base.startswith(('http://', 'https://')):
            api_base = 'https://' + api_base

        discovered_models = []
        tested_models = []

        # 方法1: 尝试通过 /v1/models 接口获取模型列表
        try:
            url = f"{api_base}/v1/models"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                models_data = response.json()
                if 'data' in models_data:
                    discovered_models = [model.get('id') for model in models_data['data'] if model.get('id')]
                    logger.info(f"通过/v1/models接口发现 {len(discovered_models)} 个模型")
        except Exception as e:
            logger.debug(f"通过/v1/models接口获取模型失败: {str(e)}")

        # 方法2: 如果没有发现模型，使用常用模型列表进行测试
        if not discovered_models:
            common_models = [
                'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo',
                'claude-3-5-sonnet-20241022', 'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro',
                'llama-3.1-70b', 'llama-3.1-8b', 'llama-3-70b', 'llama-3-8b',
                'mistral-large', 'mistral-medium', 'mistral-small',
                'qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen2.5-72b',
                'glm-4', 'glm-4-plus', 'deepseek-chat', 'deepseek-coder'
            ]
            discovered_models = common_models

        # 限制测试数量，避免过多请求
        test_models = discovered_models[:15]  # 最多测试15个模型

        # 并发测试模型可用性
        available_models = []
        import concurrent.futures
        import threading

        def test_single_model(model):
            """测试单个模型"""
            try:
                # 使用简单的测试消息
                test_messages = [{"role": "user", "content": "Hello"}]

                url = f"{api_base}/v1/chat/completions"
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                payload = {
                    'model': model,
                    'messages': test_messages,
                    'max_tokens': 5,
                    'temperature': 0.1
                }

                start_time = time.time()
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response_time = round((time.time() - start_time) * 1000, 2)

                test_result = {
                    'model': model,
                    'success': False,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'message': ''
                }

                if response.status_code == 200:
                    test_result['success'] = True
                    test_result['message'] = '测试成功'
                    logger.info(f"模型 {model} 测试成功，响应时间: {response_time}ms")
                elif response.status_code == 429:
                    # 被限流也认为模型可用
                    test_result['success'] = True
                    test_result['message'] = '被限流，但模型可用'
                    logger.info(f"模型 {model} 被限流，但认为可用")
                else:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                        test_result['message'] = error_msg
                        logger.debug(f"模型 {model} 测试失败: {error_msg}")
                    except:
                        test_result['message'] = f'HTTP {response.status_code}'
                        logger.debug(f"模型 {model} 测试失败: HTTP {response.status_code}")

                return test_result

            except Exception as e:
                logger.debug(f"测试模型 {model} 异常: {str(e)}")
                return {
                    'model': model,
                    'success': False,
                    'status_code': None,
                    'response_time': None,
                    'message': f'测试异常: {str(e)}'
                }

        # 使用线程池并发测试，限制并发数避免触发限流
        max_workers = min(3, len(test_models))  # 最多3个并发
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有测试任务
            future_to_model = {executor.submit(test_single_model, model): model for model in test_models}

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    result = future.result()
                    tested_models.append(result)

                    # 成功的模型和被限流的模型都认为是可用的
                    if result['success']:
                        available_models.append(model)

                except Exception as e:
                    logger.error(f"测试模型 {model} 时发生异常: {str(e)}")
                    tested_models.append({
                        'model': model,
                        'success': False,
                        'status_code': None,
                        'response_time': None,
                        'message': f'测试异常: {str(e)}'
                    })

        # 智能选择最合适的模型
        best_model = None
        if available_models:
            # 优先级排序：性能好的模型优先
            model_priority = {
                'gpt-4o': 100, 'gpt-4o-mini': 95, 'gpt-4-turbo': 90, 'gpt-4': 85,
                'claude-3-5-sonnet-20241022': 98, 'claude-3-opus': 88, 'claude-3-sonnet': 82,
                'gemini-1.5-pro': 80, 'gemini-1.5-flash': 75,
                'qwen-max': 70, 'qwen-plus': 65, 'glm-4-plus': 60, 'glm-4': 55,
                'gpt-3.5-turbo': 50
            }

            # 按优先级排序
            available_models.sort(key=lambda x: model_priority.get(x, 0), reverse=True)
            best_model = available_models[0]

        logger.info(f"管理员 {current_user.username} 发现模型: 总计 {len(discovered_models)} 个，可用 {len(available_models)} 个")

        return jsonify({
            'success': True,
            'message': f'模型发现完成，找到 {len(available_models)} 个可用模型',
            'data': {
                'discovered_models': discovered_models,
                'available_models': available_models,
                'best_model': best_model,
                'test_results': tested_models
            }
        })

    except Exception as e:
        logger.error(f"发现模型异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '发现模型失败'
        }), 500

@api_proxy_management_bp.route('/models', methods=['GET'])
@token_required
def get_supported_models(current_user):
    """获取所有支持的模型列表"""
    try:
        proxy_pool = get_api_proxy_pool()

        # 收集所有代理中已配置的模型
        all_models = set()
        for proxy in proxy_pool.proxies:
            all_models.update(proxy.models)

        # 尝试通过API获取更多模型
        logger.info("尝试从活跃代理获取模型列表")
        active_proxies = [p for p in proxy_pool.proxies if p.is_active]

        # 如果有活跃代理，则尝试获取模型列表
        if active_proxies:
            # 先尝试通过/v1/models接口获取完整模型列表
            for proxy in active_proxies[:2]:  # 最多尝试2个代理
                try:
                    url = f"{proxy.api_base}/v1/models"
                    headers = {
                        'Authorization': f'Bearer {proxy.get_current_key()}',
                        'Content-Type': 'application/json'
                    }
                    
                    response = requests.get(url, headers=headers, timeout=10, verify=False)
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'data' in result and isinstance(result['data'], list):
                            models = [item.get('id') for item in result['data'] if item.get('id')]
                            if models:
                                all_models.update(models)
                                logger.info(f"从代理 {proxy.name} 的/v1/models接口获取到 {len(models)} 个模型")
                                
                                # 更新代理的模型列表
                                proxy.models = list(set(proxy.models + models))
                                
                                # 保存配置
                                save_proxy_config(proxy_pool)
                except Exception as e:
                    logger.error(f"从代理 {proxy.name} 的/v1/models接口获取模型列表失败: {str(e)}")
            
            # 常用模型列表
            common_models = [
                'gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 
                'claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku',
                'gemini-1.5-pro', 'gemini-pro',
                'llama-3-70b', 'llama-3-8b',
                'mistral-large', 'mistral-medium',
                'qwen-max', 'qwen-plus', 'qwen-turbo',
                'glm-4'
            ]
            
            # 如果all_models为空，则使用常用模型列表进行测试
            test_models = list(all_models) if all_models else common_models
            
            # 为避免测试过多模型，最多测试20个
            if len(test_models) > 20:
                test_models = random.sample(test_models, 20)

            # 记录测试成功的模型
            verified_models = set()

            # 对每个代理进行测试
            for proxy in active_proxies[:2]:  # 最多尝试2个代理
                # 使用统一的系统提示词和真实的考试题目
                test_question = random.choice(TEST_QUESTIONS)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": test_question}
                ]

                # 测试每个模型
                for model in test_models:
                    try:
                        response = _make_proxy_request(proxy, model, messages, timeout=5, max_tokens=10)

                        if response.status_code == 200:
                            verified_models.add(model)
                            logger.info(f"模型 {model} 在代理 {proxy.name} 上测试成功")
                        else:
                            logger.debug(f"模型 {model} 在代理 {proxy.name} 上测试失败: HTTP {response.status_code}")
                    except Exception as e:
                        logger.debug(f"测试模型 {model} 在代理 {proxy.name} 上失败: {str(e)}")
                
                # 如果已经找到了足够多的模型，就不再继续测试
                if len(verified_models) >= 5:
                    break
            
            # 更新所有模型列表
            all_models.update(verified_models)
            
            # 如果验证了新模型，更新代理配置
            if verified_models:
                for proxy in active_proxies:
                    proxy.models = list(set(proxy.models + list(verified_models)))
                
                # 保存配置
                save_proxy_config(proxy_pool)
                logger.info(f"通过/v1/chat/completions接口验证了 {len(verified_models)} 个模型")

        return jsonify({
            'success': True,
            'data': {
                'models': sorted(list(all_models)),
                'count': len(all_models)
            }
        })

    except Exception as e:
        logger.error(f"获取支持模型列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取支持模型列表失败'
        }), 500

@api_proxy_management_bp.route('/export', methods=['GET'])
@admin_required
def export_api_proxy_config(current_user):
    """导出API代理配置"""
    try:
        proxy_pool = get_api_proxy_pool()
        
        # 构建配置数据
        export_data = {
            "third_party_apis": []
        }
        
        for proxy in proxy_pool.proxies:
            proxy_data = {
                "name": proxy.name,
                "api_base": proxy.api_base,
                "api_keys": proxy.api_keys,
                "model": proxy.model,
                "models": proxy.models,
                "is_active": proxy.is_active,
                "priority": proxy.priority
            }
            export_data["third_party_apis"].append(proxy_data)
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        temp_file_path = temp_file.name
        
        # 写入数据
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"管理员 {current_user.username} 导出API代理配置，共 {len(proxy_pool.proxies)} 个代理")
        
        # 发送文件
        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f"api_proxy_config_{int(time.time())}.json",
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"导出API代理配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '导出API代理配置失败'
        }), 500

@api_proxy_management_bp.route('/import', methods=['POST'])
@admin_required
def import_api_proxy_config(current_user):
    """导入API代理配置"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有上传文件'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '未选择文件'
            }), 400
        
        # 检查文件类型
        if not file.filename or not file.filename.endswith('.json'):
            return jsonify({
                'success': False,
                'message': '只支持导入JSON格式的配置文件'
            }), 400
        
        # 读取文件内容
        try:
            config_data = json.loads(file.read().decode('utf-8'))
        except json.JSONDecodeError:
            return jsonify({
                'success': False,
                'message': 'JSON格式错误'
            }), 400
        
        # 验证配置格式
        if 'third_party_apis' not in config_data or not isinstance(config_data['third_party_apis'], list):
            return jsonify({
                'success': False,
                'message': '配置格式错误，缺少third_party_apis字段或格式不正确'
            }), 400
        
        # 获取代理池
        proxy_pool = get_api_proxy_pool()
        
        # 记录导入结果
        results = {
            'added': [],
            'updated': [],
            'failed': []
        }
        
        # 导入代理
        for proxy_data in config_data['third_party_apis']:
            try:
                # 检查必填字段
                required_fields = ['name', 'api_base', 'api_keys', 'model', 'models']
                if not all(field in proxy_data for field in required_fields):
                    results['failed'].append({
                        'name': proxy_data.get('name', '未知'),
                        'reason': '缺少必填字段'
                    })
                    continue
                
                # 检查代理是否已存在
                existing_proxy = proxy_pool.get_proxy_by_name(proxy_data['name'])
                if existing_proxy:
                    # 更新现有代理
                    existing_proxy.api_base = proxy_data['api_base'].rstrip('/')
                    existing_proxy.api_keys = proxy_data['api_keys']
                    existing_proxy.model = proxy_data['model']
                    existing_proxy.models = proxy_data['models']
                    
                    if 'is_active' in proxy_data:
                        existing_proxy.is_active = bool(proxy_data['is_active'])
                    
                    if 'priority' in proxy_data:
                        existing_proxy.priority = int(proxy_data['priority'])
                    
                    results['updated'].append(proxy_data['name'])
                else:
                    # 添加新代理
                    success = proxy_pool.add_proxy(
                        name=proxy_data['name'],
                        api_base=proxy_data['api_base'],
                        api_keys=proxy_data['api_keys'],
                        model=proxy_data['model'],
                        models=proxy_data['models'],
                        is_active=proxy_data.get('is_active', True),
                        priority=proxy_data.get('priority', 1)
                    )
                    
                    if success:
                        results['added'].append(proxy_data['name'])
                    else:
                        results['failed'].append({
                            'name': proxy_data['name'],
                            'reason': '添加失败'
                        })
            except Exception as e:
                results['failed'].append({
                    'name': proxy_data.get('name', '未知'),
                    'reason': str(e)
                })
        
        # 保存配置
        save_proxy_config(proxy_pool)
        
        logger.info(f"管理员 {current_user.username} 导入API代理配置: 添加 {len(results['added'])}，更新 {len(results['updated'])}，失败 {len(results['failed'])}")
        
        return jsonify({
            'success': True,
            'message': f"导入完成: 添加 {len(results['added'])}，更新 {len(results['updated'])}，失败 {len(results['failed'])}",
            'data': results
        })
        
    except Exception as e:
        logger.error(f"导入API代理配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '导入API代理配置失败'
        }), 500

@api_proxy_management_bp.route('/validate', methods=['POST'])
@admin_required
def validate_api_proxy_config(current_user):
    """验证API代理配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        # 验证配置格式
        if 'third_party_apis' not in data or not isinstance(data['third_party_apis'], list):
            return jsonify({
                'success': False,
                'message': '配置格式错误，缺少third_party_apis字段或格式不正确'
            }), 400
        
        # 验证每个代理配置
        validation_results = []
        for proxy_data in data['third_party_apis']:
            result = {
                'name': proxy_data.get('name', '未知'),
                'valid': True,
                'issues': []
            }
            
            # 检查必填字段
            required_fields = ['name', 'api_base', 'api_keys', 'model', 'models']
            for field in required_fields:
                if field not in proxy_data:
                    result['valid'] = False
                    result['issues'].append(f'缺少必填字段: {field}')
            
            # 检查API基础URL格式
            if 'api_base' in proxy_data and not proxy_data['api_base'].startswith(('http://', 'https://')):
                result['valid'] = False
                result['issues'].append('API基础URL格式错误，应以http://或https://开头')
            
            # 检查API密钥
            if 'api_keys' in proxy_data:
                if not isinstance(proxy_data['api_keys'], list):
                    result['valid'] = False
                    result['issues'].append('API密钥应为数组格式')
                elif len(proxy_data['api_keys']) == 0:
                    result['valid'] = False
                    result['issues'].append('至少需要一个API密钥')
            
            # 检查模型
            if 'models' in proxy_data:
                if not isinstance(proxy_data['models'], list):
                    result['valid'] = False
                    result['issues'].append('支持模型应为数组格式')
                elif len(proxy_data['models']) == 0:
                    result['valid'] = False
                    result['issues'].append('至少需要一个支持模型')
            
            # 检查默认模型是否在支持模型列表中
            if 'model' in proxy_data and 'models' in proxy_data and isinstance(proxy_data['models'], list):
                if proxy_data['model'] not in proxy_data['models']:
                    result['valid'] = False
                    result['issues'].append('默认模型不在支持模型列表中')
            
            validation_results.append(result)
        
        # 计算总体验证结果
        is_valid = all(result['valid'] for result in validation_results)
        
        return jsonify({
            'success': True,
            'data': {
                'is_valid': is_valid,
                'results': validation_results
            }
        })
        
    except Exception as e:
        logger.error(f"验证API代理配置异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '验证API代理配置失败'
        }), 500

@api_proxy_management_bp.route('/alert-rules', methods=['POST'])
@admin_required
def set_api_proxy_alert_rules(current_user):
    """设置API代理告警规则"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        proxy_pool = get_api_proxy_pool()
        
        # 更新告警规则
        rules = {
            'success_rate_threshold': data.get('success_rate_threshold', 80),  # 成功率低于此值触发告警（百分比）
            'response_time_threshold': data.get('response_time_threshold', 5000),  # 响应时间高于此值触发告警（毫秒）
            'consecutive_errors_threshold': data.get('consecutive_errors_threshold', 5),  # 连续错误次数
            'notification_email': data.get('notification_email', ''),  # 告警通知邮箱
            'notification_webhook': data.get('notification_webhook', ''),  # 告警通知Webhook
            'alert_enabled': data.get('alert_enabled', False)  # 是否启用告警
        }
        
        # 读取当前配置文件
        config_file = proxy_pool.config_file
        if not os.path.exists(config_file):
            return jsonify({
                'success': False,
                'message': '配置文件不存在'
            }), 500
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新告警规则配置
        config['api_proxy_alert_rules'] = rules
        
        # 写回配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"管理员 {current_user.username} 更新API代理告警规则")
        
        return jsonify({
            'success': True,
            'message': 'API代理告警规则已更新',
            'data': rules
        })
        
    except Exception as e:
        logger.error(f"设置API代理告警规则异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '设置API代理告警规则失败'
        }), 500

@api_proxy_management_bp.route('/alert-rules', methods=['GET'])
@token_required
def get_api_proxy_alert_rules(current_user):
    """获取API代理告警规则"""
    try:
        proxy_pool = get_api_proxy_pool()
        
        # 读取当前配置文件
        config_file = proxy_pool.config_file
        if not os.path.exists(config_file):
            return jsonify({
                'success': False,
                'message': '配置文件不存在'
            }), 500
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 获取告警规则配置
        rules = config.get('api_proxy_alert_rules', {})
        
        # 如果没有配置，返回默认值
        if not rules:
            rules = {
                'success_rate_threshold': 80,
                'response_time_threshold': 5000,
                'consecutive_errors_threshold': 5,
                'notification_email': '',
                'notification_webhook': '',
                'alert_enabled': False
            }
        
        return jsonify({
            'success': True,
            'data': rules
        })
        
    except Exception as e:
        logger.error(f"获取API代理告警规则异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取API代理告警规则失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/keys', methods=['GET'])
@admin_required
def get_proxy_keys(current_user, proxy_name):
    """获取代理的API密钥列表"""
    try:
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        return jsonify({
            'success': True,
            'data': {
                'keys': proxy.api_keys,
                'current_key_index': proxy.current_key_index
            }
        })
        
    except Exception as e:
        logger.error(f"获取代理密钥列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取代理密钥列表失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/keys', methods=['PUT'])
@admin_required
def update_proxy_keys(current_user, proxy_name):
    """更新代理的API密钥列表"""
    try:
        data = request.get_json()
        if not data or 'keys' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
            
        keys = data['keys']
        if not isinstance(keys, list):
            return jsonify({
                'success': False,
                'message': 'keys必须是数组格式'
            }), 400
            
        if len(keys) == 0:
            return jsonify({
                'success': False,
                'message': '至少需要一个API密钥'
            }), 400
            
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 更新密钥列表
        proxy.api_keys = keys
        proxy.current_key_index = 0  # 重置当前密钥索引
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但密钥已更新到内存中")
        
        logger.info(f"管理员 {current_user.username} 更新代理 {proxy_name} 的API密钥列表，共 {len(keys)} 个密钥")
        
        return jsonify({
            'success': True,
            'message': f'API密钥列表已更新，共 {len(keys)} 个密钥'
        })
        
    except Exception as e:
        logger.error(f"更新代理密钥列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新代理密钥列表失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/keys/add', methods=['POST'])
@admin_required
def add_proxy_key(current_user, proxy_name):
    """添加API密钥到代理"""
    try:
        data = request.get_json()
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
            
        key = data['key'].strip()
        if not key:
            return jsonify({
                'success': False,
                'message': 'API密钥不能为空'
            }), 400
            
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 检查密钥是否已存在
        if key in proxy.api_keys:
            return jsonify({
                'success': False,
                'message': '密钥已存在'
            }), 409
            
        # 添加密钥
        proxy.api_keys.append(key)
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但密钥已添加到内存中")
        
        logger.info(f"管理员 {current_user.username} 为代理 {proxy_name} 添加API密钥")
        
        return jsonify({
            'success': True,
            'message': 'API密钥已添加',
            'data': {
                'keys': proxy.api_keys,
                'key_count': len(proxy.api_keys)
            }
        })
        
    except Exception as e:
        logger.error(f"添加代理密钥异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '添加代理密钥失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/keys/remove', methods=['POST'])
@admin_required
def remove_proxy_key(current_user, proxy_name):
    """从代理中移除API密钥"""
    try:
        data = request.get_json()
        if not data or 'key' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
            
        key = data['key']
        
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 检查是否只有一个密钥
        if len(proxy.api_keys) <= 1:
            return jsonify({
                'success': False,
                'message': '至少需要保留一个API密钥'
            }), 400
            
        # 检查密钥是否存在
        if key not in proxy.api_keys:
            return jsonify({
                'success': False,
                'message': '密钥不存在'
            }), 404
            
        # 移除密钥
        proxy.api_keys.remove(key)
        
        # 如果当前密钥索引超出范围，重置为0
        if proxy.current_key_index >= len(proxy.api_keys):
            proxy.current_key_index = 0
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但密钥已从内存中移除")
        
        logger.info(f"管理员 {current_user.username} 从代理 {proxy_name} 移除API密钥")
        
        return jsonify({
            'success': True,
            'message': 'API密钥已移除',
            'data': {
                'keys': proxy.api_keys,
                'key_count': len(proxy.api_keys)
            }
        })
        
    except Exception as e:
        logger.error(f"移除代理密钥异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '移除代理密钥失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/available-models', methods=['PUT'])
@admin_required
def update_available_models(current_user, proxy_name):
    """更新代理的可用模型列表"""
    try:
        data = request.get_json()
        if not data or 'models' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
            
        models = data['models']
        if not isinstance(models, list):
            return jsonify({
                'success': False,
                'message': '模型列表必须是数组格式'
            }), 400
            
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        # 更新可用模型列表
        proxy.available_models = models
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但可用模型列表已更新到内存中")
        
        logger.info(f"管理员 {current_user.username} 更新代理 {proxy_name} 的可用模型列表，共 {len(models)} 个模型")
        
        return jsonify({
            'success': True,
            'message': f'可用模型列表已更新，共 {len(models)} 个模型',
            'data': {
                'available_models': models
            }
        })
        
    except Exception as e:
        logger.error(f"更新可用模型列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新可用模型列表失败'
        }), 500

@api_proxy_management_bp.route('/<proxy_name>/available-models/test', methods=['POST'])
@admin_required
def test_model_availability(current_user, proxy_name):
    """测试模型可用性并更新可用模型列表"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
            
        # 获取要测试的模型，如果没有指定则测试所有模型
        test_models = data.get('models', [])
        max_test_count = data.get('max_test_count', 10)  # 最大测试数量，避免测试过多模型
        
        proxy_pool = get_api_proxy_pool()
        proxy = proxy_pool.get_proxy_by_name(proxy_name)
        
        if not proxy:
            return jsonify({
                'success': False,
                'message': '代理不存在'
            }), 404
            
        if not proxy.is_active:
            return jsonify({
                'success': False,
                'message': '代理未激活，无法测试模型'
            }), 400
            
        # 如果没有指定测试模型，则使用代理的所有模型
        if not test_models:
            test_models = proxy.models
            
        # 限制测试数量（当max_test_count >= 999时，测试所有模型）
        if max_test_count > 0 and max_test_count < 999 and len(test_models) > max_test_count:
            import random
            test_models = random.sample(test_models, max_test_count)
            logger.info(f"限制测试模型数量为 {max_test_count}，从 {len(proxy.models)} 个模型中随机选择")
        else:
            logger.info(f"测试代理 {proxy_name} 的所有 {len(test_models)} 个模型")
            
        # 测试结果
        results = []
        available_models = []
        
        # 并发测试每个模型
        import concurrent.futures
        import threading

        def test_single_model(model):
            """测试单个模型"""
            try:
                # 更新进度：正在测试当前模型
                if proxy_name in test_progress_cache:
                    test_progress_cache[proxy_name]['current_model'] = model
                    test_progress_cache[proxy_name]['status'] = 'testing'

                # 使用统一的API请求方法，使用真实的考试题目
                import random as rand  # 在函数内部导入避免作用域问题
                test_question = rand.choice(TEST_QUESTIONS)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": test_question}
                ]

                # 发送请求
                start_time = time.time()
                response = _make_proxy_request(proxy, model, messages,
                                             timeout=data.get('timeout_per_model', 15), max_tokens=10)
                response_time = round((time.time() - start_time) * 1000, 2)  # 毫秒

                # 判断测试结果
                # 200 = 成功
                # 429 = 请求频繁（视为部分成功，模型存在但被限流）
                # 503 = 服务不可用（通常是无可用渠道，模型可能存在）
                is_success = response.status_code == 200
                is_rate_limited = response.status_code == 429
                is_no_channel = response.status_code == 503

                result = {
                    'model': model,
                    'success': is_success,
                    'rate_limited': is_rate_limited,  # 标识是否被限流
                    'no_channel': is_no_channel,      # 标识是否无可用渠道
                    'status_code': response.status_code,
                    'response_time': response_time
                }

                if response.status_code == 200:
                    result['message'] = '测试成功'
                elif response.status_code == 429:
                    result['message'] = '请求频繁，API限流'
                elif response.status_code == 503:
                    try:
                        error_data = response.json()
                        if 'error' in error_data and '无可用渠道' in error_data['error'].get('message', ''):
                            result['message'] = '无可用渠道（模型可能存在）'
                        else:
                            result['message'] = '服务不可用'
                    except:
                        result['message'] = '服务不可用'
                else:
                    try:
                        error_data = response.json()
                        if 'error' in error_data:
                            result['message'] = error_data['error'].get('message', '未知错误')
                        else:
                            result['message'] = f'HTTP错误: {response.status_code}'
                    except:
                        result['message'] = f'HTTP错误: {response.status_code}'

                # 更新进度：模型测试完成
                if proxy_name in test_progress_cache:
                    test_progress_cache[proxy_name]['tested_models'] += 1
                    test_progress_cache[proxy_name]['results'].append(result)

                return result

            except Exception as e:
                result = {
                    'model': model,
                    'success': False,
                    'rate_limited': False,
                    'no_channel': False,
                    'status_code': None,
                    'response_time': None,
                    'message': str(e)
                }

                # 更新进度：模型测试失败
                if proxy_name in test_progress_cache:
                    test_progress_cache[proxy_name]['tested_models'] += 1
                    test_progress_cache[proxy_name]['results'].append(result)

                return result

        # 使用线程池并发测试，限制并发数避免过载
        max_concurrent = min(len(test_models), data.get('max_concurrent', 5))
        # 初始化进度缓存
        test_progress_cache[proxy_name] = {
            'status': 'started',
            'total_models': len(test_models),
            'tested_models': 0,
            'current_model': None,
            'results': [],
            'completed': False
        }

        logger.info(f"开始并发测试 {len(test_models)} 个模型，并发数: {max_concurrent}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # 提交所有测试任务
            future_to_model = {executor.submit(test_single_model, model): model for model in test_models}

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    result = future.result()
                    results.append(result)

                    # 成功的模型和被限流的模型都认为是可用的
                    # 503无可用渠道的模型暂时不加入可用列表，因为当前确实无法使用
                    if result['success'] or result.get('rate_limited', False):
                        available_models.append(model)

                except Exception as e:
                    logger.error(f"测试模型 {model} 时发生异常: {str(e)}")
                    results.append({
                        'model': model,
                        'success': False,
                        'rate_limited': False,
                        'no_channel': False,
                        'status_code': None,
                        'response_time': None,
                        'message': f'测试异常: {str(e)}'
                    })
        
        # 更新代理的可用模型列表
        proxy.available_models = available_models
        
        # 保存到配置文件
        save_success = save_proxy_config(proxy_pool)
        if not save_success:
            logger.warning("代理配置保存失败，但可用模型列表已更新到内存中")
        
        success_count = len([r for r in results if r.get('success')])
        logger.info(f"管理员 {current_user.username} 测试代理 {proxy_name} 的模型可用性，成功率: {success_count}/{len(results)}")

        # 标记测试完成
        if proxy_name in test_progress_cache:
            test_progress_cache[proxy_name]['status'] = 'completed'
            test_progress_cache[proxy_name]['completed'] = True
            test_progress_cache[proxy_name]['current_model'] = None

        return jsonify({
            'success': True,
            'message': f'模型测试完成，可用模型: {success_count}/{len(results)}',
            'data': {
                'results': results,
                'available_models': available_models
            }
        })
        
    except Exception as e:
        logger.error(f"测试模型可用性异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '测试模型可用性失败'
        }), 500

@api_proxy_management_bp.route('/update-available-models', methods=['POST'])
@admin_required
def update_available_models_config(current_user):
    """更新配置文件中的可用模型列表"""
    try:
        data = request.get_json()
        if not data or 'results' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        results = data['results']

        # 读取当前配置文件
        import json
        import os
        import shutil

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json')

        # 备份原配置文件
        backup_path = f"{config_path}.backup.{int(time.time())}"
        shutil.copy2(config_path, backup_path)
        logger.info(f"配置文件已备份到: {backup_path}")

        # 读取配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        updated_count = 0

        # 更新每个代理的可用模型
        for proxy_config in config_data.get('third_party_apis', []):
            proxy_name = proxy_config.get('name')
            if proxy_name in results:
                result = results[proxy_name]
                if result.get('status') == 'completed' and result.get('available_models'):
                    # 更新可用模型列表
                    proxy_config['available_models'] = result['available_models']
                    updated_count += 1
                    logger.info(f"更新代理 {proxy_name} 的可用模型: {len(result['available_models'])} 个")

        # 写回配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

        logger.info(f"管理员 {current_user.username} 更新了 {updated_count} 个代理的可用模型配置")

        return jsonify({
            'success': True,
            'message': f'配置文件更新成功，已更新 {updated_count} 个代理的可用模型',
            'data': {
                'updated_count': updated_count,
                'backup_path': backup_path
            }
        })

    except Exception as e:
        logger.error(f"更新配置文件异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新配置文件失败'
        }), 500

# 全局变量存储测试进度
test_progress_cache = {}

@api_proxy_management_bp.route('/<proxy_name>/test-progress', methods=['GET'])
@admin_required
def get_test_progress(current_user, proxy_name):
    """获取模型测试进度"""
    try:
        progress = test_progress_cache.get(proxy_name, {
            'status': 'not_started',
            'total_models': 0,
            'tested_models': 0,
            'current_model': None,
            'results': [],
            'completed': False
        })

        return jsonify({
            'success': True,
            'data': progress
        })

    except Exception as e:
        logger.error(f"获取测试进度异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取测试进度失败'
        }), 500
