# -*- coding: utf-8 -*-
"""
日志工具类
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from flask import request, g
import json
from typing import Dict, Any, Optional, List
from collections import deque
import gzip
import shutil

def setup_logger(app):
    """设置应用日志"""
    # 创建logs目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 设置日志级别
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
    app.logger.setLevel(log_level)
    
    # 创建文件处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(log_level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 创建系统日志处理器
    system_handler = SystemLogHandler()

    # 添加处理器
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.addHandler(system_handler)

    # 设置其他日志记录器
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # 为根日志记录器也添加系统日志处理器
    root_logger = logging.getLogger()
    root_logger.addHandler(system_handler)

def get_logger(name):
    """获取日志记录器"""
    return logging.getLogger(name)

class SystemLogHandler(logging.Handler):
    """自定义日志处理器，将日志记录到系统日志表"""

    def __init__(self):
        super().__init__()
        self.setLevel(logging.INFO)

    def emit(self, record):
        """发送日志记录"""
        try:
            # 避免循环导入
            from routes.logs import add_system_log

            # 确定日志级别
            level_map = {
                logging.DEBUG: 'debug',
                logging.INFO: 'info',
                logging.WARNING: 'warn',
                logging.ERROR: 'error',
                logging.CRITICAL: 'fatal'
            }
            level = level_map.get(record.levelno, 'info')

            # 确定日志来源
            source = 'system'
            if 'werkzeug' in record.name:
                source = 'api'
            elif 'request' in record.name:
                source = 'api'
            elif 'error' in record.name:
                source = 'system'
            elif 'security' in record.name:
                source = 'auth'

            # 获取IP地址
            ip_address = None
            try:
                from flask import has_request_context
                if has_request_context():
                    ip_address = request.remote_addr
            except Exception:
                pass

            # 记录到系统日志
            add_system_log(
                level=level,
                source=source,
                message=record.getMessage(),
                ip_address=ip_address,
                context={
                    'logger_name': record.name,
                    'module': record.module if hasattr(record, 'module') else None,
                    'function': record.funcName if hasattr(record, 'funcName') else None,
                    'line': record.lineno if hasattr(record, 'lineno') else None
                }
            )
        except Exception:
            # 避免日志记录失败影响主程序
            pass

def log_request(level='info', message=''):
    """记录请求日志"""
    logger = get_logger('request')
    
    # 构建日志信息
    log_data = {
        'method': request.method,
        'url': request.url,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if message:
        log_data['message'] = message
    
    # 记录日志
    getattr(logger, level)(f"Request: {log_data}")

def log_response(level='info', status_code=200, message=''):
    """记录响应日志"""
    logger = get_logger('response')
    
    # 构建日志信息
    log_data = {
        'method': request.method,
        'url': request.url,
        'status_code': status_code,
        'remote_addr': request.remote_addr,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if message:
        log_data['message'] = message
    
    # 记录日志
    getattr(logger, level)(f"Response: {log_data}")

def log_error(error, context=None):
    """记录错误日志"""
    logger = get_logger('error')
    
    # 构建错误信息
    error_data = {
        'error': str(error),
        'type': type(error).__name__,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        from flask import has_request_context
        if has_request_context():
            error_data['method'] = request.method
            error_data['url'] = request.url
            error_data['remote_addr'] = request.remote_addr or 'unknown'
    except Exception:
        # 如果无法获取请求上下文，跳过
        pass
    
    if context:
        error_data['context'] = context
    
    # 记录错误日志
    logger.error(f"Error: {error_data}", exc_info=True)

def log_system_event(event_type, message, level='info', context=None):
    """记录系统事件日志"""
    logger = get_logger('system')
    
    # 构建事件信息
    event_data = {
        'event_type': event_type,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if context:
        event_data['context'] = context
    
    # 记录日志
    getattr(logger, level)(f"System Event: {event_data}")

def log_security_event(event_type, message, level='warning', user_id=None):
    """记录安全事件日志"""
    logger = get_logger('security')
    
    # 构建安全事件信息
    security_data = {
        'event_type': event_type,
        'message': message,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if hasattr(request, 'method'):
        security_data.update({
            'method': request.method,
            'url': request.url,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        })
    
    if user_id:
        security_data['user_id'] = user_id
    
    # 记录安全日志
    getattr(logger, level)(f"Security Event: {security_data}")

class RequestLogger:
    """请求日志中间件"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_appcontext(self.teardown)
    
    def before_request(self):
        """请求前处理"""
        g.start_time = datetime.utcnow()
        
        # 记录请求开始
        if not request.path.startswith('/static/'):
            log_request('info', 'Request started')
    
    def after_request(self, response):
        """请求后处理"""
        if hasattr(g, 'start_time'):
            duration = (datetime.utcnow() - g.start_time).total_seconds()
            
            # 记录请求完成
            if not request.path.startswith('/static/'):
                log_response(
                    'info' if response.status_code < 400 else 'warning',
                    response.status_code,
                    f'Request completed in {duration:.3f}s'
                )
        
        return response
    
    def teardown(self, exception):
        """请求结束处理"""
        if exception:
            log_error(exception, {'phase': 'teardown'})

