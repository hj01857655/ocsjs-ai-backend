# -*- coding: utf-8 -*-
"""
数据库连接池监控和管理工具
"""
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.pool import Pool
from flask import current_app

from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseMonitor:
    """数据库连接池监控器"""
    
    def __init__(self, db):
        self.db = db
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'pool_size': 0,
            'overflow_connections': 0,
            'checked_out_connections': 0,
            'query_count': 0,
            'slow_queries': 0,
            'connection_errors': 0,
            'last_updated': None
        }
        
        # 慢查询阈值（秒）
        self.slow_query_threshold = 2.0
        
        # 监控配置
        self.monitoring_enabled = True
        self.monitoring_interval = 60  # 60秒
        
        # 查询统计
        self.query_stats = {
            'total_queries': 0,
            'slow_queries': 0,
            'failed_queries': 0,
            'avg_query_time': 0.0,
            'query_times': []
        }
        
        # 启动监控线程
        self._start_monitoring()
    
    def _start_monitoring(self):
        """启动监控线程"""
        if self.monitoring_enabled:
            monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
            monitor_thread.start()
            logger.info("数据库连接池监控器已启动")
    
    def _monitor_worker(self):
        """监控工作线程"""
        while self.monitoring_enabled:
            try:
                self._collect_stats()
                self._check_pool_health()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"数据库监控异常: {str(e)}")
                time.sleep(self.monitoring_interval)
    
    def _collect_stats(self):
        """收集连接池统计信息"""
        try:
            engine = self.db.engine
            pool = engine.pool
            
            # 更新连接池统计
            self.stats.update({
                'pool_size': pool.size(),
                'checked_out_connections': pool.checkedout(),
                'overflow_connections': pool.overflow(),
                'total_connections': pool.size() + pool.overflow(),
                'active_connections': pool.checkedout(),
                'idle_connections': pool.size() - pool.checkedout(),
                'last_updated': datetime.utcnow()
            })
            
            logger.debug(f"连接池状态: {self.stats}")
            
        except Exception as e:
            logger.error(f"收集连接池统计失败: {str(e)}")
    
    def _check_pool_health(self):
        """检查连接池健康状态"""
        try:
            # 检查连接池是否接近满载
            if self.stats['active_connections'] > self.stats['pool_size'] * 0.8:
                logger.warning(f"连接池使用率过高: {self.stats['active_connections']}/{self.stats['pool_size']}")
            
            # 检查是否有溢出连接
            if self.stats['overflow_connections'] > 0:
                logger.warning(f"连接池溢出: {self.stats['overflow_connections']} 个溢出连接")
            
            # 测试连接可用性
            self._test_connection()
            
        except Exception as e:
            logger.error(f"连接池健康检查失败: {str(e)}")
            self.stats['connection_errors'] += 1
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            with self.db.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            raise
    
    def record_query(self, query_time: float, success: bool = True):
        """记录查询统计"""
        self.query_stats['total_queries'] += 1
        
        if not success:
            self.query_stats['failed_queries'] += 1
            return
        
        # 记录查询时间
        self.query_stats['query_times'].append(query_time)
        
        # 保持最近1000次查询的时间记录
        if len(self.query_stats['query_times']) > 1000:
            self.query_stats['query_times'] = self.query_stats['query_times'][-1000:]
        
        # 计算平均查询时间
        if self.query_stats['query_times']:
            self.query_stats['avg_query_time'] = sum(self.query_stats['query_times']) / len(self.query_stats['query_times'])
        
        # 检查慢查询
        if query_time > self.slow_query_threshold:
            self.query_stats['slow_queries'] += 1
            logger.warning(f"检测到慢查询: {query_time:.2f}秒")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        return {
            'pool_stats': self.stats.copy(),
            'query_stats': self.query_stats.copy(),
            'health_status': self._get_health_status()
        }
    
    def _get_health_status(self) -> str:
        """获取健康状态"""
        if self.stats['connection_errors'] > 5:
            return 'critical'
        elif self.stats['active_connections'] > self.stats['pool_size'] * 0.9:
            return 'warning'
        elif self.query_stats['failed_queries'] > self.query_stats['total_queries'] * 0.1:
            return 'warning'
        else:
            return 'healthy'
    
    def optimize_pool(self):
        """优化连接池配置建议"""
        recommendations = []
        
        # 检查连接池大小
        if self.stats['overflow_connections'] > 0:
            recommendations.append("建议增加连接池大小，当前有溢出连接")
        
        # 检查慢查询
        if self.query_stats['slow_queries'] > self.query_stats['total_queries'] * 0.05:
            recommendations.append("慢查询比例过高，建议优化SQL查询")
        
        # 检查失败查询
        if self.query_stats['failed_queries'] > self.query_stats['total_queries'] * 0.01:
            recommendations.append("查询失败率过高，建议检查数据库连接稳定性")
        
        return recommendations
    
    def reset_stats(self):
        """重置统计信息"""
        self.query_stats = {
            'total_queries': 0,
            'slow_queries': 0,
            'failed_queries': 0,
            'avg_query_time': 0.0,
            'query_times': []
        }
        self.stats['connection_errors'] = 0
        logger.info("数据库监控统计已重置")

class QueryProfiler:
    """查询性能分析器"""
    
    def __init__(self, monitor: DatabaseMonitor):
        self.monitor = monitor
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        query_time = time.time() - self.start_time
        success = exc_type is None
        self.monitor.record_query(query_time, success)

# 全局监控器实例
_db_monitor = None

def get_db_monitor() -> Optional[DatabaseMonitor]:
    """获取数据库监控器实例"""
    global _db_monitor
    return _db_monitor

def init_db_monitor(db):
    """初始化数据库监控器"""
    global _db_monitor
    if _db_monitor is None:
        _db_monitor = DatabaseMonitor(db)
        logger.info("数据库监控器已初始化")
    return _db_monitor

def profile_query(func):
    """查询性能分析装饰器"""
    def wrapper(*args, **kwargs):
        monitor = get_db_monitor()
        if monitor:
            with QueryProfiler(monitor):
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    return wrapper
