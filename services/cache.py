# -*- coding: utf-8 -*-
"""
Redis缓存实现 - 优化版本
支持多级缓存、缓存预热、统计监控
"""
import redis
import hashlib
import json
import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)

class RedisCache:
    """Redis缓存实现 - 优化版本"""

    def __init__(self, host='localhost', port=6379, db=0, password=None, expiration=86400):
        """初始化Redis连接 - 使用优化配置"""
        try:
            # 使用连接池优化性能
            connection_pool = redis.ConnectionPool(
                host=host,
                port=port,
                password=password,
                db=db,
                max_connections=50,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )

            self.redis = redis.Redis(
                connection_pool=connection_pool,
                decode_responses=True
            )
            self.expiration = expiration

            # 测试连接
            self.redis.ping()
            logger.info("Redis缓存连接成功")

        except Exception as e:
            logger.warning(f"Redis连接失败，使用内存缓存: {str(e)}")
            self.redis = None
            self._memory_cache = {}

        # 多级缓存配置
        self.cache_levels = {
            'hot': 7200,    # 2小时 - 热门题目
            'normal': 3600, # 1小时 - 普通题目
            'cold': 1800    # 30分钟 - 冷门题目
        }

        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'hot_cache_hits': 0,
            'normal_cache_hits': 0,
            'cold_cache_hits': 0,
            'preheated_hits': 0,
            'adaptive_expires': 0
        }

        # 缓存预热配置
        self.preheat_enabled = True
        self.preheat_patterns = [
            '单选题', '多选题', '判断题', '填空题',
            '计算机', '数学', '英语', '物理', '化学'
        ]

        # 智能过期配置
        self.adaptive_expiry_enabled = True
        self.access_frequency_threshold = 5  # 访问频率阈值
        self.popularity_boost_factor = 2.0   # 热门内容过期时间倍数

        # 访问频率统计
        self.access_frequency = {}
        self.access_lock = threading.Lock()

        # 启动统计数据记录线程
        self._start_stats_recorder()

        # 启动缓存预热
        if self.preheat_enabled:
            self._start_cache_preheating()

    def _start_stats_recorder(self):
        """启动统计数据记录线程"""
        if self.redis:
            # 创建并启动记录线程
            self.stats_recorder = StatsRecorder(self)
            self.stats_recorder.start()
            logger.info("缓存统计记录器已启动")

    def _generate_key(self, question, question_type=None, options=None, prefix="qa_cache"):
        """生成缓存键"""
        content = f"{question}_{question_type or ''}_{options or ''}"
        hash_key = hashlib.md5(content.encode('utf-8')).hexdigest()
        return f"{prefix}:{hash_key}"

    def _get_cache_keys(self, pattern="qa_cache:*"):
        """安全地获取缓存键列表"""
        try:
            if self.redis:
                keys = self.redis.keys(pattern)
                # 确保返回的是列表类型
                if isinstance(keys, (list, tuple)):
                    return list(keys)
                else:
                    logger.warning(f"Redis keys() 返回了非列表类型: {type(keys)}")
                    return []
            else:
                # 内存缓存版本
                if pattern == "qa_cache:*":
                    return list(self._memory_cache.keys())
                else:
                    # 简单的模式匹配
                    prefix = pattern.replace("*", "")
                    return [key for key in self._memory_cache.keys() if key.startswith(prefix)]
        except Exception as e:
            logger.error(f"获取缓存键失败: {str(e)}")
            return []

    def get(self, question, question_type=None, options=None):
        """获取缓存 - 增强版本，支持智能过期和访问频率统计"""
        try:
            key = self._generate_key(question, question_type, options)

            if self.redis:
                cached = self.redis.get(key)
                if cached:
                    self.stats['hits'] += 1

                    # 更新访问频率
                    self._update_access_frequency(key)

                    # 智能过期时间调整
                    if self.adaptive_expiry_enabled:
                        new_ttl = self._calculate_adaptive_ttl(key, question_type)
                        self.redis.expire(key, new_ttl)
                        if new_ttl > self.expiration:
                            self.stats['adaptive_expires'] += 1
                    else:
                        self.redis.expire(key, self.expiration)

                    # 检查是否是预热缓存命中
                    if self._is_preheated_content(key):
                        self.stats['preheated_hits'] += 1

                    return cached
                else:
                    self.stats['misses'] += 1
                    return None
            else:
                # 使用内存缓存
                if key in self._memory_cache:
                    cache_data = self._memory_cache[key]
                    current_time = time.time()

                    # 计算自适应过期时间
                    ttl = self.expiration
                    if self.adaptive_expiry_enabled:
                        ttl = self._calculate_adaptive_ttl(key, question_type)

                    if current_time - cache_data['timestamp'] < ttl:
                        self.stats['hits'] += 1
                        self._update_access_frequency(key)

                        # 更新时间戳以延长生命周期
                        cache_data['last_access'] = current_time

                        return cache_data['value']
                    else:
                        del self._memory_cache[key]

                self.stats['misses'] += 1
                return None

        except Exception as e:
            logger.error(f"缓存获取失败: {str(e)}")
            self.stats['misses'] += 1
            return None

    def set(self, question, answer, question_type=None, options=None, ttl=None):
        """设置缓存 - 智能多级缓存策略"""
        try:
            key = self._generate_key(question, question_type, options)

            # 智能选择缓存级别
            cache_level = self._determine_cache_level(question, question_type)
            expiration = ttl or self.cache_levels.get(cache_level, self.expiration)

            if self.redis:
                # 使用pipeline提高性能
                pipe = self.redis.pipeline()
                pipe.setex(key, expiration, answer)

                # 记录缓存元数据
                meta_key = f"meta:{key}"
                meta_data = {
                    'created_at': time.time(),
                    'question_type': question_type or 'unknown',
                    'access_count': 1,
                    'cache_level': cache_level,
                    'question_length': len(question)
                }
                pipe.setex(meta_key, expiration, json.dumps(meta_data))

                # 更新热度统计
                self.update_question_popularity(question, question_type, options)

                pipe.execute()
                logger.debug(f"缓存设置成功: {cache_level}级缓存, TTL={expiration}秒")
            else:
                # 使用内存缓存
                self._memory_cache[key] = {
                    'value': answer,
                    'timestamp': time.time(),
                    'cache_level': cache_level
                }

                # 限制内存缓存大小
                if len(self._memory_cache) > 1000:
                    # 删除最旧的缓存
                    oldest_key = min(self._memory_cache.keys(),
                                   key=lambda k: self._memory_cache[k]['timestamp'])
                    del self._memory_cache[oldest_key]

            self.stats['sets'] += 1
            return True

        except Exception as e:
            logger.error(f"缓存设置失败: {str(e)}")
            return False

    def _determine_cache_level(self, question, question_type):
        """智能确定缓存级别"""
        # 基于题目特征判断热度
        question_len = len(question)

        # 短题目通常是热门题目
        if question_len < 50:
            return 'hot'

        # 选择题通常比填空题更热门
        if question_type in ['single', 'multiple']:
            return 'normal'

        # 长题目或特殊类型题目
        return 'cold'

    def delete(self, question, question_type=None, options=None):
        """删除缓存"""
        try:
            key = self._generate_key(question, question_type, options)

            if self.redis:
                result = self.redis.delete(key)
            else:
                result = 1 if key in self._memory_cache else 0
                if key in self._memory_cache:
                    del self._memory_cache[key]

            self.stats['deletes'] += 1
            return result

        except Exception as e:
            logger.error(f"缓存删除失败: {str(e)}")
            return 0

    def clear(self):
        """清除所有缓存"""
        try:
            if self.redis:
                qa_keys = self._get_cache_keys("qa_cache:*")
                if qa_keys and len(qa_keys) > 0:
                    return self.redis.delete(*qa_keys)
                return 0
            else:
                count = len(self._memory_cache)
                self._memory_cache.clear()
                return count

        except Exception as e:
            logger.error(f"缓存清除失败: {str(e)}")
            return 0

    @property
    def size(self):
        """获取缓存大小"""
        try:
            if self.redis:
                qa_keys = self._get_cache_keys("qa_cache:*")
                return len(qa_keys)
            else:
                return len(self._memory_cache)
        except Exception as e:
            logger.error(f"获取缓存大小失败: {str(e)}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

            stats = {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'sets': self.stats['sets'],
                'deletes': self.stats['deletes'],
                'hit_rate': round(hit_rate, 2),
                'total_keys': self.size,
                'connected': self.is_connected(),
                'type': 'Redis' if self.redis else 'Memory'
            }

            if self.redis:
                try:
                    info = self.redis.info('memory')
                    # 确保info是字典类型
                    if isinstance(info, dict):
                        stats['memory_usage'] = info.get('used_memory_human', 'N/A')
                    else:
                        stats['memory_usage'] = 'N/A'
                except Exception as e:
                    logger.debug(f"获取Redis内存信息失败: {str(e)}")
                    stats['memory_usage'] = 'N/A'

            return stats

        except Exception as e:
            logger.error(f"获取缓存统计失败: {str(e)}")
            return {}

    def is_connected(self) -> bool:
        """检查缓存连接状态"""
        try:
            if self.redis:
                self.redis.ping()
                return True
            return False
        except Exception:
            return False

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取Redis内存使用情况"""
        try:
            if not self.redis:
                return {
                    'used_memory': 0,
                    'used_memory_human': '0B',
                    'used_memory_peak': 0,
                    'used_memory_peak_human': '0B',
                    'used_memory_lua': 0,
                    'used_memory_lua_human': '0B',
                    'mem_fragmentation_ratio': 0,
                    'mem_allocator': 'N/A'
                }
                
            info = self.redis.info('memory')
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                'used_memory_lua': info.get('used_memory_lua', 0),
                'used_memory_lua_human': info.get('used_memory_lua_human', '0B'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                'mem_allocator': info.get('mem_allocator', 'N/A')
            }
        except Exception as e:
            logger.error(f"获取内存使用情况失败: {str(e)}")
            return {
                'used_memory': 0,
                'used_memory_human': '0B',
                'error': str(e)
            }

    def get_keys(self, pattern: str = "qa_cache:*") -> List[str]:
        """获取匹配模式的所有键"""
        return self._get_cache_keys(pattern)
        
    def get_key_info(self, key: str) -> Optional[Dict[str, Any]]:
        """获取键的详细信息"""
        try:
            if self.redis:
                # 检查键是否存在
                if not self.redis.exists(key):
                    return None
                    
                # 获取键类型
                key_type = self.redis.type(key).decode('utf-8') if isinstance(self.redis.type(key), bytes) else self.redis.type(key)
                
                # 获取TTL
                ttl = self.redis.ttl(key)
                
                # 获取键大小
                size = 0
                if key_type == 'string':
                    size = self.redis.strlen(key)
                elif key_type == 'hash':
                    size = sum(len(k) + len(v) for k, v in self.redis.hgetall(key).items())
                elif key_type == 'list':
                    size = sum(len(item) for item in self.redis.lrange(key, 0, -1))
                elif key_type == 'set':
                    size = sum(len(member) for member in self.redis.smembers(key))
                elif key_type == 'zset':
                    size = sum(len(member) for member in self.redis.zrange(key, 0, -1))
                
                # 格式化大小
                size_str = self._format_size(size)
                
                # 获取元数据
                meta_key = f"meta:{key}"
                meta_data = {}
                if self.redis.exists(meta_key):
                    try:
                        meta_data = json.loads(self.redis.get(meta_key))
                    except:
                        pass
                
                # 创建时间
                created_at = meta_data.get('created_at', time.time())
                created_at_str = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S')
                
                return {
                    'key': key,
                    'type': key_type,
                    'ttl': ttl,
                    'size': size_str,
                    'size_bytes': size,
                    'created_at': created_at_str,
                    'access_count': meta_data.get('access_count', 0),
                    'cache_level': meta_data.get('cache_level', 'unknown'),
                    'question_type': meta_data.get('question_type', 'unknown')
                }
            else:
                # 内存缓存版本
                if key in self._memory_cache:
                    cache_data = self._memory_cache[key]
                    created_at = cache_data.get('timestamp', time.time())
                    created_at_str = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 计算TTL
                    ttl = -1
                    if self.expiration > 0:
                        elapsed = time.time() - created_at
                        ttl = max(0, int(self.expiration - elapsed))
                    
                    # 计算大小
                    value = cache_data.get('value', '')
                    size = len(value) if value else 0
                    size_str = self._format_size(size)
                    
                    return {
                        'key': key,
                        'type': 'string',
                        'ttl': ttl,
                        'size': size_str,
                        'size_bytes': size,
                        'created_at': created_at_str,
                        'access_count': cache_data.get('access_count', 0),
                        'cache_level': cache_data.get('cache_level', 'unknown')
                    }
                return None
        except Exception as e:
            logger.error(f"获取键信息失败: {str(e)}")
            return None
            
    def _format_size(self, size_bytes: int) -> str:
        """格式化字节大小为人类可读格式"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
            
    def get_raw(self, key: str) -> str:
        """获取键的原始值"""
        try:
            if self.redis:
                key_type = self.redis.type(key).decode('utf-8') if isinstance(self.redis.type(key), bytes) else self.redis.type(key)
                
                if key_type == 'string':
                    value = self.redis.get(key)
                    return value if value is None else value
                elif key_type == 'hash':
                    return json.dumps(self.redis.hgetall(key), ensure_ascii=False)
                elif key_type == 'list':
                    return json.dumps(self.redis.lrange(key, 0, -1), ensure_ascii=False)
                elif key_type == 'set':
                    return json.dumps(list(self.redis.smembers(key)), ensure_ascii=False)
                elif key_type == 'zset':
                    return json.dumps(self.redis.zrange(key, 0, -1, withscores=True), ensure_ascii=False)
                else:
                    return "不支持的数据类型"
            else:
                # 内存缓存版本
                if key in self._memory_cache:
                    return self._memory_cache[key].get('value', '')
                return None
        except Exception as e:
            logger.error(f"获取原始值失败: {str(e)}")
            return f"获取失败: {str(e)}"
            
    def delete_key(self, key: str) -> bool:
        """删除指定键"""
        try:
            if self.redis:
                # 同时删除元数据
                meta_key = f"meta:{key}"
                pipe = self.redis.pipeline()
                pipe.delete(key)
                pipe.delete(meta_key)
                results = pipe.execute()
                return results[0] > 0
            else:
                # 内存缓存版本
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    return True
                return False
        except Exception as e:
            logger.error(f"删除键失败: {str(e)}")
            return False

    def get_hot_questions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门问题缓存"""
        try:
            result = []
            
            if self.redis:
                # 获取所有缓存键
                keys = self._get_cache_keys("qa_cache:*")
                
                # 获取每个键的访问次数
                key_stats = []
                for key in keys:
                    meta_key = f"meta:{key}"
                    if self.redis.exists(meta_key):
                        try:
                            meta_data = json.loads(self.redis.get(meta_key))
                            access_count = meta_data.get('access_count', 0)
                            
                            # 获取键信息
                            key_info = self.get_key_info(key)
                            if key_info:
                                key_info['hits'] = access_count
                                key_stats.append(key_info)
                        except:
                            pass
                
                # 按访问次数排序
                key_stats.sort(key=lambda x: x.get('hits', 0), reverse=True)
                
                # 取前limit个
                result = key_stats[:limit]
            else:
                # 内存缓存版本
                key_stats = []
                for key, data in self._memory_cache.items():
                    if key.startswith('qa_cache:'):
                        access_count = data.get('access_count', 0)
                        size = len(data.get('value', ''))
                        size_str = self._format_size(size)
                        
                        key_stats.append({
                            'key': key,
                            'hits': access_count,
                            'size': size_str,
                            'size_bytes': size,
                            'type': 'string',
                            'cache_level': data.get('cache_level', 'unknown')
                        })
                
                # 按访问次数排序
                key_stats.sort(key=lambda x: x.get('hits', 0), reverse=True)
                
                # 取前limit个
                result = key_stats[:limit]
            
            return result
        except Exception as e:
            logger.error(f"获取热门问题失败: {str(e)}")
            return []

    def update_question_popularity(self, question, question_type=None, options=None):
        """更新问题热度"""
        try:
            if self.redis:
                key = self._generate_key(question, question_type, options)
                question_hash = key.split(':')[1]

                hot_key = "hot_questions"
                self.redis.zincrby(hot_key, 1, question_hash)

                # 保持热门问题列表不超过1000个
                self.redis.zremrangebyrank(hot_key, 0, -1001)

        except Exception as e:
            logger.error(f"更新问题热度失败: {str(e)}")

    def preload_cache(self, questions_data: List[Dict[str, Any]]):
        """缓存预热 - 批量加载常用问题"""
        try:
            if not self.redis:
                return 0

            pipe = self.redis.pipeline()
            loaded_count = 0

            for data in questions_data:
                question = data.get('question', '')
                answer = data.get('answer', '')
                question_type = data.get('type', '')
                options = data.get('options', '')

                if question and answer:
                    key = self._generate_key(question, question_type, options)
                    pipe.setex(key, self.expiration, answer)
                    loaded_count += 1

            pipe.execute()
            logger.info(f"缓存预热完成，加载了 {loaded_count} 个问题")
            return loaded_count

        except Exception as e:
            logger.error(f"缓存预热失败: {str(e)}")
            return 0

    def _update_access_frequency(self, key: str):
        """更新访问频率统计"""
        with self.access_lock:
            if key not in self.access_frequency:
                self.access_frequency[key] = {
                    'count': 0,
                    'first_access': time.time(),
                    'last_access': time.time()
                }

            self.access_frequency[key]['count'] += 1
            self.access_frequency[key]['last_access'] = time.time()

            # 清理过期的访问频率记录（超过24小时）
            current_time = time.time()
            expired_keys = [
                k for k, v in self.access_frequency.items()
                if current_time - v['last_access'] > 86400
            ]
            for k in expired_keys:
                del self.access_frequency[k]

    def _calculate_adaptive_ttl(self, key: str, question_type: Optional[str] = None) -> int:
        """计算自适应过期时间"""
        base_ttl = self.expiration

        # 基于访问频率调整
        if key in self.access_frequency:
            freq_data = self.access_frequency[key]
            access_count = freq_data['count']

            # 如果访问频率高，延长过期时间
            if access_count >= self.access_frequency_threshold:
                base_ttl = int(base_ttl * self.popularity_boost_factor)

        # 基于题目类型调整
        if question_type:
            type_multipliers = {
                'single': 1.2,    # 单选题稍微延长
                'multiple': 1.1,  # 多选题稍微延长
                'judgment': 1.0,  # 判断题正常
                'completion': 0.9 # 填空题稍微缩短
            }
            multiplier = type_multipliers.get(question_type, 1.0)
            base_ttl = int(base_ttl * multiplier)

        # 限制最大和最小TTL
        max_ttl = self.expiration * 3  # 最大3倍
        min_ttl = self.expiration // 2  # 最小0.5倍

        return max(min_ttl, min(max_ttl, base_ttl))

    def _is_preheated_content(self, key: str) -> bool:
        """检查是否是预热内容"""
        # 简单实现：检查key是否包含预热模式
        if hasattr(self, '_preheated_keys'):
            return key in self._preheated_keys
        return False

    def _start_cache_preheating(self):
        """启动缓存预热"""
        def preheat_worker():
            """缓存预热工作线程"""
            try:
                logger.info("开始缓存预热...")

                # 预热常见题目模式
                common_patterns = [
                    "下列哪个选项是正确的",
                    "以下说法正确的是",
                    "关于...的描述，正确的是",
                    "判断题：",
                    "填空题：",
                    "计算题："
                ]

                self._preheated_keys = set()

                for pattern in common_patterns:
                    try:
                        # 模拟预热这些模式的缓存
                        key = self._generate_key(pattern, prefix="preheat")

                        if self.redis:
                            # 设置预热标记
                            self.redis.setex(f"{key}:preheated", 3600, "1")

                        self._preheated_keys.add(key)

                        # 避免过于频繁的操作
                        time.sleep(0.1)

                    except Exception as e:
                        logger.warning(f"预热模式 '{pattern}' 失败: {str(e)}")

                logger.info(f"缓存预热完成，预热了 {len(self._preheated_keys)} 个模式")

            except Exception as e:
                logger.error(f"缓存预热异常: {str(e)}")

        # 启动预热线程
        preheat_thread = threading.Thread(target=preheat_worker, daemon=True)
        preheat_thread.start()
        logger.info("缓存预热线程已启动")

# 全局缓存实例
_cache_instance = None

def get_cache() -> RedisCache:
    """获取缓存实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance

class StatsRecorder(threading.Thread):
    """缓存统计数据记录器"""
    
    def __init__(self, cache_instance):
        """初始化统计记录器"""
        super().__init__(daemon=True)  # 设置为守护线程，主程序退出时自动结束
        self.cache = cache_instance
        self.running = True
        
        # 统计数据记录间隔
        self.intervals = {
            '1h': 300,   # 5分钟记录一次，保存12个点
            '24h': 3600,  # 1小时记录一次，保存24个点
            '7d': 86400   # 1天记录一次，保存7个点
        }
        
        # 统计数据最大保存点数
        self.max_points = {
            '1h': 12,
            '24h': 24,
            '7d': 7
        }
        
        # 上次记录时间
        self.last_record_time = {
            '1h': 0,
            '24h': 0,
            '7d': 0
        }

    def run(self):
        """运行统计记录线程"""
        try:
            while self.running:
                try:
                    self._record_stats()
                except Exception as e:
                    logger.error(f"记录缓存统计数据异常: {str(e)}")
                
                # 每分钟检查一次是否需要记录
                time.sleep(60)
        except Exception as e:
            logger.error(f"缓存统计记录器异常: {str(e)}")

    def _record_stats(self):
        """记录缓存统计数据"""
        if not self.cache.redis:
            return
        
        current_time = int(time.time())
        stats = self.cache.get_stats()
        
        # 获取当前统计数据
        hit_rate = stats.get('hit_rate', 0)
        total_requests = stats.get('hits', 0) + stats.get('misses', 0)
        
        # 检查各个时间段是否需要记录
        for period, interval in self.intervals.items():
            if current_time - self.last_record_time.get(period, 0) >= interval:
                # 更新最后记录时间
                self.last_record_time[period] = current_time
                
                # 创建记录数据
                record = {
                    'timestamp': current_time,
                    'hit_rate': hit_rate,
                    'requests': total_requests,
                    'time_str': datetime.fromtimestamp(current_time).strftime('%H:%M' if period != '7d' else '%m-%d')
                }
                
                # 记录到Redis
                history_key = f"cache:stats:history:{period}"
                
                try:
                    # 添加新记录
                    self.cache.redis.rpush(history_key, json.dumps(record))
                    
                    # 保持列表长度不超过最大点数
                    list_len = self.cache.redis.llen(history_key)
                    if list_len > self.max_points.get(period, 24):
                        # 删除多余的旧数据
                        excess = list_len - self.max_points.get(period, 24)
                        if excess > 0:
                            self.cache.redis.ltrim(history_key, excess, -1)
                    
                    logger.debug(f"已记录{period}缓存统计数据: 命中率={hit_rate}%, 请求数={total_requests}")
                except Exception as e:
                    logger.error(f"记录{period}缓存统计数据失败: {str(e)}")
    
    def stop(self):
        """停止统计记录线程"""
        self.running = False
