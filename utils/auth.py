# -*- coding: utf-8 -*-
"""
认证工具类
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app

from models.models import db, User, UserSession

def init_auth(app):
    """初始化认证系统"""
    pass

def token_required(f):
    """Token验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从请求头获取token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'success': False,
                'message': '缺少认证token'
            }), 401
        
        try:
            # 解码token
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            
            user_id = payload.get('user_id')
            session_id = payload.get('jti')
            
            # 检查用户是否存在
            current_user = User.query.get(user_id)
            if not current_user or not current_user.is_active:
                return jsonify({
                    'success': False,
                    'message': 'Token无效'
                }), 401
            
            # 检查会话是否存在且有效
            session_record = UserSession.query.filter_by(session_id=session_id).first()
            if not session_record or session_record.expires_at < datetime.utcnow():
                return jsonify({
                    'success': False,
                    'message': 'Token已过期'
                }), 401
            
            # 更新最后活跃时间
            session_record.last_active = datetime.utcnow()
            db.session.commit()
            
            return f(current_user, *args, **kwargs)
            
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
            return jsonify({
                'success': False,
                'message': '认证失败'
            }), 401
    
    return decorated

def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'message': '需要管理员权限'
            }), 403
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def optional_auth(f):
    """可选认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = None
        
        # 尝试获取token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            try:
                # 解码token
                payload = jwt.decode(
                    token,
                    current_app.config['SECRET_KEY'],
                    algorithms=['HS256']
                )
                
                user_id = payload.get('user_id')
                session_id = payload.get('jti')
                
                # 检查用户是否存在
                user = User.query.get(user_id)
                if user and user.is_active:
                    # 检查会话是否存在且有效
                    session_record = UserSession.query.filter_by(session_id=session_id).first()
                    if session_record and session_record.expires_at > datetime.utcnow():
                        current_user = user
                        # 更新最后活跃时间
                        session_record.last_active = datetime.utcnow()
                        db.session.commit()
                        
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                pass
        
        return f(current_user, *args, **kwargs)
    
    return decorated

def generate_token(user, remember=False):
    """生成JWT token"""
    import uuid
    
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
    
    return token, payload

def get_current_user():
    """获取当前用户"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        
        user_id = payload.get('user_id')
        user = User.query.get(user_id)
        
        if user and user.is_active:
            return user
            
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        pass
    
    return None
