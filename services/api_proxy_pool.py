# -*- coding: utf-8 -*-
"""
API代理池管理服务
"""
import json
import random
import time
import requests
from typing import List, Dict, Any, Optional
import urllib3
from datetime import datetime
import threading
from threading import Lock
import os

from utils.logger import get_logger
from constants import SYSTEM_PROMPT, TEST_QUESTIONS
import random

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)

class ApiProxy:
    """API代理类"""

    def __init__(self, name: str, api_base: str, api_keys: List[str],
                 model: str, models: List[str], is_active: bool = True, priority: int = 1,
                 available_models: Optional[List[str]] = None):
        self.name = name
        self.api_base = api_base.rstrip('/')
        self.api_keys = api_keys
        self.model = model
        self.models = models
        self.available_models = available_models or []  # 经过测试确认可用的模型列表
        self.is_active = is_active
        self.priority = priority

        # 运行时状态
        self.current_key_index = 0
        self.success_count = 0
        self.error_count = 0
        self.last_used = 0
        self.response_times = []
        self.last_health_check = 0
        self.health_check_interval = 300  # 5分钟
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.created_at = time.time()
        self.disabled_at = 0  # 记录被禁用的时间
        self.auto_recovery_attempts = 0  # 记录自动恢复尝试次数
        self.max_auto_recovery_attempts = 3  # 最大自动恢复尝试次数

        # 增强监控属性
        self.last_success_time = 0.0  # 最后成功时间
        self.request_timestamps = []  # 请求时间戳列表
        self.circuit_breaker_opened_at = 0.0  # 熔断器开启时间
        self.error_types = {}  # 错误类型统计

        # 线程锁
        self._lock = Lock()

    def get_current_key(self) -> str:
        """获取当前API密钥"""
        if not self.api_keys:
            return ""
        return self.api_keys[self.current_key_index % len(self.api_keys)]

    def rotate_key(self):
        """轮换API密钥"""
        with self._lock:
            if len(self.api_keys) > 1:
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                logger.debug(f"代理 {self.name} 轮换到密钥 {self.current_key_index}")

    def record_success(self, response_time: float):
        """记录成功调用"""
        with self._lock:
            current_time = time.time()
            self.success_count += 1
            self.last_used = current_time
            self.last_success_time = current_time
            self.response_times.append(response_time)
            self.consecutive_errors = 0  # 重置连续错误计数

            # 记录请求时间戳
            self.request_timestamps.append(current_time)
            # 保持最近500个时间戳
            if len(self.request_timestamps) > 500:
                self.request_timestamps = self.request_timestamps[-500:]

            # 保持最近100次的响应时间
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]

    def record_error(self, error_type: str = "unknown"):
        """记录错误调用"""
        with self._lock:
            current_time = time.time()
            self.error_count += 1
            self.last_used = current_time
            self.consecutive_errors += 1

            # 记录错误类型统计
            if error_type in self.error_types:
                self.error_types[error_type] += 1
            else:
                self.error_types[error_type] = 1

            # 记录请求时间戳
            self.request_timestamps.append(current_time)
            # 保持最近500个时间戳
            if len(self.request_timestamps) > 500:
                self.request_timestamps = self.request_timestamps[-500:]

            # 如果连续错误过多，暂时禁用代理
            if self.consecutive_errors >= self.max_consecutive_errors:
                logger.warning(f"代理 {self.name} 连续错误 {self.consecutive_errors} 次，暂时禁用，错误类型: {error_type}")
                self.is_active = False
                self.disabled_at = current_time  # 记录禁用时间

    def get_success_rate(self) -> float:
        """获取成功率"""
        total = self.success_count + self.error_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def is_healthy(self) -> bool:
        """检查代理是否健康"""
        if not self.is_active:
            return False

        # 如果成功率太低，认为不健康
        if self.get_success_rate() < 0.5 and (self.success_count + self.error_count) > 10:
            return False

        # 如果连续错误过多，认为不健康
        if self.consecutive_errors >= self.max_consecutive_errors:
            return False

        return True

    def needs_health_check(self) -> bool:
        """检查是否需要健康检查"""
        return time.time() - self.last_health_check > self.health_check_interval

    def update_health_check(self):
        """更新健康检查时间"""
        self.last_health_check = time.time()

    def reset_errors(self):
        """重置错误计数（用于手动恢复代理）"""
        with self._lock:
            self.consecutive_errors = 0
            if not self.is_active:
                self.is_active = True
                logger.info(f"代理 {self.name} 已手动恢复")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'api_base': self.api_base,
            'model': self.model,
            'models': self.models,
            'available_models': self.available_models,
            'is_active': self.is_active,
            'priority': self.priority,
            'key_count': len(self.api_keys),
            'current_key_index': self.current_key_index,
            'current_key': self.get_current_key()[:10] + "..." if self.get_current_key() else "",
            'success_count': self.success_count,
            'error_count': self.error_count,
            'consecutive_errors': self.consecutive_errors,
            'success_rate': round(self.get_success_rate() * 100, 2),
            'avg_response_time': round(self.get_avg_response_time(), 2),
            'last_used': self.last_used,
            'last_used_str': datetime.fromtimestamp(self.last_used).strftime('%Y-%m-%d %H:%M:%S') if self.last_used else "从未使用",
            'is_healthy': self.is_healthy(),
            'created_at': self.created_at,
            'uptime': round(time.time() - self.created_at, 0)
        }

