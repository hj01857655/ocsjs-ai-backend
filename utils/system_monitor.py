# -*- coding: utf-8 -*-
"""
系统性能监控模块
"""
import psutil
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
import json

from utils.logger import get_logger

logger = get_logger(__name__)

class SystemMonitor:
    """系统性能监控器"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 5  # 5秒采集一次
        
        # 历史数据存储
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.disk_history = deque(maxlen=history_size)
        self.network_history = deque(maxlen=history_size)
        
        # 网络统计基准
        self.last_network_stats = None
        
        # 告警配置
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'network_error_rate': 5.0
        }
        
        # 告警状态
        self.active_alerts = {}
        
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("系统性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        logger.info("系统性能监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                timestamp = datetime.utcnow()
                
                # 收集系统指标
                cpu_data = self._collect_cpu_data(timestamp)
                memory_data = self._collect_memory_data(timestamp)
                disk_data = self._collect_disk_data(timestamp)
                network_data = self._collect_network_data(timestamp)
                
                # 存储历史数据
                self.cpu_history.append(cpu_data)
                self.memory_history.append(memory_data)
                self.disk_history.append(disk_data)
                self.network_history.append(network_data)
                
                # 检查告警
                self._check_alerts(cpu_data, memory_data, disk_data, network_data)
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"系统监控异常: {str(e)}")
                time.sleep(self.monitor_interval)
    
    def _collect_cpu_data(self, timestamp: datetime) -> Dict[str, Any]:
        """收集CPU数据"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            
            return {
                'timestamp': timestamp.isoformat(),
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'cpu_freq_current': cpu_freq.current if cpu_freq else 0,
                'cpu_freq_max': cpu_freq.max if cpu_freq else 0,
                'load_avg_1m': load_avg[0],
                'load_avg_5m': load_avg[1],
                'load_avg_15m': load_avg[2]
            }
        except Exception as e:
            logger.error(f"收集CPU数据失败: {str(e)}")
            return {'timestamp': timestamp.isoformat(), 'error': str(e)}
    
    def _collect_memory_data(self, timestamp: datetime) -> Dict[str, Any]:
        """收集内存数据"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                'timestamp': timestamp.isoformat(),
                'memory_total': memory.total,
                'memory_available': memory.available,
                'memory_used': memory.used,
                'memory_percent': memory.percent,
                'swap_total': swap.total,
                'swap_used': swap.used,
                'swap_percent': swap.percent
            }
        except Exception as e:
            logger.error(f"收集内存数据失败: {str(e)}")
            return {'timestamp': timestamp.isoformat(), 'error': str(e)}
    
    def _collect_disk_data(self, timestamp: datetime) -> Dict[str, Any]:
        """收集磁盘数据"""
        try:
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            return {
                'timestamp': timestamp.isoformat(),
                'disk_total': disk_usage.total,
                'disk_used': disk_usage.used,
                'disk_free': disk_usage.free,
                'disk_percent': disk_usage.percent,
                'disk_read_bytes': disk_io.read_bytes if disk_io else 0,
                'disk_write_bytes': disk_io.write_bytes if disk_io else 0,
                'disk_read_count': disk_io.read_count if disk_io else 0,
                'disk_write_count': disk_io.write_count if disk_io else 0
            }
        except Exception as e:
            logger.error(f"收集磁盘数据失败: {str(e)}")
            return {'timestamp': timestamp.isoformat(), 'error': str(e)}
    
    def _collect_network_data(self, timestamp: datetime) -> Dict[str, Any]:
        """收集网络数据"""
        try:
            network_io = psutil.net_io_counters()
            network_connections = len(psutil.net_connections())
            
            # 计算网络速率
            bytes_sent_rate = 0
            bytes_recv_rate = 0
            
            if self.last_network_stats:
                time_diff = (timestamp - self.last_network_stats['timestamp']).total_seconds()
                if time_diff > 0:
                    bytes_sent_rate = (network_io.bytes_sent - self.last_network_stats['bytes_sent']) / time_diff
                    bytes_recv_rate = (network_io.bytes_recv - self.last_network_stats['bytes_recv']) / time_diff
            
            data = {
                'timestamp': timestamp.isoformat(),
                'bytes_sent': network_io.bytes_sent,
                'bytes_recv': network_io.bytes_recv,
                'packets_sent': network_io.packets_sent,
                'packets_recv': network_io.packets_recv,
                'errin': network_io.errin,
                'errout': network_io.errout,
                'dropin': network_io.dropin,
                'dropout': network_io.dropout,
                'connections': network_connections,
                'bytes_sent_rate': bytes_sent_rate,
                'bytes_recv_rate': bytes_recv_rate
            }
            
            # 更新基准数据
            self.last_network_stats = {
                'timestamp': timestamp,
                'bytes_sent': network_io.bytes_sent,
                'bytes_recv': network_io.bytes_recv
            }
            
            return data
            
        except Exception as e:
            logger.error(f"收集网络数据失败: {str(e)}")
            return {'timestamp': timestamp.isoformat(), 'error': str(e)}
    
    def _check_alerts(self, cpu_data: Dict, memory_data: Dict, disk_data: Dict, network_data: Dict):
        """检查告警条件"""
        alerts = []
        
        # CPU告警
        if 'cpu_percent' in cpu_data and cpu_data['cpu_percent'] > self.alert_thresholds['cpu_percent']:
            alert_key = 'high_cpu'
            if alert_key not in self.active_alerts:
                alert = {
                    'type': 'high_cpu',
                    'level': 'warning',
                    'message': f"CPU使用率过高: {cpu_data['cpu_percent']:.1f}%",
                    'value': cpu_data['cpu_percent'],
                    'threshold': self.alert_thresholds['cpu_percent'],
                    'timestamp': cpu_data['timestamp']
                }
                alerts.append(alert)
                self.active_alerts[alert_key] = alert
        else:
            self.active_alerts.pop('high_cpu', None)
        
        # 内存告警
        if 'memory_percent' in memory_data and memory_data['memory_percent'] > self.alert_thresholds['memory_percent']:
            alert_key = 'high_memory'
            if alert_key not in self.active_alerts:
                alert = {
                    'type': 'high_memory',
                    'level': 'warning',
                    'message': f"内存使用率过高: {memory_data['memory_percent']:.1f}%",
                    'value': memory_data['memory_percent'],
                    'threshold': self.alert_thresholds['memory_percent'],
                    'timestamp': memory_data['timestamp']
                }
                alerts.append(alert)
                self.active_alerts[alert_key] = alert
        else:
            self.active_alerts.pop('high_memory', None)
        
        # 磁盘告警
        if 'disk_percent' in disk_data and disk_data['disk_percent'] > self.alert_thresholds['disk_percent']:
            alert_key = 'high_disk'
            if alert_key not in self.active_alerts:
                alert = {
                    'type': 'high_disk',
                    'level': 'critical',
                    'message': f"磁盘使用率过高: {disk_data['disk_percent']:.1f}%",
                    'value': disk_data['disk_percent'],
                    'threshold': self.alert_thresholds['disk_percent'],
                    'timestamp': disk_data['timestamp']
                }
                alerts.append(alert)
                self.active_alerts[alert_key] = alert
        else:
            self.active_alerts.pop('high_disk', None)
        
        # 记录新告警
        for alert in alerts:
            logger.warning(f"系统告警: {alert['message']}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前系统状态"""
        try:
            timestamp = datetime.utcnow()
            return {
                'cpu': self._collect_cpu_data(timestamp),
                'memory': self._collect_memory_data(timestamp),
                'disk': self._collect_disk_data(timestamp),
                'network': self._collect_network_data(timestamp),
                'alerts': list(self.active_alerts.values())
            }
        except Exception as e:
            logger.error(f"获取系统状态失败: {str(e)}")
            return {'error': str(e)}
    
    def get_history_stats(self, minutes: int = 60) -> Dict[str, List]:
        """获取历史统计数据"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        def filter_by_time(data_list):
            return [
                item for item in data_list
                if datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00')) > cutoff_time
            ]
        
        return {
            'cpu': filter_by_time(list(self.cpu_history)),
            'memory': filter_by_time(list(self.memory_history)),
            'disk': filter_by_time(list(self.disk_history)),
            'network': filter_by_time(list(self.network_history))
        }
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """获取汇总统计"""
        if not self.cpu_history:
            return {}
        
        # CPU统计
        cpu_values = [item.get('cpu_percent', 0) for item in self.cpu_history if 'cpu_percent' in item]
        cpu_avg = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        cpu_max = max(cpu_values) if cpu_values else 0
        
        # 内存统计
        memory_values = [item.get('memory_percent', 0) for item in self.memory_history if 'memory_percent' in item]
        memory_avg = sum(memory_values) / len(memory_values) if memory_values else 0
        memory_max = max(memory_values) if memory_values else 0
        
        # 磁盘统计
        disk_values = [item.get('disk_percent', 0) for item in self.disk_history if 'disk_percent' in item]
        disk_avg = sum(disk_values) / len(disk_values) if disk_values else 0
        disk_max = max(disk_values) if disk_values else 0
        
        return {
            'cpu': {
                'avg': round(cpu_avg, 2),
                'max': round(cpu_max, 2),
                'current': cpu_values[-1] if cpu_values else 0
            },
            'memory': {
                'avg': round(memory_avg, 2),
                'max': round(memory_max, 2),
                'current': memory_values[-1] if memory_values else 0
            },
            'disk': {
                'avg': round(disk_avg, 2),
                'max': round(disk_max, 2),
                'current': disk_values[-1] if disk_values else 0
            },
            'active_alerts': len(self.active_alerts),
            'monitoring_duration': len(self.cpu_history) * self.monitor_interval
        }

# 全局监控器实例
_system_monitor = None

def get_system_monitor() -> SystemMonitor:
    """获取系统监控器实例"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
        _system_monitor.start_monitoring()
    return _system_monitor

def init_system_monitor():
    """初始化系统监控器"""
    monitor = get_system_monitor()
    logger.info("系统性能监控器已初始化")
    return monitor