class EnhancedLogManager:
    """增强的日志管理器"""

    def __init__(self, max_memory_logs: int = 1000):
        self.max_memory_logs = max_memory_logs
        self.memory_logs = deque(maxlen=max_memory_logs)
        self.log_stats = {
            'total_logs': 0,
            'error_count': 0,
            'warning_count': 0,
            'info_count': 0,
            'debug_count': 0
        }
        self.log_lock = threading.Lock()

        # 日志压缩配置
        self.compression_enabled = True
        self.compression_age_days = 7

        # 启动日志清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()

    def add_log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        """添加日志到内存缓存"""
        with self.log_lock:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'level': level.upper(),
                'message': message,
                'context': context or {}
            }

            self.memory_logs.append(log_entry)
            self.log_stats['total_logs'] += 1
            self.log_stats[f'{level.lower()}_count'] += 1

    def get_recent_logs(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取最近的日志"""
        with self.log_lock:
            logs = list(self.memory_logs)

            # 按级别过滤
            if level:
                logs = [log for log in logs if log['level'].lower() == level.lower()]

            # 按时间倒序排序并限制数量
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            return logs[:limit]

    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计"""
        with self.log_lock:
            return self.log_stats.copy()

    def search_logs(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """搜索日志"""
        with self.log_lock:
            query_lower = query.lower()
            matching_logs = []

            for log in self.memory_logs:
                if (query_lower in log['message'].lower() or
                    query_lower in str(log['context']).lower()):
                    matching_logs.append(log)

            # 按时间倒序排序并限制数量
            matching_logs.sort(key=lambda x: x['timestamp'], reverse=True)
            return matching_logs[:limit]

    def export_logs(self, start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """导出日志"""
        with self.log_lock:
            logs = list(self.memory_logs)

            if start_time or end_time:
                filtered_logs = []
                for log in logs:
                    log_time = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))

                    if start_time and log_time < start_time:
                        continue
                    if end_time and log_time > end_time:
                        continue

                    filtered_logs.append(log)

                return filtered_logs

            return logs

    def _cleanup_worker(self):
        """日志清理工作线程"""
        while True:
            try:
                self._compress_old_logs()
                self._cleanup_old_logs()
                time.sleep(3600)  # 每小时运行一次
            except Exception as e:
                print(f"日志清理异常: {str(e)}")
                time.sleep(3600)

    def _compress_old_logs(self):
        """压缩旧日志文件"""
        if not self.compression_enabled:
            return

        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        if not os.path.exists(log_dir):
            return

        cutoff_date = datetime.now() - timedelta(days=self.compression_age_days)

        for filename in os.listdir(log_dir):
            if filename.endswith('.log') and not filename.endswith('.gz'):
                file_path = os.path.join(log_dir, filename)

                # 检查文件修改时间
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_mtime < cutoff_date:
                    try:
                        # 压缩文件
                        compressed_path = file_path + '.gz'
                        with open(file_path, 'rb') as f_in:
                            with gzip.open(compressed_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)

                        # 删除原文件
                        os.remove(file_path)
                        print(f"已压缩日志文件: {filename}")

                    except Exception as e:
                        print(f"压缩日志文件失败 {filename}: {str(e)}")

    def _cleanup_old_logs(self):
        """清理过期的压缩日志"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        if not os.path.exists(log_dir):
            return

        # 删除30天前的压缩日志
        cutoff_date = datetime.now() - timedelta(days=30)

        for filename in os.listdir(log_dir):
            if filename.endswith('.log.gz'):
                file_path = os.path.join(log_dir, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_mtime < cutoff_date:
                    try:
                        os.remove(file_path)
                        print(f"已删除过期日志: {filename}")
                    except Exception as e:
                        print(f"删除过期日志失败 {filename}: {str(e)}")

class StructuredLogHandler(logging.Handler):
    """结构化日志处理器"""

    def __init__(self, log_manager: EnhancedLogManager):
        super().__init__()
        self.log_manager = log_manager

    def emit(self, record):
        """发送日志记录"""
        try:
            # 提取上下文信息
            context = {}
            if hasattr(record, 'extra'):
                context.update(record.extra)

            # 添加到日志管理器
            self.log_manager.add_log(
                level=record.levelname,
                message=record.getMessage(),
                context=context
            )
        except Exception:
            self.handleError(record)

# 全局日志管理器实例
_log_manager = None

def get_log_manager() -> EnhancedLogManager:
    """获取日志管理器实例"""
    global _log_manager
    if _log_manager is None:
        _log_manager = EnhancedLogManager()
    return _log_manager

def init_enhanced_logging():
    """初始化增强日志系统"""
    log_manager = get_log_manager()

    # 添加结构化日志处理器到根日志记录器
    root_logger = logging.getLogger()
    structured_handler = StructuredLogHandler(log_manager)
    root_logger.addHandler(structured_handler)

    return log_manager
