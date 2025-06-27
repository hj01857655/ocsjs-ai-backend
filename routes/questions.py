# -*- coding: utf-8 -*-
"""
题目相关API路由 - 适配前端需求
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json
import random

from models.models import db, QARecord, User
from utils.auth import token_required, optional_auth
from utils.logger import get_logger
from utils.error_handler import get_error_handler
from utils.response_handler import get_response_handler, success_response, error_response, handle_exception
from services.search_service import get_search_service
from services.cache import get_cache
from routes.logs import add_system_log

questions_bp = Blueprint('questions', __name__)
logger = get_logger(__name__)

@questions_bp.route('/search', methods=['POST'])
@optional_auth
def search_question(current_user):
    """AI搜题接口"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据格式错误', status_code=400)

        question = data.get('question', '').strip()
        if not question:
            return error_response('题目内容不能为空', status_code=400)

        # 使用搜索服务
        search_service = get_search_service()
        result = search_service.search_question(
            question=question,
            question_type=data.get('type'),
            options=data.get('options'),
            concurrent=data.get('concurrent', True),
            strategy=data.get('strategy', 'first_success')
        )

        if result.get('success'):
            # 记录搜索成功日志
            add_system_log(
                level='info',
                source='search',
                message=f'题目搜索成功: {question[:50]}...',
                user_id=current_user.id if current_user else None,
                ip_address=request.remote_addr,
                context={'source': result.get('source'), 'search_time': result.get('search_time')}
            )

            logger.info(f"搜题成功 - {result.get('source')}: {question[:50]}...")

            # 构建响应数据
            response_data = {
                'question': question,
                'answer': result.get('answer'),
                'type': data.get('type', 'unknown'),
                'options': data.get('options', ''),
                'source': result.get('source'),
                'search_time': result.get('search_time'),
                'question_id': result.get('question_id'),
                'confidence': 0.9
            }

            # 添加元数据
            meta = {
                'concurrent_used': result.get('concurrent_used', False),
                'strategy_used': result.get('strategy_used', 'unknown')
            }

            return success_response(data=response_data, message='搜索成功', meta=meta)
        else:
            # 记录搜索失败日志
            add_system_log(
                level='warn',
                source='search',
                message=f'题目搜索失败: {question[:50]}...',
                user_id=current_user.id if current_user else None,
                ip_address=request.remote_addr,
                context={'reason': result.get('message'), 'search_time': result.get('search_time')}
            )

            logger.warning(f"搜题失败: {question[:50]}...")

            # 构建增强的错误响应
            error_response = {
                'success': False,
                'message': result.get('message', '暂时无法找到答案'),
                'search_time': result.get('search_time')
            }

            # 添加错误分类信息（如果有的话）
            if 'error_category' in result:
                error_response['error_category'] = result['error_category']
            if 'error_severity' in result:
                error_response['error_severity'] = result['error_severity']
            if 'should_retry' in result:
                error_response['should_retry'] = result['should_retry']

            return jsonify(error_response)

    except Exception as e:
        # 使用增强的错误处理
        context = {
            'function': 'search_question',
            'user_id': current_user.id if current_user else None,
            'ip_address': request.remote_addr
        }

        # 安全地添加question信息
        try:
            context['question'] = question[:50]
        except:
            context['question'] = 'unknown'

        return handle_exception(e, context=context)

