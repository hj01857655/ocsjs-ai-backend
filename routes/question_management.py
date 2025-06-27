# -*- coding: utf-8 -*-
"""
题库管理API路由 - 适配新架构
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import re

from models.models import db, QARecord
from utils.auth import token_required
from utils.logger import get_logger

question_management_bp = Blueprint('question_management', __name__)
logger = get_logger(__name__)

@question_management_bp.route('', methods=['GET'])
@token_required
def get_questions(current_user):
    """获取题目列表"""
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        size = request.args.get('size', 20, type=int)
        keyword = request.args.get('keyword', '').strip()
        question_type = request.args.get('type', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        favorite = request.args.get('favorite')

        # 构建查询
        query = QARecord.query.filter_by(user_id=current_user.id)

        # 关键词搜索
        if keyword:
            query = query.filter(
                db.or_(
                    QARecord.question.contains(keyword),
                    QARecord.answer.contains(keyword),
                    QARecord.tags.contains(keyword)
                )
            )

        # 题目类型过滤
        if question_type:
            query = query.filter_by(type=question_type)

        # 难度过滤
        if difficulty:
            query = query.filter_by(difficulty=difficulty)

        # 收藏过滤
        if favorite is not None:
            is_favorite = favorite.lower() in ['true', '1', 'yes']
            query = query.filter_by(is_favorite=is_favorite)

        # 排序
        query = query.order_by(QARecord.created_at.desc())

        # 分页
        total = query.count()
        questions = query.offset((page - 1) * size).limit(size).all()

        # 转换为字典
        questions_data = []
        for question in questions:
            question_dict = question.to_dict()
            # 处理标签
            if question_dict.get('tags'):
                question_dict['tags'] = [tag.strip() for tag in question_dict['tags'].split(',') if tag.strip()]
            else:
                question_dict['tags'] = []
            questions_data.append(question_dict)

        return jsonify({
            'success': True,
            'data': {
                'questions': questions_data,
                'total': total,
                'page': page,
                'size': size,
                'pages': (total + size - 1) // size
            }
        })

    except Exception as e:
        logger.error(f"获取题目列表异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取题目列表失败'
        }), 500

@question_management_bp.route('/add', methods=['POST'])
@token_required
def add_question(current_user):
    """在线添加单个题目"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        # 验证必填字段
        required_fields = ['question', 'type', 'answer']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400

        # 创建新题目
        new_question = QARecord(
            question=data['question'].strip(),
            type=data['type'],
            options=data.get('options', '').strip(),
            answer=data['answer'].strip(),
            difficulty=data.get('difficulty', 'medium'),
            tags=data.get('tags', ''),
            source=data.get('source', '手动添加'),
            question_length=len(data['question'].strip()),
            user_id=current_user.id,
            created_at=datetime.utcnow()
        )

        db.session.add(new_question)
        db.session.commit()

        logger.info(f"用户 {current_user.username} 添加题目: {new_question.id}")

        return jsonify({
            'success': True,
            'message': '题目添加成功',
            'data': {
                'question_id': new_question.id,
                'question': new_question.to_dict()
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"添加题目异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'添加题目失败: {str(e)}'
        }), 500

@question_management_bp.route('/<int:question_id>', methods=['PUT'])
@token_required
def update_question(current_user, question_id):
    """更新题目信息"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        question = QARecord.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'message': '题目不存在'
            }), 404

        # 检查权限（只能修改自己的题目或管理员可以修改所有）
        if question.user_id != current_user.id and not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': '无权限修改此题目'
            }), 403

        # 更新字段
        updatable_fields = ['question', 'type', 'options', 'answer', 'difficulty', 'tags', 'source']
        for field in updatable_fields:
            if field in data:
                setattr(question, field, data[field])

        # 更新题目长度
        if 'question' in data:
            question.question_length = len(data['question'].strip())

        question.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"用户 {current_user.username} 更新题目: {question_id}")

        return jsonify({
            'success': True,
            'message': '题目更新成功',
            'data': {
                'question': question.to_dict()
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"更新题目异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新题目失败: {str(e)}'
        }), 500

@question_management_bp.route('/<int:question_id>', methods=['DELETE'])
@token_required
def delete_question(current_user, question_id):
    """删除题目"""
    try:
        question = QARecord.query.get(question_id)
        if not question:
            return jsonify({
                'success': False,
                'message': '题目不存在'
            }), 404

        # 检查权限
        if question.user_id != current_user.id and not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': '无权限删除此题目'
            }), 403

        db.session.delete(question)
        db.session.commit()

        logger.info(f"用户 {current_user.username} 删除题目: {question_id}")

        return jsonify({
            'success': True,
            'message': '题目删除成功'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"删除题目异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除题目失败: {str(e)}'
        }), 500

@question_management_bp.route('/smart-import', methods=['POST'])
@token_required
def smart_import(current_user):
    """智能导入 - 支持多种格式的文本解析"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        text_content = data.get('content', '')
        if not text_content:
            return jsonify({
                'success': False,
                'message': '请提供要导入的文本内容'
            }), 400

        # 智能解析文本
        questions = parse_text_to_questions(text_content)

        if not questions:
            return jsonify({
                'success': False,
                'message': '未能从文本中解析出有效题目'
            }), 400

        # 批量导入
        imported_count = 0
        failed_count = 0

        for q_data in questions:
            try:
                new_question = QARecord(
                    question=q_data['question'],
                    type=q_data['type'],
                    options=q_data.get('options', ''),
                    answer=q_data['answer'],
                    difficulty=q_data.get('difficulty', 'medium'),
                    source='智能导入',
                    question_length=len(q_data['question']),
                    user_id=current_user.id,
                    created_at=datetime.utcnow()
                )

                db.session.add(new_question)
                imported_count += 1

            except Exception as e:
                failed_count += 1
                logger.warning(f"导入题目失败: {str(e)}")
                continue

        db.session.commit()

        logger.info(f"用户 {current_user.username} 智能导入题目: 成功{imported_count}个, 失败{failed_count}个")

        return jsonify({
            'success': True,
            'message': f'成功导入 {imported_count} 道题目',
            'data': {
                'imported_count': imported_count,
                'failed_count': failed_count,
                'total_parsed': len(questions)
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"智能导入异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'智能导入失败: {str(e)}'
        }), 500

@question_management_bp.route('/batch-delete', methods=['POST'])
@token_required
def batch_delete(current_user):
    """批量删除题目"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        question_ids = data.get('question_ids', [])
        if not question_ids:
            return jsonify({
                'success': False,
                'message': '请提供要删除的题目ID列表'
            }), 400

        deleted_count = 0
        failed_count = 0

        for question_id in question_ids:
            try:
                question = QARecord.query.get(question_id)
                if question and (question.user_id == current_user.id or current_user.is_admin):
                    db.session.delete(question)
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1

        db.session.commit()

        logger.info(f"用户 {current_user.username} 批量删除题目: 成功{deleted_count}个, 失败{failed_count}个")

        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 道题目',
            'data': {
                'deleted_count': deleted_count,
                'failed_count': failed_count
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量删除异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量删除失败: {str(e)}'
        }), 500

@question_management_bp.route('/save', methods=['POST'])
@token_required
def save_question(current_user):
    """保存搜题结果到题库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        # 验证必填字段
        required_fields = ['question', 'type', 'answer']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400

        # 检查是否已存在相同题目
        existing_question = QARecord.query.filter_by(
            question=data['question'].strip(),
            user_id=current_user.id
        ).first()

        if existing_question:
            # 更新现有题目
            existing_question.type = data['type']
            existing_question.options = data.get('options', '')
            existing_question.answer = data['answer']
            existing_question.updated_at = datetime.utcnow()
            existing_question.source = data.get('source', '搜题结果')
            
            db.session.commit()
            
            logger.info(f"用户 {current_user.username} 更新已存在题目: {existing_question.id}")
            
            return jsonify({
                'success': True,
                'message': '题目已更新',
                'data': {
                    'question_id': existing_question.id,
                    'question': existing_question.to_dict(),
                    'is_new': False
                }
            })
        else:
            # 创建新题目
            new_question = QARecord(
                question=data['question'].strip(),
                type=data['type'],
                options=data.get('options', ''),
                answer=data['answer'],
                difficulty=data.get('difficulty', 'medium'),
                tags=data.get('tags', ''),
                source=data.get('source', '搜题结果'),
                question_length=len(data['question'].strip()),
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_question)
            db.session.commit()
            
            logger.info(f"用户 {current_user.username} 保存搜题结果: {new_question.id}")
            
            return jsonify({
                'success': True,
                'message': '题目保存成功',
                'data': {
                    'question_id': new_question.id,
                    'question': new_question.to_dict(),
                    'is_new': True
                }
            })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存搜题结果异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'保存题目失败: {str(e)}'
        }), 500

