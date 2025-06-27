# -*- coding: utf-8 -*-
"""
增强的错误处理和重试机制
"""
import time
import random
import functools
from typing import Dict, Any, Optional, Callable, List, Type, Union
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)

class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """错误分类"""
    NETWORK = "network"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    CLIENT = "client"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

@dataclass
class ErrorInfo:
    """错误信息"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None
    should_retry: bool = True

class ErrorClassifier:
    """错误分类器"""
    
    @staticmethod
    def classify_error(error: Exception) -> ErrorInfo:
        """分类错误"""
        error_str = str(error).lower()
        
        # 网络错误
        if "connection" in error_str or "network" in error_str:
            return ErrorInfo(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.MEDIUM,
                message="网络连接错误",
                should_retry=True
            )
        
        # 超时错误
        if "timeout" in error_str:
            return ErrorInfo(
                category=ErrorCategory.TIMEOUT,
                severity=ErrorSeverity.MEDIUM,
                message="请求超时",
                should_retry=True
            )
        
        # 认证错误
        if any(auth_keyword in error_str for auth_keyword in ["401", "403", "unauthorized", "forbidden"]):
            return ErrorInfo(
                category=ErrorCategory.AUTH,
                severity=ErrorSeverity.HIGH,
                message="认证失败",
                should_retry=False
            )
        
        # 限流错误
        if any(rate_keyword in error_str for rate_keyword in ["429", "rate limit", "too many requests"]):
            retry_after = 60  # 默认60秒后重试
            return ErrorInfo(
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.MEDIUM,
                message="请求频率限制",
                retry_after=retry_after,
                should_retry=True
            )
        
        # 服务器错误
        if any(server_keyword in error_str for server_keyword in ["500", "502", "503", "504", "internal server error"]):
            return ErrorInfo(
                category=ErrorCategory.SERVER,
                severity=ErrorSeverity.HIGH,
                message="服务器错误",
                should_retry=True
            )
        
        # 客户端错误
        if any(client_keyword in error_str for client_keyword in ["400", "404", "422", "bad request"]):
            return ErrorInfo(
                category=ErrorCategory.CLIENT,
                severity=ErrorSeverity.LOW,
                message="客户端请求错误",
                should_retry=False
            )
        
        # 未知错误
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            message=f"未知错误: {str(error)}",
            should_retry=True
        )

class RetryStrategy:
    """重试策略"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, backoff_factor: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if attempt <= 0:
            return 0
        
        # 指数退避
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        # 添加随机抖动
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay

class EnhancedErrorHandler:
    """增强的错误处理器"""
    
    def __init__(self):
        self.classifier = ErrorClassifier()
        self.default_retry_strategy = RetryStrategy()
        self.error_stats = {}
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorInfo:
        """处理错误"""
        error_info = self.classifier.classify_error(error)
        
        # 记录错误统计
        self._record_error_stats(error_info, context)
        
        # 记录日志
        self._log_error(error, error_info, context)
        
        return error_info
    
    def _record_error_stats(self, error_info: ErrorInfo, context: Optional[Dict[str, Any]]):
        """记录错误统计"""
        category = error_info.category.value
        if category not in self.error_stats:
            self.error_stats[category] = {
                'count': 0,
                'last_occurrence': None,
                'severity_counts': {}
            }
        
        self.error_stats[category]['count'] += 1
        self.error_stats[category]['last_occurrence'] = time.time()
        
        severity = error_info.severity.value
        if severity not in self.error_stats[category]['severity_counts']:
            self.error_stats[category]['severity_counts'][severity] = 0
        self.error_stats[category]['severity_counts'][severity] += 1
    
    def _log_error(self, error: Exception, error_info: ErrorInfo, context: Optional[Dict[str, Any]]):
        """记录错误日志"""
        log_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'category': error_info.category.value,
            'severity': error_info.severity.value,
            'should_retry': error_info.should_retry,
            'context': context or {}
        }
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {error_info.message}", extra=log_data)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {error_info.message}", extra=log_data)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {error_info.message}", extra=log_data)
        else:
            logger.info(f"Low severity error: {error_info.message}", extra=log_data)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return self.error_stats.copy()

def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0, 
                      max_delay: float = 60.0, backoff_factor: float = 2.0,
                      retry_on: Optional[List[Type[Exception]]] = None,
                      stop_on: Optional[List[Type[Exception]]] = None):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = EnhancedErrorHandler()
            retry_strategy = RetryStrategy(max_attempts, base_delay, max_delay, backoff_factor)
            
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # 检查是否应该停止重试
                    if stop_on and any(isinstance(e, exc_type) for exc_type in stop_on):
                        logger.info(f"停止重试，遇到停止异常: {type(e).__name__}")
                        break
                    
                    # 检查是否应该重试
                    if retry_on and not any(isinstance(e, exc_type) for exc_type in retry_on):
                        logger.info(f"不重试，异常类型不在重试列表中: {type(e).__name__}")
                        break
                    
                    # 处理错误
                    error_info = error_handler.handle_error(e, {
                        'function': func.__name__,
                        'attempt': attempt + 1,
                        'max_attempts': max_attempts
                    })
                    
                    # 如果不应该重试，直接抛出
                    if not error_info.should_retry:
                        logger.info(f"错误不应重试: {error_info.message}")
                        break
                    
                    # 如果是最后一次尝试，不再等待
                    if attempt == max_attempts - 1:
                        break
                    
                    # 计算延迟时间
                    delay = error_info.retry_after or retry_strategy.get_delay(attempt + 1)
                    logger.info(f"第 {attempt + 1} 次尝试失败，{delay:.2f}秒后重试: {error_info.message}")
                    time.sleep(delay)
            
            # 所有重试都失败了，抛出最后一个错误
            raise last_error
        
        return wrapper
    return decorator

# 全局错误处理器实例
_error_handler = None

def get_error_handler() -> EnhancedErrorHandler:
    """获取全局错误处理器实例"""
    global _error_handler
    if _error_handler is None:
        _error_handler = EnhancedErrorHandler()
    return _error_handler
