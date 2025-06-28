# -*- coding: utf-8 -*-
"""
认证相关路由
"""
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import jwt
import uuid

from models.models import db, User, UserSession
from utils.auth import token_required, admin_required
from utils.logger import get_logger

# 尝试导入日志模块，如果失败则使用简化版本
try:
    from routes.logs import add_system_log
except ImportError:
    def add_system_log(level='info', source='system', message='', user_id=None, ip_address=None, context=None):
        """简化的日志记录函数"""
        logger = get_logger(__name__)
        log_message = f"[{source.upper()}] {message}"
        if user_id:
            log_message += f" | User: {user_id}"
        if ip_address:
            log_message += f" | IP: {ip_address}"
        if context:
            log_message += f" | Context: {context}"

        if level == 'error':
            logger.error(log_message)
        elif level == 'warn':
            logger.warning(log_message)
        else:
            logger.info(log_message)

auth_bp = Blueprint('auth', __name__)
logger = get_logger(__name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)

        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400

        # 查找用户
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            # 记录登录失败日志
            add_system_log(
                level='warn',
                source='auth',
                message=f'用户登录失败: {username} - 用户名或密码错误',
                ip_address=request.remote_addr
            )
            logger.warning(f"登录失败: {username} - {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': '用户名或密码错误'
            }), 401

        # 检查用户状态
        if not user.is_active:
            return jsonify({
                'success': False,
                'message': '账户已被禁用'
            }), 403

        # 生成JWT token
        payload = {
            'user_id': user.id,
            'username': user.username,
            'is_admin': user.is_admin,
            'exp': datetime.utcnow() + timedelta(days=30 if remember else 1),
            'iat': datetime.utcnow(),
            'jti': str(uuid.uuid4())
        }

        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )

        # 创建用户会话
        session_record = UserSession(
            user_id=user.id,
            session_id=payload['jti'],
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            expires_at=payload['exp']
        )
        db.session.add(session_record)

        # 更新用户最后登录时间
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1

        db.session.commit()

        # 记录系统日志
        add_system_log(
            level='info',
            source='auth',
            message=f'用户登录成功: {username}',
            user_id=user.id,
            ip_address=request.remote_addr,
            request_id=session_record.session_id
        )

        logger.info(f"用户登录成功: {username} - {request.remote_addr}")

        return jsonify({
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_admin': user.is_admin,
                    'avatar': user.avatar,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            }
        })

    except Exception as e:
        logger.error(f"登录异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '登录失败，请稍后重试'
        }), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip()

        # 验证输入
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400

        if len(username) < 3:
            return jsonify({
                'success': False,
                'message': '用户名长度不能少于3个字符'
            }), 400

        if len(password) < 6:
            return jsonify({
                'success': False,
                'message': '密码长度不能少于6个字符'
            }), 400

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'message': '用户名已存在'
            }), 409

        # 检查邮箱是否已存在
        if email and User.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'message': '邮箱已被注册'
            }), 409

        # 创建新用户
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email if email else None,
            is_admin=False,
            is_active=True,
            created_at=datetime.utcnow()
        )

        db.session.add(user)
        db.session.commit()

        # 记录系统日志
        add_system_log(
            level='info',
            source='auth',
            message=f'用户注册成功: {username}',
            user_id=user.id,
            ip_address=request.remote_addr
        )

        logger.info(f"用户注册成功: {username} - {request.remote_addr}")

        return jsonify({
            'success': True,
            'message': '注册成功',
            'data': {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"注册异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '注册失败，请稍后重试'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """用户登出"""
    try:
        # 获取当前会话ID
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(
                    token,
                    current_app.config['SECRET_KEY'],
                    algorithms=['HS256']
                )
                session_id = payload.get('jti')

                # 删除会话记录
                if session_id:
                    UserSession.query.filter_by(session_id=session_id).delete()
                    db.session.commit()

            except jwt.InvalidTokenError:
                pass

        logger.info(f"用户登出: {current_user.username} - {request.remote_addr}")

        return jsonify({
            'success': True,
            'message': '登出成功'
        })

    except Exception as e:
        logger.error(f"登出异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '登出失败'
        }), 500

@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """获取用户信息"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'email': current_user.email,
                    'is_admin': current_user.is_admin,
                    'avatar': current_user.avatar,
                    'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
                    'last_login': current_user.last_login.isoformat() if current_user.last_login else None,
                    'login_count': current_user.login_count or 0
                }
            }
        })

    except Exception as e:
        logger.error(f"获取用户信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取用户信息失败'
        }), 500

@auth_bp.route('/user', methods=['GET'])
@token_required
def get_user_info(current_user):
    """获取用户信息 (别名路由)"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'id': current_user.id,
                'username': current_user.username,
                'email': current_user.email,
                'role': 'admin' if current_user.is_admin else 'user',
                'is_admin': current_user.is_admin,
                'avatar': current_user.avatar,
                'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
                'last_login': current_user.last_login.isoformat() if current_user.last_login else None,
                'login_count': current_user.login_count or 0,
                'permissions': ['admin'] if current_user.is_admin else ['user']
            }
        })

    except Exception as e:
        logger.error(f"获取用户信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '获取用户信息失败'
        }), 500

@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """更新用户信息"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        # 更新允许的字段
        if 'email' in data:
            email = data['email'].strip()
            if email and User.query.filter(User.email == email, User.id != current_user.id).first():
                return jsonify({
                    'success': False,
                    'message': '邮箱已被其他用户使用'
                }), 409
            current_user.email = email if email else None

        if 'avatar' in data:
            current_user.avatar = data['avatar']

        current_user.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"用户信息更新: {current_user.username}")

        return jsonify({
            'success': True,
            'message': '用户信息更新成功',
            'data': {
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'email': current_user.email,
                    'avatar': current_user.avatar
                }
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"更新用户信息异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '更新用户信息失败'
        }), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """修改密码"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400

        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')

        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'message': '当前密码和新密码不能为空'
            }), 400

        # 验证当前密码
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({
                'success': False,
                'message': '当前密码错误'
            }), 400

        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': '新密码长度不能少于6个字符'
            }), 400

        # 更新密码
        current_user.password_hash = generate_password_hash(new_password)
        current_user.updated_at = datetime.utcnow()
        db.session.commit()

        logger.info(f"密码修改成功: {current_user.username}")

        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"修改密码异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '修改密码失败'
        }), 500

@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """验证token有效性"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'message': 'Token格式错误'
            }), 401

        token = auth_header.split(' ')[1]

        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )

            user_id = payload.get('user_id')
            session_id = payload.get('jti')

            # 检查用户是否存在
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({
                    'success': False,
                    'message': 'Token无效'
                }), 401

            # 检查会话是否存在
            session_record = UserSession.query.filter_by(session_id=session_id).first()
            if not session_record or session_record.expires_at < datetime.utcnow():
                return jsonify({
                    'success': False,
                    'message': 'Token已过期'
                }), 401

            return jsonify({
                'success': True,
                'message': 'Token有效',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'is_admin': user.is_admin
                    }
                }
            })

        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Token已过期'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Token无效'
            }), 401

    except Exception as e:
        logger.error(f"验证Token异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '验证失败'
        }), 500