@questions_bp.route('/batch-search', methods=['POST'])
@optional_auth
def batch_search(current_user):
    """批量搜题接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        questions = data.get('questions', [])
        if not questions or not isinstance(questions, list):
            return jsonify({
                'success': False,
                'message': '题目列表不能为空'
            }), 400

        if len(questions) > 100:
            return jsonify({
                'success': False,
                'message': '批量搜题最多支持100个题目'
            }), 400

        # 使用搜索服务进行批量搜索
        search_service = get_search_service()

        # 构建搜索数据
        search_data = []
        for question in questions:
            if isinstance(question, str):
                search_data.append({'question': question.strip()})
            elif isinstance(question, dict):
                search_data.append(question)

        # 执行批量搜索
        results = search_service.batch_search(search_data)

        return jsonify({
            'success': True,
            'message': '批量搜索完成',
            'data': {
                'results': results,
                'total': len(questions),
                'success_count': len([r for r in results if r['success']]),
                'failed_count': len([r for r in results if not r['success']])
            }
        })

    except Exception as e:
        logger.error(f"批量搜题异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '批量搜索失败'
        }), 500

@questions_bp.route('/list', methods=['GET'])
@optional_auth
def get_questions_list(current_user):
    """获取题目列表"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        keyword = request.args.get('keyword', '').strip()
        question_type = request.args.get('type', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        favorite = request.args.get('favorite')

        # 构建查询
        query = QARecord.query

        # 如果有用户登录，优先显示该用户的题目
        if current_user:
            query = query.filter_by(user_id=current_user.id)

        # 关键词搜索
        if keyword:
            query = query.filter(QARecord.question.contains(keyword))

        # 题型筛选
        if question_type:
            query = query.filter_by(type=question_type)

        # 难度筛选
        if difficulty:
            query = query.filter_by(difficulty=difficulty)

        # 收藏筛选
        if favorite is not None:
            is_favorite = favorite.lower() == 'true'
            query = query.filter_by(is_favorite=is_favorite)

        # 排序
        sort_by = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'desc')

        if hasattr(QARecord, sort_by):
            sort_column = getattr(QARecord, sort_by)
            if order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())

        # 分页
        total = query.count()
        questions = query.offset((page - 1) * size).limit(size).all()

        return jsonify({
            'success': True,
            'data': {
                'questions': [q.to_dict() for q in questions],
                'pagination': {
                    'page': page,
                    'size': size,
                    'total': total,
                    'pages': (total + size - 1) // size
                }
            }
        })

    except Exception as e:
        logger.error(f"获取题目列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取题目列表失败'
        }), 500

@questions_bp.route('/<int:question_id>', methods=['GET'])
@optional_auth
def get_question_detail(current_user, question_id):
    """获取题目详情"""
    try:
        question = QARecord.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'message': '题目不存在'
            }), 404

        # 增加查看次数
        question.view_count = (question.view_count or 0) + 1
        question.last_viewed = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'question': question.to_dict()
            }
        })

    except Exception as e:
        logger.error(f"获取题目详情异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取题目详情失败'
        }), 500

@questions_bp.route('/<int:question_id>/favorite', methods=['POST'])
@token_required
def toggle_favorite(current_user, question_id):
    """切换收藏状态"""
    try:
        question = QARecord.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'message': '题目不存在'
            }), 404

        # 只能操作自己的题目
        if question.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': '无权限操作此题目'
            }), 403

        question.is_favorite = not question.is_favorite
        question.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '收藏状态已更新',
            'data': {
                'is_favorite': question.is_favorite
            }
        })

    except Exception as e:
        logger.error(f"切换收藏状态异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '操作失败'
        }), 500

@questions_bp.route('/statistics', methods=['GET'])
@optional_auth
def get_statistics(current_user):
    """获取题库统计信息"""
    try:
        # 基础统计
        total_questions = QARecord.query.count()

        if current_user:
            user_questions = QARecord.query.filter_by(user_id=current_user.id).count()
            user_favorites = QARecord.query.filter_by(user_id=current_user.id, is_favorite=True).count()
        else:
            user_questions = 0
            user_favorites = 0

        # 今日新增
        today = datetime.utcnow().date()
        today_questions = QARecord.query.filter(
            QARecord.created_at >= today
        ).count()

        # 题型分布
        type_stats = db.session.query(
            QARecord.type,
            db.func.count(QARecord.id).label('count')
        ).group_by(QARecord.type).all()

        # 难度分布
        difficulty_stats = db.session.query(
            QARecord.difficulty,
            db.func.count(QARecord.id).label('count')
        ).group_by(QARecord.difficulty).all()

        return jsonify({
            'success': True,
            'data': {
                'overview': {
                    'total_questions': total_questions,
                    'user_questions': user_questions,
                    'user_favorites': user_favorites,
                    'today_questions': today_questions
                },
                'type_distribution': [
                    {'type': item[0] or 'unknown', 'count': item[1]}
                    for item in type_stats
                ],
                'difficulty_distribution': [
                    {'difficulty': item[0] or 'medium', 'count': item[1]}
                    for item in difficulty_stats
                ]
            }
        })

    except Exception as e:
        logger.error(f"获取统计信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取统计信息失败'
        }), 500

