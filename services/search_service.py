# -*- coding: utf-8 -*-
"""
搜索服务 - AI题目搜索核心逻辑
"""
import json
import time
import requests
from typing import Dict, Any, Optional, List, Union

from models.models import db, QARecord
from services.cache import get_cache
from services.model_service import get_model_service
from utils.logger import get_logger
from utils.error_handler import get_error_handler, retry_with_backoff, ErrorCategory

logger = get_logger(__name__)

class SearchService:
    """搜索服务类"""

    def __init__(self):
        self.cache = get_cache()
        self.error_handler = get_error_handler()

    def search_question(self, question: str, question_type: Optional[str] = None, options: Optional[str] = None,
                       concurrent: bool = True, strategy: str = 'first_success') -> Dict[str, Any]:
        """搜索题目答案，支持并发搜索"""
        start_time = time.time()

        try:
            if concurrent:
                logger.info(f"并发AI搜索: {question[:50]}...")
                ai_result = self._concurrent_search(question, question_type, options, strategy)
            else:
                logger.info(f"单线程AI搜索: {question[:50]}...")
                ai_result = self._search_with_ai(question, question_type, options)

            if ai_result and ai_result.get('success'):
                # 可选：保存到数据库和缓存（如果需要的话）
                # self._save_to_database(question, ai_result['answer'], question_type, options)
                # self.cache.set(question, ai_result['answer'], question_type, options)

                logger.info(f"AI搜索成功: {question[:50]}...")
                return {
                    'success': True,
                    'answer': ai_result['answer'],
                    'source': ai_result.get('source', 'ai_direct'),
                    'search_time': round((time.time() - start_time) * 1000, 2),
                    'concurrent_used': concurrent,
                    'strategy_used': strategy
                }
            else:
                logger.warning(f"AI搜索失败: {ai_result.get('error', '未知错误') if ai_result else '无响应'}")
                return {
                    'success': False,
                    'message': 'AI搜索失败，请稍后重试',
                    'search_time': round((time.time() - start_time) * 1000, 2)
                }

        except Exception as e:
            # 使用增强的错误处理
            error_info = self.error_handler.handle_error(e, {
                'function': 'search_question',
                'question': question[:50],
                'question_type': question_type,
                'concurrent': concurrent,
                'strategy': strategy
            })

            logger.error(f"搜索异常: {error_info.message}")
            return {
                'success': False,
                'message': error_info.message,
                'error_category': error_info.category.value,
                'error_severity': error_info.severity.value,
                'should_retry': error_info.should_retry,
                'search_time': round((time.time() - start_time) * 1000, 2)
            }

    def _search_from_database(self, question: str, question_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """从数据库搜索"""
        try:
            # 检查是否在Flask应用上下文中
            from flask import has_app_context
            if not has_app_context():
                logger.debug("不在Flask应用上下文中，跳过数据库搜索")
                return None

            query = QARecord.query.filter(QARecord.question.contains(question))

            if question_type:
                query = query.filter_by(type=question_type)

            # 优先匹配完全相同的题目
            exact_match = query.filter_by(question=question).first()
            if exact_match:
                return {
                    'id': exact_match.id,
                    'answer': exact_match.answer,
                    'type': exact_match.type,
                    'options': exact_match.options
                }

            # 模糊匹配
            fuzzy_match = query.first()
            if fuzzy_match:
                return {
                    'id': fuzzy_match.id,
                    'answer': fuzzy_match.answer,
                    'type': fuzzy_match.type,
                    'options': fuzzy_match.options
                }

            return None

        except Exception as e:
            logger.error(f"数据库搜索异常: {str(e)}")
            return None

    def _concurrent_search(self, question: str, question_type: Optional[str] = None, options: Optional[str] = None, strategy: str = 'first_success') -> Optional[Dict[str, Any]]:
        """并发AI搜索"""
        import concurrent.futures

        try:
            model_service = get_model_service()

            def search_task(task_id: int):
                try:
                    logger.info(f"并发任务{task_id}开始搜索")
                    answer = model_service.generate_answer(question, question_type, options)
                    if answer:
                        logger.info(f"并发任务{task_id}搜索成功: {answer[:50]}...")
                        return {
                            'success': True,
                            'answer': answer,
                            'confidence': 0.8 + (task_id * 0.05),  # 稍微区分置信度
                            'task_id': task_id,
                            'source': f'ai_concurrent_{task_id}'
                        }
                    else:
                        logger.warning(f"并发任务{task_id}搜索失败: 无答案")
                        return None
                except Exception as e:
                    logger.error(f"并发任务{task_id}异常: {str(e)}")
                    return None

            # 根据策略调整并发数量
            if strategy == 'first_success':
                max_workers = 1  # first_success策略只需要1个任务
            else:
                max_workers = 3  # 其他策略使用3个并发任务

            results = []

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                futures = [executor.submit(search_task, i+1) for i in range(max_workers)]

                if strategy == 'first_success':
                    # 第一个成功策略：只启动一个任务
                    for future in concurrent.futures.as_completed(futures, timeout=30):
                        try:
                            result = future.result()
                            if result and result.get('success'):
                                logger.info(f"搜索成功(first_success): 任务{result.get('task_id')}")
                                return result
                        except Exception as e:
                            logger.error(f"搜索任务执行异常: {str(e)}")
                            continue
                else:
                    # best_match策略：等待所有任务完成，选择最佳结果
                    for future in concurrent.futures.as_completed(futures, timeout=30):
                        try:
                            result = future.result()
                            if result and result.get('success'):
                                results.append(result)
                        except Exception as e:
                            logger.error(f"并发任务执行异常: {str(e)}")
                            continue

                    if results:
                        # 选择置信度最高的结果
                        best_result = max(results, key=lambda x: x.get('confidence', 0))
                        logger.info(f"并发搜索成功(best_match): 任务{best_result.get('task_id')}, 共{len(results)}个结果")
                        return best_result

            logger.warning("所有并发搜索任务都失败了")
            return None

        except Exception as e:
            logger.error(f"并发AI搜索异常: {str(e)}")
            return None

    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=30.0)
    def _search_with_ai(self, question: str, question_type: Optional[str] = None, options: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """使用AI搜索（带重试机制）"""
        try:
            # 使用模型服务生成答案
            model_service = get_model_service()
            answer = model_service.generate_answer(question, question_type, options)

            if answer:
                return {
                    'success': True,
                    'answer': answer,
                    'confidence': 0.8,
                    'source': 'ai_single'
                }
            else:
                # 如果没有答案，抛出异常以触发重试
                raise Exception('无法生成答案')

        except Exception as e:
            # 使用增强的错误处理
            error_info = self.error_handler.handle_error(e, {
                'function': '_search_with_ai',
                'question': question[:50],
                'question_type': question_type
            })

            logger.error(f"AI搜索异常: {error_info.message}")

            # 重新抛出异常以触发重试机制
            raise e



    def _save_to_database(self, question: str, answer: str, question_type: Optional[str] = None, options: Optional[str] = None) -> Optional[int]:
        """保存到数据库"""
        try:
            # 检查是否在Flask应用上下文中
            from flask import has_app_context
            if not has_app_context():
                logger.debug("不在Flask应用上下文中，跳过数据库保存")
                return None

            # 检查是否已存在
            existing = QARecord.query.filter_by(question=question).first()
            if existing:
                return existing.id

            # 创建新记录
            new_record = QARecord(
                question=question,
                answer=answer,
                type=question_type or 'unknown',
                options=options or '',
                source='AI搜索',
                question_length=len(question),
                created_at=time.time()
            )

            db.session.add(new_record)
            db.session.commit()

            logger.info(f"保存新题目到数据库: {new_record.id}")
            return new_record.id

        except Exception as e:
            logger.error(f"保存到数据库异常: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return None

    def batch_search(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量搜索"""
        results = []

        for i, question_data in enumerate(questions):
            question = question_data.get('question', '')
            question_type = question_data.get('type')
            options = question_data.get('options')

            if not question:
                results.append({
                    'index': i,
                    'success': False,
                    'message': '题目内容为空',
                    'question': question
                })
                continue

            # 搜索单个题目
            result = self.search_question(question, question_type, options)
            result['index'] = i
            result['question'] = question
            results.append(result)

            # 添加延迟避免过于频繁的请求
            time.sleep(0.1)

        return results

    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计"""
        try:
            # 缓存统计
            cache_stats = self.cache.get_stats()

            # 数据库统计
            total_questions = QARecord.query.count()
            recent_questions = QARecord.query.filter(
                QARecord.created_at >= time.time() - 86400  # 最近24小时
            ).count()

            return {
                'cache_stats': cache_stats,
                'database_stats': {
                    'total_questions': total_questions,
                    'recent_questions': recent_questions
                },
                'search_performance': {
                    'cache_hit_rate': cache_stats.get('hit_rate', 0),
                    'total_searches': cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
                }
            }

        except Exception as e:
            logger.error(f"获取搜索统计异常: {str(e)}")
            return {}

# 全局搜索服务实例
_search_service = None

def get_search_service() -> SearchService:
    """获取搜索服务实例"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