@question_management_bp.route('/batch-delete', methods=['POST'])
@token_required
def batch_delete_questions(current_user):
    """批量删除题目"""
    try:
        data = request.get_json()
        if not data or 'question_ids' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        question_ids = data['question_ids']
        if not isinstance(question_ids, list) or not question_ids:
            return jsonify({
                'success': False,
                'message': '题目ID列表不能为空'
            }), 400

        # 查询要删除的题目
        questions = QARecord.query.filter(
            QARecord.id.in_(question_ids)
        ).all()

        if not questions:
            return jsonify({
                'success': False,
                'message': '未找到要删除的题目'
            }), 404

        # 检查权限（只能删除自己的题目或管理员可以删除所有）
        unauthorized_questions = []
        for question in questions:
            if question.user_id != current_user.id and not current_user.is_admin:
                unauthorized_questions.append(question.id)

        if unauthorized_questions:
            return jsonify({
                'success': False,
                'message': f'无权限删除题目: {unauthorized_questions}'
            }), 403

        # 执行删除
        deleted_count = 0
        for question in questions:
            db.session.delete(question)
            deleted_count += 1

        db.session.commit()

        logger.info(f"用户 {current_user.username} 批量删除题目: {question_ids}")

        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 道题目',
            'data': {
                'deleted_count': deleted_count,
                'deleted_ids': question_ids
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量删除题目异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '批量删除失败'
        }), 500