@questions_bp.route('/dashboard', methods=['GET'])
@optional_auth
def get_dashboard_data(current_user):
    """获取仪表板数据"""
    try:
        from services.cache import get_cache
        from services.api_proxy_pool import get_api_proxy_pool
        import psutil

        # 基础统计
        total_questions = QARecord.query.count()

        # 今日搜索数（基于今日创建的记录）
        today = datetime.utcnow().date()
        today_searches = QARecord.query.filter(
            QARecord.created_at >= today
        ).count()

        # 活跃用户数（最近7天有活动的用户）
        from models.models import User
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = User.query.filter(
            User.last_login >= week_ago
        ).count()

        # 缓存命中率
        cache = get_cache()
        cache_stats = cache.get_stats()
        cache_hit_rate = cache_stats.get('hit_rate', 0)

        # 题型分布
        type_stats = db.session.query(
            QARecord.type,
            db.func.count(QARecord.id).label('count')
        ).group_by(QARecord.type).all()

        # 最近7天的搜索趋势
        trend_data = []
        for i in range(7):
            date = datetime.utcnow().date() - timedelta(days=6-i)
            count = QARecord.query.filter(
                db.func.date(QARecord.created_at) == date
            ).count()
            trend_data.append({
                'date': date.strftime('%m-%d'),
                'count': count
            })

        # 系统状态
        try:
            # 数据库状态
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            db_status = 'healthy'
            db_detail = '连接正常，响应时间 < 100ms'
        except:
            db_status = 'error'
            db_detail = '连接异常'

        # Redis状态
        try:
            cache.redis.ping() if cache.redis else None
            redis_status = 'healthy'
            redis_detail = f'运行正常，内存使用率 {cache_stats.get("memory_usage", "未知")}'
        except:
            redis_status = 'error'
            redis_detail = '连接异常'

        # API代理池状态
        try:
            proxy_pool = get_api_proxy_pool()
            pool_status = proxy_pool.get_pool_status()
            api_status = 'healthy'
            api_detail = f'{pool_status.get("active_count", 0)}个代理可用，成功率 {pool_status.get("success_rate", 0):.1f}%'
        except:
            api_status = 'error'
            api_detail = '代理池异常'

        # 系统负载
        try:
            # 快速获取系统信息，避免超时
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            system_status = 'healthy' if cpu_percent < 80 and memory_percent < 80 else 'warning'
            system_detail = f'CPU {cpu_percent:.1f}%, 内存 {memory_percent:.1f}%'
        except Exception as e:
            system_status = 'error'
            system_detail = f'无法获取系统信息: {str(e)}'

        # 最近活动（最近的问答记录）
        recent_activities = []
        recent_records = QARecord.query.order_by(QARecord.created_at.desc()).limit(5).all()

        for record in recent_records:
            user_name = 'anonymous'
            if record.user_id:
                user = User.query.get(record.user_id)
                if user:
                    user_name = user.username

            recent_activities.append({
                'id': record.id,
                'title': f'用户 {user_name} 搜索了{record.type or "题目"}',
                'time': int(record.created_at.timestamp() * 1000),
                'icon': 'Search'
            })

        return jsonify({
            'success': True,
            'data': {
                'stats': {
                    'total_questions': total_questions,
                    'today_searches': today_searches,
                    'active_users': active_users,
                    'cache_hit_rate': f'{cache_hit_rate:.1f}%'
                },
                'type_distribution': [
                    {'name': item[0] or '未分类', 'value': item[1]}
                    for item in type_stats
                ],
                'trend_data': trend_data,
                'system_status': [
                    {
                        'name': '数据库',
                        'status': db_status,
                        'detail': db_detail
                    },
                    {
                        'name': 'Redis缓存',
                        'status': redis_status,
                        'detail': redis_detail
                    },
                    {
                        'name': 'API代理池',
                        'status': api_status,
                        'detail': api_detail
                    },
                    {
                        'name': '系统负载',
                        'status': system_status,
                        'detail': system_detail
                    }
                ],
                'recent_activities': recent_activities
            }
        })

    except Exception as e:
        logger.error(f"获取仪表板数据异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取仪表板数据失败'
        }), 500