class ApiProxyPool:
    """API代理池管理器"""

    def __init__(self, config_file: Optional[str] = None):
        if config_file is None:
            # 获取项目根目录路径
            import os
            # services/api_proxy_pool.py -> services/ -> 项目根目录
            project_root = os.path.dirname(os.path.dirname(__file__))
            config_path = os.path.join(project_root, 'config.json')

            if os.path.exists(config_path):
                self.config_file = config_path
            else:
                # 如果项目根目录没有找到，尝试其他路径
                possible_paths = [
                    'config.json',
                    '../config.json',
                    '../../config.json'
                ]

                for path in possible_paths:
                    if os.path.exists(path):
                        self.config_file = path
                        break
                else:
                    self.config_file = config_path  # 使用项目根目录路径作为默认值
        else:
            self.config_file = config_file

        self.proxies: List[ApiProxy] = []
        self._lock = Lock()
        self.load_config()

        # 自动恢复设置
        self.auto_recovery_enabled = True  # 是否启用自动恢复
        self.auto_recovery_interval = 1800  # 自动恢复检查间隔（秒），默认30分钟

        # 模型可用性测试设置
        self.model_test_enabled = True  # 是否启用模型可用性测试
        self.model_test_interval = 86400  # 模型测试间隔（秒），默认24小时
        self.model_test_max_count = 5  # 每次测试的模型数量

        # 负载均衡增强配置
        self.load_balancing_enabled = True
        self.circuit_breaker_enabled = True
        self.circuit_breaker_threshold = 5  # 连续失败5次后熔断
        self.circuit_breaker_timeout = 300  # 熔断5分钟

        # 性能监控配置
        self.performance_window = 100  # 保留最近100次请求的性能数据
        self.adaptive_timeout_enabled = True
        self.min_timeout = 10  # 最小超时时间
        self.max_timeout = 60  # 最大超时时间

        # 故障检测增强配置
        self.failure_patterns = {
            'timeout': {'weight': 1.0, 'threshold': 3},
            'connection_error': {'weight': 1.5, 'threshold': 2},
            'auth_error': {'weight': 2.0, 'threshold': 1},
            'rate_limit': {'weight': 0.5, 'threshold': 5},
            'server_error': {'weight': 1.2, 'threshold': 3}
        }

        # 健康检查增强配置
        self.health_check_interval = 300  # 健康检查间隔（秒）
        self.health_check_timeout = 30  # 健康检查超时时间
        self.health_score_threshold = 0.7  # 健康分数阈值

        # 启动健康检查线程
        self._health_check_thread = None
        self._stop_health_check = False
        self.start_health_check()
        
        # 启动模型测试线程
        self._model_test_thread = None
        self._stop_model_test = False
        self.start_model_test()

    def load_config(self):
        """加载配置文件"""
        try:
            logger.info(f"尝试加载配置文件: {self.config_file}")
            logger.info(f"配置文件是否存在: {os.path.exists(self.config_file)}")

            if not os.path.exists(self.config_file):
                logger.error(f"配置文件不存在: {self.config_file}")
                return

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.proxies = []
            third_party_apis = config.get('third_party_apis', [])
            logger.info(f"配置文件中找到 {len(third_party_apis)} 个API配置")

            for api_config in third_party_apis:
                proxy = ApiProxy(
                    name=api_config['name'],
                    api_base=api_config['api_base'],
                    api_keys=api_config['api_keys'],
                    model=api_config['model'],
                    models=api_config['models'],
                    available_models=api_config.get('available_models', []),
                    is_active=api_config.get('is_active', True),
                    priority=api_config.get('priority', 1)
                )
                self.proxies.append(proxy)
                logger.debug(f"加载API代理: {proxy.name} (活跃: {proxy.is_active})")

            active_count = len([p for p in self.proxies if p.is_active])
            logger.info(f"成功加载了 {len(self.proxies)} 个API代理，其中 {active_count} 个处于活跃状态")

        except FileNotFoundError:
            logger.error(f"配置文件不存在: {self.config_file}")
            self.proxies = []
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {str(e)}")
            self.proxies = []
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            self.proxies = []

    def get_active_proxies(self) -> List[ApiProxy]:
        """获取活跃的代理"""
        return [proxy for proxy in self.proxies if proxy.is_active]

    def get_proxy_by_name(self, name: str) -> Optional[ApiProxy]:
        """根据名称获取代理"""
        for proxy in self.proxies:
            if proxy.name == name:
                return proxy
        return None

    def select_best_proxy(self, model: Optional[str] = None) -> Optional[ApiProxy]:
        """选择最佳代理 - 增强版负载均衡算法"""
        active_proxies = self.get_active_proxies()
        if not active_proxies:
            return None

        # 过滤支持指定模型的代理
        if model:
            # 首先尝试在可用模型列表中查找
            available_candidate_proxies = [p for p in active_proxies if model in p.available_models]
            if available_candidate_proxies:
                candidate_proxies = available_candidate_proxies
            else:
                # 如果可用模型列表中没有，则在所有支持模型中查找
                candidate_proxies = [p for p in active_proxies if model in p.models]
                if not candidate_proxies:
                    candidate_proxies = active_proxies
        else:
            candidate_proxies = active_proxies

        # 过滤掉熔断状态的代理
        if self.circuit_breaker_enabled:
            candidate_proxies = [p for p in candidate_proxies if not self._is_circuit_breaker_open(p)]

        if not candidate_proxies:
            logger.warning("所有候选代理都处于熔断状态")
            return None

        # 增强的代理评分算法
        def enhanced_proxy_score(proxy):
            # 基础分数组件
            priority_score = max(0, 100 - proxy.priority)  # 优先级分数
            success_rate = proxy.get_success_rate() * 100  # 成功率分数

            # 响应时间分数（考虑自适应超时）
            response_time_score = 0
            if proxy.response_times:
                avg_time = proxy.get_avg_response_time()
                if avg_time > 0:
                    # 使用对数函数，避免极端值影响
                    response_time_score = max(0, 100 - (avg_time * 10))

            # 健康分数
            health_score = self._calculate_health_score(proxy) * 100

            # 负载分数（基于最近的请求频率）
            load_score = self._calculate_load_score(proxy) * 100

            # 可用模型加分
            available_models_bonus = 20 if proxy.available_models else 0

            # 连续错误惩罚
            error_penalty = min(50, proxy.consecutive_errors * 10)

            # 综合评分（权重可调）
            total_score = (
                priority_score * 0.25 +      # 优先级权重
                success_rate * 0.25 +        # 成功率权重
                response_time_score * 0.15 + # 响应时间权重
                health_score * 0.20 +        # 健康状态权重
                load_score * 0.10 +          # 负载权重
                available_models_bonus * 0.05 # 可用模型加分权重
            ) - error_penalty

            return max(0, total_score)

        # 按分数降序排序
        sorted_proxies = sorted(candidate_proxies, key=enhanced_proxy_score, reverse=True)
        
        if sorted_proxies:
            selected_proxy = sorted_proxies[0]
            logger.debug(f"选择代理: {selected_proxy.name}, 优先级: {selected_proxy.priority}, 成功率: {selected_proxy.get_success_rate():.2f}")
            return selected_proxy
            
        return None

    def select_random_proxy(self, model: Optional[str] = None) -> Optional[ApiProxy]:
        """随机选择代理"""
        active_proxies = self.get_active_proxies()
        if not active_proxies:
            return None

        # 过滤支持指定模型的代理
        if model:
            candidate_proxies = [p for p in active_proxies if model in p.models]
            if not candidate_proxies:
                candidate_proxies = active_proxies
        else:
            candidate_proxies = active_proxies

        return random.choice(candidate_proxies)

    def call_api(self, proxy: ApiProxy, model: str, messages: List[Dict],
                 max_retries: int = 3) -> Dict[str, Any]:
        """调用API"""
        if not proxy.is_active:
            raise Exception(f"代理 {proxy.name} 未激活")

        # 如果指定了模型，但不在代理支持的模型列表中，则使用代理的默认模型
        if model and model not in proxy.models:
            logger.warning(f"模型 {model} 不在代理 {proxy.name} 支持的模型列表中，使用默认模型 {proxy.model}")
            model = proxy.model
            
        # 如果有可用模型列表，且指定的模型不在可用模型列表中，则尝试找一个可用的替代模型
        if proxy.available_models and model not in proxy.available_models:
            logger.warning(f"模型 {model} 不在代理 {proxy.name} 可用的模型列表中")
            
            # 尝试在可用模型列表中找到一个相似的模型
            similar_model = None
            model_prefix = model.split('/')[0] if '/' in model else model.split('-')[0]
            
            for available_model in proxy.available_models:
                if model_prefix.lower() in available_model.lower():
                    similar_model = available_model
                    break
            
            # 如果找到了相似模型，使用它
            if similar_model:
                logger.info(f"使用相似的可用模型 {similar_model} 替代 {model}")
                model = similar_model
            # 否则使用第一个可用模型
            elif proxy.available_models:
                logger.info(f"使用第一个可用模型 {proxy.available_models[0]} 替代 {model}")
                model = proxy.available_models[0]
            # 如果没有可用模型，则使用默认模型
            else:
                logger.info(f"没有可用模型，使用默认模型 {proxy.model}")
                model = proxy.model

        retries = 0
        last_error = None

        while retries < max_retries:
            try:
                return self._make_api_request(proxy, model, messages)
            except Exception as e:
                last_error = e
            
            retries += 1
            if retries < max_retries:
                logger.warning(f"代理 {proxy.name} 调用失败，重试第 {retries} 次: {str(last_error)}")
                time.sleep(1)  # 等待1秒后重试
        
        # 所有重试都失败了
        raise last_error or Exception(f"代理 {proxy.name} 调用失败，已重试 {max_retries} 次")

    def _make_api_request(self, proxy: ApiProxy, model: str, messages: List[Dict],
                         timeout: int = 60, max_tokens: int = 2000, use_system_prompt: bool = True) -> Dict[str, Any]:
        """统一的API请求方法"""
        # 如果需要，添加统一的系统提示词
        if use_system_prompt and (not messages or messages[0].get('role') != 'system'):
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

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
            'temperature': 0.7,
            'max_tokens': max_tokens
        }

        # 发送请求
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=timeout, verify=False)
        response_time = time.time() - start_time

        # 处理响应
        if response.status_code == 200:
            proxy.record_success(response_time)
            return response.json()

        # 处理错误
        proxy.record_error()
        error_message = f"HTTP错误: {response.status_code}"
        try:
            error_data = response.json()
            if 'error' in error_data:
                error_message = error_data['error'].get('message', error_message)
        except:
            pass

        # 如果是认证错误，尝试轮换密钥
        if response.status_code in [401, 403]:
            logger.warning(f"代理 {proxy.name} 认证失败，轮换密钥")
            proxy.rotate_key()

        raise Exception(error_message)

    def get_pool_status(self) -> Dict[str, Any]:
        """获取代理池状态"""
        active_proxies = self.get_active_proxies()
        healthy_proxies = [p for p in self.proxies if p.is_healthy()]

        total_success = sum(p.success_count for p in self.proxies)
        total_error = sum(p.error_count for p in self.proxies)
        total_requests = total_success + total_error

        avg_response_time = 0
        if active_proxies:
            response_times = []
            for proxy in active_proxies:
                if proxy.response_times:
                    response_times.extend(proxy.response_times)
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)

        return {
            'total_proxies': len(self.proxies),
            'active_proxies': len(active_proxies),
            'inactive_proxies': len(self.proxies) - len(active_proxies),
            'healthy_proxies': len(healthy_proxies),
            'total_requests': total_requests,
            'total_success': total_success,
            'total_errors': total_error,
            'overall_success_rate': round((total_success / total_requests * 100) if total_requests > 0 else 0, 2),
            'avg_response_time': round(avg_response_time, 2),
            'proxies': [proxy.to_dict() for proxy in self.proxies]
        }

    def start_health_check(self):
        """启动健康检查线程"""
        if self._health_check_thread is None or not self._health_check_thread.is_alive():
            self._stop_health_check = False
            self._health_check_thread = threading.Thread(target=self._health_check_worker)
            self._health_check_thread.daemon = True
            self._health_check_thread.start()
            logger.info("健康检查线程已启动")

    def stop_health_check(self):
        """停止健康检查线程"""
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._stop_health_check = True
            self._health_check_thread.join(timeout=5)
            logger.info("健康检查线程已停止")
            
    def start_model_test(self):
        """启动模型测试线程"""
        if not self.model_test_enabled:
            return
            
        if self._model_test_thread is None or not self._model_test_thread.is_alive():
            self._stop_model_test = False
            self._model_test_thread = threading.Thread(target=self._model_test_worker)
            self._model_test_thread.daemon = True
            self._model_test_thread.start()
            logger.info("模型测试线程已启动")
            
    def stop_model_test(self):
        """停止模型测试线程"""
        if self._model_test_thread and self._model_test_thread.is_alive():
            self._stop_model_test = True
            self._model_test_thread.join(timeout=5)
            logger.info("模型测试线程已停止")

    def _health_check_worker(self):
        """健康检查工作线程"""
        logger.info("健康检查工作线程启动")
        while not self._stop_health_check:
            try:
                for proxy in self.proxies:
                    if self._stop_health_check:  # 检查是否需要退出
                        break
                    if proxy.needs_health_check():
                        try:
                            self._perform_health_check(proxy)
                        except Exception as e:
                            logger.error(f"代理 {proxy.name} 健康检查失败: {str(e)}")
                        time.sleep(2)  # 每个代理检查后稍微暂停，避免过于频繁的请求
            except Exception as e:
                logger.error(f"健康检查工作线程异常: {str(e)}")

            # 睡眠一段时间后再次检查
            for _ in range(60):  # 每分钟检查一次是否需要退出
                if self._stop_health_check:
                    break
                time.sleep(1)

        logger.info("健康检查工作线程退出")

    def _perform_health_check(self, proxy: ApiProxy):
        """执行增强的健康检查"""
        logger.debug(f"执行代理 {proxy.name} 的健康检查")
        proxy.update_health_check()

        # 检查是否需要尝试自动恢复
        if self.auto_recovery_enabled and not proxy.is_active and proxy.disabled_at > 0:
            # 如果代理被禁用时间超过恢复间隔，且尝试次数未达上限，则尝试恢复
            time_since_disabled = time.time() - proxy.disabled_at
            if (time_since_disabled > self.auto_recovery_interval and
                proxy.auto_recovery_attempts < proxy.max_auto_recovery_attempts):

                logger.info(f"尝试自动恢复代理 {proxy.name}，第 {proxy.auto_recovery_attempts + 1} 次尝试")
                proxy.auto_recovery_attempts += 1

                # 尝试测试代理
                try:
                    # 使用统一的API请求方法，使用真实的考试题目
                    test_question = random.choice(TEST_QUESTIONS)
                    test_messages = [{"role": "user", "content": test_question}]

                    # 使用自适应超时
                    timeout = self._get_adaptive_timeout(proxy)
                    self._make_api_request(proxy, proxy.model, test_messages, timeout=timeout, max_tokens=10)

                    # 恢复成功
                    proxy.is_active = True
                    proxy.consecutive_errors = 0
                    proxy.circuit_breaker_opened_at = 0.0  # 重置熔断器
                    logger.info(f"代理 {proxy.name} 自动恢复成功")

                except Exception as e:
                    error_type = self._classify_error(e)
                    proxy.record_error(error_type)
                    logger.warning(f"代理 {proxy.name} 自动恢复失败: {str(e)}")

        # 如果代理活跃，执行常规健康检查
        if proxy.is_active:
            try:
                # 使用统一的API请求方法进行健康检查，使用真实的考试题目
                test_question = random.choice(TEST_QUESTIONS)
                test_messages = [{"role": "user", "content": test_question}]

                # 使用自适应超时
                timeout = self._get_adaptive_timeout(proxy)
                self._make_api_request(proxy, proxy.model, test_messages, timeout=timeout, max_tokens=10)

                # 健康检查成功，重置一些状态
                if proxy.consecutive_errors > 0:
                    logger.info(f"代理 {proxy.name} 健康检查通过，重置错误计数")
                    proxy.consecutive_errors = max(0, proxy.consecutive_errors - 1)

                logger.debug(f"代理 {proxy.name} 健康检查通过")

            except requests.exceptions.Timeout:
                proxy.record_error("timeout")
                logger.warning(f"代理 {proxy.name} 健康检查超时")
            except requests.exceptions.ConnectionError:
                proxy.record_error("connection_error")
                logger.warning(f"代理 {proxy.name} 健康检查连接失败")
            except requests.exceptions.RequestException as e:
                error_type = self._classify_error(e)
                proxy.record_error(error_type)
                logger.warning(f"代理 {proxy.name} 健康检查请求异常: {str(e)}")
            except Exception as e:
                error_type = self._classify_error(e)
                proxy.record_error(error_type)
                logger.warning(f"代理 {proxy.name} 健康检查异常: {str(e)}")
                
    def _model_test_worker(self):
        """模型测试工作线程"""
        # 启动后等待一段时间再进行第一次测试
        time.sleep(300)  # 等待5分钟
        
        while not self._stop_model_test:
            try:
                for proxy in self.proxies:
                    if proxy.is_active:
                        self._test_proxy_models(proxy)
                        time.sleep(5)  # 每个代理测试后暂停5秒，避免过于频繁的请求
            except Exception as e:
                logger.error(f"模型测试异常: {str(e)}")
            
            # 睡眠一段时间后再次测试
            for _ in range(self.model_test_interval):  # 每隔指定时间测试一次
                if self._stop_model_test:
                    break
                time.sleep(1)
                
    def _test_proxy_models(self, proxy: ApiProxy):
        """测试代理的模型可用性"""
        if not proxy.is_active:
            return
            
        logger.info(f"开始测试代理 {proxy.name} 的模型可用性")
        
        # 如果模型列表为空，则不测试
        if not proxy.models:
            logger.warning(f"代理 {proxy.name} 没有模型列表，跳过测试")
            return
            
        # 从模型列表中随机选择一些模型进行测试
        import random
        test_models = proxy.models
        if len(test_models) > self.model_test_max_count:
            test_models = random.sample(test_models, self.model_test_max_count)
            
        # 测试结果
        available_models = []
        
        # 测试每个模型
        for model in test_models:
            try:
                # 使用统一的API请求方法测试模型，使用真实的考试题目
                test_question = random.choice(TEST_QUESTIONS)
                test_messages = [{"role": "user", "content": test_question}]
                self._make_api_request(proxy, model, test_messages, timeout=15, max_tokens=10)
                available_models.append(model)
                logger.info(f"模型 {model} 在代理 {proxy.name} 上测试成功")
            except Exception as e:
                logger.warning(f"测试模型 {model} 在代理 {proxy.name} 上失败: {str(e)}")
                
        # 如果有新的可用模型，更新代理的可用模型列表
        if available_models:
            # 合并现有的可用模型和新测试的可用模型
            updated_models = list(set(proxy.available_models + available_models))
            
            # 如果有变化，更新代理的可用模型列表
            if set(updated_models) != set(proxy.available_models):
                proxy.available_models = updated_models
                logger.info(f"更新代理 {proxy.name} 的可用模型列表，共 {len(updated_models)} 个模型")
                
                # 保存到配置文件
                save_success = save_proxy_config(self)
                if not save_success:
                    logger.warning("代理配置保存失败，但可用模型列表已更新到内存中")
        else:
            logger.warning(f"代理 {proxy.name} 没有可用模型")

    def add_proxy(self, name: str, api_base: str, api_keys: List[str],
                  model: str, models: List[str], is_active: bool = True,
                  priority: int = 1, available_models: Optional[List[str]] = None) -> bool:
        """添加代理"""
        if self.get_proxy_by_name(name):
            return False

        proxy = ApiProxy(
            name=name,
            api_base=api_base,
            api_keys=api_keys,
            model=model,
            models=models,
            available_models=available_models or [],
            is_active=is_active,
            priority=priority
        )
        self.proxies.append(proxy)
        return True

    def remove_proxy(self, name: str) -> bool:
        """移除代理"""
        with self._lock:
            for i, proxy in enumerate(self.proxies):
                if proxy.name == name:
                    del self.proxies[i]
                    logger.info(f"已移除代理: {name}")
                    return True
            return False

    def update_proxy_status(self, name: str, is_active: bool) -> bool:
        """更新代理状态"""
        proxy = self.get_proxy_by_name(name)
        if proxy:
            proxy.is_active = is_active
            logger.info(f"代理 {name} 状态已更新为: {'活跃' if is_active else '非活跃'}")
            return True
        return False

    def update_proxy_priority(self, name: str, priority: int) -> bool:
        """更新代理优先级"""
        proxy = self.get_proxy_by_name(name)
        if proxy:
            proxy.priority = priority
            logger.info(f"代理 {name} 优先级已更新为: {priority}")
            return True
        return False

    def reset_proxy_errors(self, name: str) -> bool:
        """重置代理错误计数"""
        proxy = self.get_proxy_by_name(name)
        if not proxy:
            return False
        
        proxy.reset_errors()
        proxy.auto_recovery_attempts = 0  # 重置自动恢复尝试次数
        return True

    def _is_circuit_breaker_open(self, proxy: ApiProxy) -> bool:
        """检查代理是否处于熔断状态"""
        if not self.circuit_breaker_enabled:
            return False

        # 检查连续错误次数
        if proxy.consecutive_errors >= self.circuit_breaker_threshold:
            # 检查熔断时间是否已过
            if hasattr(proxy, 'circuit_breaker_opened_at'):
                time_since_opened = time.time() - proxy.circuit_breaker_opened_at
                if time_since_opened < self.circuit_breaker_timeout:
                    return True
                else:
                    # 熔断时间已过，重置状态
                    proxy.consecutive_errors = 0
                    delattr(proxy, 'circuit_breaker_opened_at')
                    logger.info(f"代理 {proxy.name} 熔断器已重置")
                    return False
            else:
                # 首次达到熔断阈值
                proxy.circuit_breaker_opened_at = time.time()
                logger.warning(f"代理 {proxy.name} 触发熔断器，连续错误 {proxy.consecutive_errors} 次")
                return True

        return False

    def _calculate_health_score(self, proxy: ApiProxy) -> float:
        """计算代理健康分数 (0-1)"""
        if not proxy.is_active:
            return 0.0

        # 基础健康分数基于成功率
        success_rate = proxy.get_success_rate()

        # 考虑连续错误的影响
        error_penalty = min(0.5, proxy.consecutive_errors * 0.1)

        # 考虑响应时间的影响
        time_penalty = 0
        if proxy.response_times:
            avg_time = proxy.get_avg_response_time()
            if avg_time > 30:  # 超过30秒认为较慢
                time_penalty = min(0.3, (avg_time - 30) * 0.01)

        # 考虑最近活动的影响
        activity_bonus = 0
        if hasattr(proxy, 'last_success_time'):
            time_since_success = time.time() - proxy.last_success_time
            if time_since_success < 300:  # 5分钟内有成功请求
                activity_bonus = 0.1

        health_score = success_rate - error_penalty - time_penalty + activity_bonus
        return max(0.0, min(1.0, health_score))

    def _calculate_load_score(self, proxy: ApiProxy) -> float:
        """计算代理负载分数 (0-1，越高表示负载越轻)"""
        # 简单的负载计算：基于最近的请求频率
        current_time = time.time()

        # 计算最近5分钟的请求数
        recent_requests = 0
        if hasattr(proxy, 'request_timestamps'):
            recent_requests = len([t for t in proxy.request_timestamps if current_time - t < 300])
        else:
            proxy.request_timestamps = []

        # 假设每分钟最多处理20个请求为满负载
        max_requests_per_5min = 100
        load_ratio = min(1.0, recent_requests / max_requests_per_5min)

        # 负载分数 = 1 - 负载比例
        return 1.0 - load_ratio

    def _get_adaptive_timeout(self, proxy: ApiProxy) -> int:
        """获取自适应超时时间"""
        if not self.adaptive_timeout_enabled:
            return self.health_check_timeout

        # 基于历史响应时间计算自适应超时
        if proxy.response_times:
            avg_time = proxy.get_avg_response_time()
            # 超时时间 = 平均响应时间 * 3 + 10秒缓冲
            adaptive_timeout = int(avg_time * 3 + 10)
            # 限制在最小和最大超时时间之间
            return max(self.min_timeout, min(self.max_timeout, adaptive_timeout))

        return self.health_check_timeout

    def _classify_error(self, error: Exception) -> str:
        """分类错误类型"""
        error_str = str(error).lower()

        if isinstance(error, requests.exceptions.Timeout):
            return "timeout"
        elif isinstance(error, requests.exceptions.ConnectionError):
            return "connection_error"
        elif "401" in error_str or "403" in error_str or "unauthorized" in error_str:
            return "auth_error"
        elif "429" in error_str or "rate limit" in error_str:
            return "rate_limit"
        elif "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return "server_error"
        elif "400" in error_str:
            return "client_error"
        else:
            return "unknown"