@question_management_bp.route('/smart-import', methods=['POST'])
@token_required
def smart_import_questions(current_user):
    """智能导入题目"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        content = data['content'].strip()
        if not content:
            return jsonify({
                'success': False,
                'message': '导入内容不能为空'
            }), 400

        # 简单的文本解析逻辑
        questions = []
        lines = content.split('\n')
        current_question = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测题目开始（以数字开头）
            if re.match(r'^\d+[\.、]', line):
                if current_question.get('question'):
                    questions.append(current_question)
                current_question = {
                    'question': re.sub(r'^\d+[\.、]\s*', '', line),
                    'type': 'single_choice',
                    'options': '',
                    'answer': '',
                    'difficulty': 'medium',
                    'tags': '',
                    'source': '智能导入'
                }
            # 检测选项
            elif re.match(r'^[A-Z][\.、]', line):
                if current_question.get('options'):
                    current_question['options'] += '\n' + line
                else:
                    current_question['options'] = line
            # 检测答案
            elif line.startswith('答案') or line.startswith('答：'):
                current_question['answer'] = re.sub(r'^(答案|答：)\s*', '', line)
            # 检测解析
            elif line.startswith('解析') or line.startswith('解：'):
                if current_question.get('answer'):
                    current_question['answer'] += '\n解析：' + re.sub(r'^(解析|解：)\s*', '', line)
                else:
                    current_question['answer'] = '解析：' + re.sub(r'^(解析|解：)\s*', '', line)
            # 其他内容追加到题目
            else:
                if current_question.get('question'):
                    current_question['question'] += ' ' + line

        # 添加最后一个题目
        if current_question.get('question'):
            questions.append(current_question)

        if not questions:
            return jsonify({
                'success': False,
                'message': '未能解析出有效题目，请检查格式'
            }), 400

        # 保存到数据库
        imported_count = 0
        skipped_count = 0

        for q_data in questions:
            if not q_data.get('question') or not q_data.get('answer'):
                skipped_count += 1
                continue

            # 检查是否已存在
            existing = QARecord.query.filter_by(
                question=q_data['question'],
                user_id=current_user.id
            ).first()

            if existing:
                skipped_count += 1
                continue

            new_question = QARecord(
                question=q_data['question'],
                type=q_data['type'],
                options=q_data['options'],
                answer=q_data['answer'],
                difficulty=q_data['difficulty'],
                tags=q_data['tags'],
                source=q_data['source'],
                question_length=len(q_data['question']),
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )

            db.session.add(new_question)
            imported_count += 1

        db.session.commit()

        logger.info(f"用户 {current_user.username} 智能导入题目: {imported_count} 道")

        return jsonify({
            'success': True,
            'message': f'导入完成！成功导入 {imported_count} 道题目，跳过 {skipped_count} 道',
            'data': {
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'total_parsed': len(questions)
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"智能导入题目异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '智能导入失败'
        }), 500

@question_management_bp.route('/statistics', methods=['GET'])
@token_required
def get_question_statistics(current_user):
    """获取题库统计信息"""
    try:
        # 基础统计
        total_questions = QARecord.query.filter_by(user_id=current_user.id).count()
        favorite_questions = QARecord.query.filter_by(user_id=current_user.id, is_favorite=True).count()

        # 按类型统计
        type_stats = db.session.query(
            QARecord.type,
            db.func.count(QARecord.id).label('count')
        ).filter_by(user_id=current_user.id).group_by(QARecord.type).all()

        # 按难度统计
        difficulty_stats = db.session.query(
            QARecord.difficulty,
            db.func.count(QARecord.id).label('count')
        ).filter_by(user_id=current_user.id).group_by(QARecord.difficulty).all()

        # 按来源统计
        source_stats = db.session.query(
            QARecord.source,
            db.func.count(QARecord.id).label('count')
        ).filter_by(user_id=current_user.id).group_by(QARecord.source).all()

        # 最近7天新增统计
        from datetime import timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_questions = QARecord.query.filter(
            QARecord.user_id == current_user.id,
            QARecord.created_at >= seven_days_ago
        ).count()

        # 热门标签统计
        tag_stats = {}
        questions_with_tags = QARecord.query.filter(
            QARecord.user_id == current_user.id,
            QARecord.tags.isnot(None),
            QARecord.tags != ''
        ).all()

        for question in questions_with_tags:
            if question.tags:
                tags = [tag.strip() for tag in question.tags.split(',') if tag.strip()]
                for tag in tags:
                    tag_stats[tag] = tag_stats.get(tag, 0) + 1

        # 转换为列表并排序
        tag_list = [{'tag': tag, 'count': count} for tag, count in tag_stats.items()]
        tag_list.sort(key=lambda x: x['count'], reverse=True)

        return jsonify({
            'success': True,
            'data': {
                'overview': {
                    'total_questions': total_questions,
                    'favorite_questions': favorite_questions,
                    'recent_questions': recent_questions,
                    'favorite_rate': round(favorite_questions / total_questions * 100, 1) if total_questions > 0 else 0
                },
                'type_distribution': [{'type': item.type or '未分类', 'count': item.count} for item in type_stats],
                'difficulty_distribution': [{'difficulty': item.difficulty or 'medium', 'count': item.count} for item in difficulty_stats],
                'source_distribution': [{'source': item.source or '未知', 'count': item.count} for item in source_stats],
                'popular_tags': tag_list[:10]  # 取前10个热门标签
            }
        })

    except Exception as e:
        logger.error(f"获取题库统计异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取统计信息失败'
        }), 500

def parse_text_to_questions(text):
    """解析文本为题目列表"""
    questions = []
    lines = text.strip().split('\n')
    current_question = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测题目开始（数字+点号+题目类型）
        question_match = re.match(r'(\d+)\.?\s*[\(（]?([^）)]*)[）)]?\s*(.*)', line)
        if question_match:
            # 保存上一题
            if current_question.get('question') and current_question.get('answer'):
                questions.append(current_question.copy())

            # 开始新题
            current_question = {
                'question': question_match.group(3),
                'type': detect_question_type(question_match.group(2)),
                'options': '',
                'answer': ''
            }

        # 检测选项（A. B. C. D.）
        elif re.match(r'^[A-Z]\.?\s+', line):
            if 'options' in current_question:
                current_question['options'] += line + '\n'

        # 检测答案（答案：或Answer:）
        elif re.match(r'(答案|Answer)[:：]\s*(.+)', line, re.IGNORECASE):
            answer_match = re.match(r'(答案|Answer)[:：]\s*(.+)', line, re.IGNORECASE)
            if answer_match:
                current_question['answer'] = answer_match.group(2).strip()

        # 其他情况，可能是题目内容的延续
        elif current_question.get('question') and not current_question.get('answer'):
            current_question['question'] += ' ' + line

    # 添加最后一题
    if current_question.get('question') and current_question.get('answer'):
        questions.append(current_question)

    return questions

def detect_question_type(type_text):
    """检测题目类型"""
    type_text = type_text.lower()

    if '单选' in type_text or 'single' in type_text:
        return 'single'
    elif '多选' in type_text or 'multiple' in type_text:
        return 'multiple'
    elif '判断' in type_text or 'true' in type_text or 'false' in type_text:
        return 'judgement'
    elif '填空' in type_text or 'blank' in type_text or 'completion' in type_text:
        return 'completion'
    else:
        return 'single'  # 默认为单选题
