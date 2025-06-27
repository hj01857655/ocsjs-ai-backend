# -*- coding: utf-8 -*-
"""
API响应标准化处理
"""
from typing import Dict, Any, Optional, Union
from flask import jsonify
from datetime import datetime
import traceback

from utils.error_handler import get_error_handler, ErrorInfo, ErrorSeverity
from utils.logger import get_logger

logger = get_logger(__name__)

class ResponseHandler:
    """API响应处理器"""
    
    def __init__(self):
        self.error_handler = get_error_handler()
    
    def success(self, data: Any = None, message: str = "操作成功", 
                meta: Optional[Dict[str, Any]] = None, status_code: int = 200):
        """成功响应"""
        response_data = {
            'success': True,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        if meta:
            response_data['meta'] = meta
            
        return jsonify(response_data), status_code
    
    def error(self, message: str = "操作失败", error_code: Optional[str] = None,
              details: Optional[Dict[str, Any]] = None, status_code: int = 400):
        """错误响应"""
        response_data = {
            'success': False,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if error_code:
            response_data['error_code'] = error_code
            
        if details:
            response_data['details'] = details
            
        return jsonify(response_data), status_code
    
    def handle_exception(self, exception: Exception, context: Optional[Dict[str, Any]] = None,
                        include_traceback: bool = False) -> tuple:
        """处理异常并返回标准化响应"""
        # 使用增强的错误处理
        error_info = self.error_handler.handle_error(exception, context)
        
        # 构建响应数据
        response_data = {
            'success': False,
            'message': error_info.message,
            'timestamp': datetime.utcnow().isoformat(),
            'error_category': error_info.category.value,
            'error_severity': error_info.severity.value,
            'should_retry': error_info.should_retry
        }
        
        # 添加详细信息
        if error_info.details:
            response_data['details'] = error_info.details
            
        if error_info.retry_after:
            response_data['retry_after'] = error_info.retry_after
            
        # 在开发环境中包含堆栈跟踪
        if include_traceback:
            response_data['traceback'] = traceback.format_exc()
            
        # 根据错误严重程度确定HTTP状态码
        status_code = self._get_status_code_from_severity(error_info.severity)
        
        return jsonify(response_data), status_code
    
    def _get_status_code_from_severity(self, severity: ErrorSeverity) -> int:
        """根据错误严重程度获取HTTP状态码"""
        severity_to_status = {
            ErrorSeverity.LOW: 400,
            ErrorSeverity.MEDIUM: 500,
            ErrorSeverity.HIGH: 500,
            ErrorSeverity.CRITICAL: 503
        }
        return severity_to_status.get(severity, 500)
    
    def paginated_success(self, data: list, page: int, per_page: int, 
                         total: int, message: str = "获取成功"):
        """分页成功响应"""
        total_pages = (total + per_page - 1) // per_page
        
        meta = {
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        return self.success(data=data, message=message, meta=meta)
    
    def validation_error(self, errors: Dict[str, list], message: str = "数据验证失败"):
        """验证错误响应"""
        return self.error(
            message=message,
            error_code="VALIDATION_ERROR",
            details={'validation_errors': errors},
            status_code=422
        )
    
    def not_found(self, resource: str = "资源", message: Optional[str] = None):
        """资源不存在响应"""
        if not message:
            message = f"{resource}不存在"
            
        return self.error(
            message=message,
            error_code="NOT_FOUND",
            status_code=404
        )
    
    def unauthorized(self, message: str = "未授权访问"):
        """未授权响应"""
        return self.error(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=401
        )
    
    def forbidden(self, message: str = "禁止访问"):
        """禁止访问响应"""
        return self.error(
            message=message,
            error_code="FORBIDDEN",
            status_code=403
        )
    
    def rate_limited(self, retry_after: int = 60, message: str = "请求频率过高"):
        """限流响应"""
        return self.error(
            message=message,
            error_code="RATE_LIMITED",
            details={'retry_after': retry_after},
            status_code=429
        )

# 全局响应处理器实例
_response_handler = None

def get_response_handler() -> ResponseHandler:
    """获取全局响应处理器实例"""
    global _response_handler
    if _response_handler is None:
        _response_handler = ResponseHandler()
    return _response_handler

# 便捷函数
def success_response(*args, **kwargs):
    """成功响应便捷函数"""
    return get_response_handler().success(*args, **kwargs)

def error_response(*args, **kwargs):
    """错误响应便捷函数"""
    return get_response_handler().error(*args, **kwargs)

def handle_exception(*args, **kwargs):
    """异常处理便捷函数"""
    return get_response_handler().handle_exception(*args, **kwargs)

def paginated_response(*args, **kwargs):
    """分页响应便捷函数"""
    return get_response_handler().paginated_success(*args, **kwargs)

def validation_error_response(*args, **kwargs):
    """验证错误响应便捷函数"""
    return get_response_handler().validation_error(*args, **kwargs)

def not_found_response(*args, **kwargs):
    """资源不存在响应便捷函数"""
    return get_response_handler().not_found(*args, **kwargs)

def unauthorized_response(*args, **kwargs):
    """未授权响应便捷函数"""
    return get_response_handler().unauthorized(*args, **kwargs)

def forbidden_response(*args, **kwargs):
    """禁止访问响应便捷函数"""
    return get_response_handler().forbidden(*args, **kwargs)

def rate_limited_response(*args, **kwargs):
    """限流响应便捷函数"""
    return get_response_handler().rate_limited(*args, **kwargs)