# 全局代理池实例
_proxy_pool = None

def get_api_proxy_pool() -> ApiProxyPool:
    """获取API代理池实例"""
    global _proxy_pool
    if _proxy_pool is None:
        _proxy_pool = ApiProxyPool()
    return _proxy_pool

def reload_proxy_pool():
    """重新加载代理池"""
    global _proxy_pool
    if _proxy_pool:
        _proxy_pool.stop_health_check()
        _proxy_pool.stop_model_test()
        
        _proxy_pool = ApiProxyPool()
    logger.info("代理池已重新加载")
    return _proxy_pool

def save_proxy_config(proxy_pool) -> bool:
    """保存代理配置到文件"""
    try:
        # 读取当前配置文件
        config_file = proxy_pool.config_file
        if not os.path.exists(config_file):
            logger.error(f"配置文件不存在: {config_file}")
            return False
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新third_party_apis配置
        config['third_party_apis'] = []
        for proxy in proxy_pool.proxies:
            config['third_party_apis'].append({
                'name': proxy.name,
                'api_base': proxy.api_base,
                'api_keys': proxy.api_keys,
                'model': proxy.model,
                'models': proxy.models,
                'available_models': proxy.available_models,
                'is_active': proxy.is_active,
                'priority': proxy.priority
            })
        
        # 写回配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"API代理配置已保存到: {config_file}")
        return True
        
    except Exception as e:
        logger.error(f"保存API代理配置失败: {str(e)}")
        return False
