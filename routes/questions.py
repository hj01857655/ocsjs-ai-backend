# -*- coding: utf-8 -*-
"""
问答系统核心API - 精简版，只保留必要功能
"""
from flask import Blueprint, request, jsonify
from datetime import datetime

from models.models import db, QARecord, User
from utils.auth import token_required, optional_auth
from utils.logger import get_logger
from utils.response_handler import success_response, error_response, handle_exception
from services.search_service import get_search_service

questions_bp = Blueprint('questions', __name__)
logger = get_logger(__name__)

@questions_bp.route('/search', methods=['POST'])
@optional_auth
def search_question(current_user):
    """搜题接口 - 核心功能"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据格式错误', status_code=400)

        question = data.get('question', '').strip()
        if not question:
            return error_response('问题内容不能为空', status_code=400)

        # 获取搜索服务
        search_service = get_search_service()
        
        # 执行搜索
        result = search_service.search_question(question)
        
        if result and result.get('success'):
            # 记录搜索历史（如果用户已登录）
            if current_user:
                try:
                    qa_record = QARecord(
                        question=question,
                        answer=result.get('answer', ''),
                        type=result.get('type', 'unknown'),
                        source='search',
                        user_id=current_user.id,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(qa_record)
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"保存搜索记录失败: {str(e)}")
            
            return success_response(
                data=result,
                message='搜索完成'
            )
        else:
            return error_response('未找到相关答案', status_code=404)

    except Exception as e:
        logger.error(f"搜题异常: {str(e)}")
        return handle_exception(e, context={'question': question if 'question' in locals() else 'unknown'})

@questions_bp.route('/history', methods=['GET'])
@token_required
def get_search_history(current_user):
    """获取搜索历史 - 核心功能"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        
        # 查询用户的搜索历史
        pagination = QARecord.query.filter_by(user_id=current_user.id)\
            .order_by(QARecord.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        history_data = []
        for record in pagination.items:
            history_data.append({
                'id': record.id,
                'question': record.question,
                'answer': record.answer,
                'type': record.type,
                'source': record.source,
                'created_at': record.created_at.isoformat() if record.created_at else None
            })
        
        return success_response(
            data={
                'history': history_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            },
            message='获取搜索历史成功'
        )

    except Exception as e:
        logger.error(f"获取搜索历史异常: {str(e)}")
        return handle_exception(e, context={'user_id': current_user.id})

@questions_bp.route('/favorite', methods=['POST'])
@token_required
def toggle_favorite(current_user):
    """收藏/取消收藏 - 核心功能"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据格式错误', status_code=400)

        question_id = data.get('question_id')
        if not question_id:
            return error_response('缺少题目ID', status_code=400)

        # 查找题目
        question = QARecord.query.get(question_id)
        if not question:
            return error_response('题目不存在', status_code=404)

        # 检查权限
        if question.user_id != current_user.id:
            return error_response('无权限操作此题目', status_code=403)

        # 切换收藏状态
        question.is_favorite = not question.is_favorite
        db.session.commit()

        action = '收藏' if question.is_favorite else '取消收藏'
        logger.info(f"用户 {current_user.username} {action}题目: {question_id}")

        return success_response(
            data={'is_favorite': question.is_favorite},
            message=f'{action}成功'
        )

    except Exception as e:
        logger.error(f"收藏操作异常: {str(e)}")
        return handle_exception(e, context={'user_id': current_user.id})

@questions_bp.route('/delete', methods=['DELETE'])
@token_required
def delete_question(current_user):
    """删除题目 - 核心功能"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据格式错误', status_code=400)

        question_id = data.get('question_id')
        if not question_id:
            return error_response('缺少题目ID', status_code=400)

        # 查找题目
        question = QARecord.query.get(question_id)
        if not question:
            return error_response('题目不存在', status_code=404)

        # 检查权限
        if question.user_id != current_user.id:
            return error_response('无权限删除此题目', status_code=403)

        # 删除题目
        db.session.delete(question)
        db.session.commit()

        logger.info(f"用户 {current_user.username} 删除题目: {question_id}")

        return success_response(message='删除成功')

    except Exception as e:
        logger.error(f"删除题目异常: {str(e)}")
        return handle_exception(e, context={'user_id': current_user.id})

@questions_bp.route('/clear-history', methods=['POST'])
@token_required
def clear_search_history(current_user):
    """清除搜索历史 - 核心功能"""
    try:
        # 删除用户的所有搜索记录
        deleted_count = QARecord.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        logger.info(f"用户 {current_user.username} 清除搜索历史: {deleted_count}条")

        return success_response(
            data={'deleted_count': deleted_count},
            message='搜索历史已清除'
        )

    except Exception as e:
        logger.error(f"清除搜索历史异常: {str(e)}")
        return handle_exception(e, context={'user_id': current_user.id})

# 已删除的功能（非核心）：
# - 批量搜索 (batch-search)
# - 统计信息 (statistics) 
# - 仪表板数据 (dashboard)
# - 导出功能 (export)
# - 复杂的筛选和排序
# - 标签管理
# - 题目分类统计
