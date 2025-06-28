# -*- coding: utf-8 -*-
"""
系统日志模块 - 简化版本
"""
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

def add_system_log(level='info', source='system', message='', user_id=None, ip_address=None, context=None):
    """
    添加系统日志 - 简化版本，只记录到应用日志
    
    Args:
        level: 日志级别 (info, warn, error)
        source: 日志来源 (system, auth, proxy, etc.)
        message: 日志消息
        user_id: 用户ID
        ip_address: IP地址
        context: 额外上下文信息
    """
    try:
        # 构建日志消息
        log_message = f"[{source.upper()}] {message}"
        
        if user_id:
            log_message += f" | User: {user_id}"
        
        if ip_address:
            log_message += f" | IP: {ip_address}"
        
        if context:
            log_message += f" | Context: {context}"
        
        # 根据级别记录日志
        if level == 'error':
            logger.error(log_message)
        elif level == 'warn':
            logger.warning(log_message)
        else:
            logger.info(log_message)
            
    except Exception as e:
        # 如果日志记录失败，至少打印到控制台
        print(f"日志记录失败: {str(e)}")
        print(f"原始日志: [{source.upper()}] {message}")