@questions_bp.route('/search-history', methods=['GET'])
@token_required
def get_search_history(current_user):
    """获取搜索历史"""
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        # 限制每页数量
        per_page = min(per_page, 100)

        # 获取搜索历史
        cache = get_cache()
        search_history_key = f"search_history:{current_user.id}"
        history_data = cache.get(search_history_key)

        # 确保history_data是列表类型
        if history_data is None:
            history_data = []
        elif isinstance(history_data, str):
            try:
                history_data = json.loads(history_data)
            except json.JSONDecodeError:
                history_data = []
        elif not isinstance(history_data, list):
            history_data = []

        # 分页处理
        total = len(history_data)
        start = (page - 1) * per_page
        end = start + per_page
        page_data = history_data[start:end]

        return jsonify({
            'success': True,
            'data': {
                'items': page_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            },
            'message': '获取搜索历史成功'
        })

    except Exception as e:
        logger.error(f"获取搜索历史失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取搜索历史失败: {str(e)}'
        }), 500

@questions_bp.route('/search-history', methods=['DELETE'])
@token_required
def clear_search_history(current_user):
    """清除搜索历史"""
    try:
        # 清除搜索历史
        cache = get_cache()
        search_history_key = f"search_history:{current_user.id}"
        cache.delete(search_history_key)

        # 记录日志
        logger.info(f"用户 {current_user.username} 清除了搜索历史")

        return jsonify({
            'success': True,
            'message': '搜索历史已清除'
        })

    except Exception as e:
        logger.error(f"清除搜索历史失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'清除搜索历史失败: {str(e)}'
        }), 500

@questions_bp.route('/export', methods=['GET'])
@optional_auth
def export_questions(current_user):
    """导出题库数据"""
    try:
        # 获取查询参数
        export_format = request.args.get('format', 'json').lower()
        question_type = request.args.get('type', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        favorite_only = request.args.get('favorite', '').lower() == 'true'
        limit = int(request.args.get('limit', 1000))  # 限制导出数量

        # 构建查询
        query = QARecord.query

        # 如果有用户登录，优先导出该用户的题目
        if current_user:
            query = query.filter_by(user_id=current_user.id)

        # 题型筛选
        if question_type:
            query = query.filter_by(type=question_type)

        # 难度筛选
        if difficulty:
            query = query.filter_by(difficulty=difficulty)

        # 收藏筛选
        if favorite_only:
            query = query.filter_by(is_favorite=True)

        # 限制数量并排序
        questions = query.order_by(QARecord.created_at.desc()).limit(limit).all()

        if not questions:
            return jsonify({
                'success': False,
                'message': '没有找到符合条件的题目'
            }), 404

        # 准备导出数据
        export_data = []
        for question in questions:
            export_data.append({
                'id': question.id,
                'question': question.question,
                'type': question.type,
                'options': question.options,
                'answer': question.answer,
                'difficulty': question.difficulty,
                'tags': question.tags,
                'source': question.source,
                'view_count': question.view_count or 0,
                'is_favorite': question.is_favorite or False,
                'created_at': question.created_at.isoformat() if question.created_at else None,
                'updated_at': question.updated_at.isoformat() if question.updated_at else None
            })

        # 根据格式返回数据
        if export_format == 'csv':
            import csv
            import io
            from flask import make_response

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)

            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename=questions_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

            logger.info(f"用户 {current_user.username if current_user else 'anonymous'} 导出题库CSV: {len(export_data)}条")
            return response

        else:  # JSON格式
            logger.info(f"用户 {current_user.username if current_user else 'anonymous'} 导出题库JSON: {len(export_data)}条")

            return jsonify({
                'success': True,
                'message': f'成功导出 {len(export_data)} 道题目',
                'data': {
                    'questions': export_data,
                    'count': len(export_data),
                    'export_time': datetime.now().isoformat(),
                    'format': export_format
                }
            })

    except Exception as e:
        logger.error(f"导出题库异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '导出失败，请稍后重试'
        }), 500


