# -*- coding: utf-8 -*-
"""
数据库模型定义 - Flask-SQLAlchemy版本
"""
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

# 创建SQLAlchemy实例
db = SQLAlchemy()

def init_db(app):
    """初始化数据库"""
    db.init_app(app)

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 创建默认管理员用户
        create_default_admin()

def create_default_admin():
    """创建默认管理员用户"""
    try:
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                email='admin@example.com',
                is_admin=True,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("默认管理员用户已创建: admin/admin123")
    except Exception as e:
        print(f"创建默认管理员失败: {str(e)}")
        print("这可能是因为数据库表结构不匹配，将重新创建表...")
        try:
            # 删除所有表并重新创建
            db.drop_all()
            db.create_all()
            # 重新创建管理员
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                email='admin@example.com',
                is_admin=True,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("数据库表重新创建完成，默认管理员用户已创建: admin/admin123")
        except Exception as e2:
            print(f"重新创建数据库表也失败: {str(e2)}")
            print("请检查数据库连接和权限")

# 问答记录模型
class QARecord(db.Model):
    __tablename__ = 'qa_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.Text, nullable=False, comment='问题内容')
    type = db.Column(db.String(20), nullable=True, comment='问题类型', index=True)
    options = db.Column(db.Text, nullable=True, comment='选项内容')
    answer = db.Column(db.Text, nullable=True, comment='回答内容')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间', index=True)

    # 新增字段用于搜索优化
    question_length = db.Column(db.Integer, default=0, comment='题目长度')
    is_favorite = db.Column(db.Boolean, default=False, comment='收藏状态', index=True)
    view_count = db.Column(db.Integer, default=0, comment='查看次数')
    last_viewed = db.Column(db.DateTime, nullable=True, comment='最后查看时间')
    difficulty = db.Column(db.String(10), default='medium', comment='难度等级', index=True)  # easy, medium, hard
    tags = db.Column(db.Text, nullable=True, comment='标签，用逗号分隔')
    source = db.Column(db.String(100), nullable=True, comment='题目来源')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 用户关联
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='创建用户ID')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'question': self.question,
            'type': self.type,
            'options': self.options,
            'answer': self.answer,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'question_length': self.question_length or 0,
            'is_favorite': self.is_favorite or False,
            'view_count': self.view_count or 0,
            'last_viewed': self.last_viewed.isoformat() if self.last_viewed else None,
            'difficulty': self.difficulty or 'medium',
            'tags': self.tags.split(',') if self.tags else [],
            'source': self.source,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id
        }

# 用户模型
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希值')
    email = db.Column(db.String(100), unique=True, nullable=True, comment='邮箱')
    phone = db.Column(db.String(20), nullable=True, comment='手机号')
    real_name = db.Column(db.String(50), nullable=True, comment='真实姓名')
    bio = db.Column(db.Text, nullable=True, comment='个人简介')
    avatar = db.Column(db.String(255), nullable=True, comment='头像URL')
    role = db.Column(db.String(20), default='user', comment='用户角色')
    is_admin = db.Column(db.Boolean, default=False, comment='是否管理员')
    is_active = db.Column(db.Boolean, default=True, comment='是否激活')
    last_login = db.Column(db.DateTime, nullable=True, comment='最后登录时间')
    login_count = db.Column(db.Integer, default=0, comment='登录次数')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    # 偏好设置
    preferences = db.Column(db.Text, nullable=True, comment='用户偏好设置JSON')

    # 关联关系
    qa_records = db.relationship('QARecord', backref='user', lazy='dynamic')
    sessions = db.relationship('UserSession', backref='user', lazy='dynamic')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'real_name': self.real_name,
            'bio': self.bio,
            'avatar': self.avatar,
            'role': self.role,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count or 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# 用户会话模型
class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    session_id = db.Column(db.String(64), unique=True, nullable=False, comment='会话ID')
    ip_address = db.Column(db.String(50), nullable=True, comment='IP地址')
    user_agent = db.Column(db.String(500), nullable=True, comment='用户代理')
    device_info = db.Column(db.String(200), nullable=True, comment='设备信息')
    location = db.Column(db.String(100), nullable=True, comment='登录地点')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    expires_at = db.Column(db.DateTime, nullable=False, comment='过期时间')
    last_active = db.Column(db.DateTime, default=datetime.utcnow, comment='最后活跃时间')
    is_active = db.Column(db.Boolean, default=True, comment='是否活跃')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'device_info': self.device_info,
            'location': self.location,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'is_active': self.is_active
        }

# 系统日志模型
class SystemLog(db.Model):
    __tablename__ = 'system_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level = db.Column(db.String(10), nullable=False, comment='日志级别', index=True)
    source = db.Column(db.String(50), nullable=False, comment='日志来源', index=True)
    message = db.Column(db.Text, nullable=False, comment='日志消息')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='用户ID')
    ip_address = db.Column(db.String(50), nullable=True, comment='IP地址')
    request_id = db.Column(db.String(64), nullable=True, comment='请求ID')
    stack_trace = db.Column(db.Text, nullable=True, comment='堆栈跟踪')
    context = db.Column(db.Text, nullable=True, comment='上下文信息JSON')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间', index=True)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'level': self.level,
            'source': self.source,
            'message': self.message,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'request_id': self.request_id,
            'stack_trace': self.stack_trace,
            'context': self.context,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# 代理池模型
class ProxyPool(db.Model):
    __tablename__ = 'proxy_pool'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    host = db.Column(db.String(100), nullable=False, comment='代理主机')
    port = db.Column(db.Integer, nullable=False, comment='代理端口')
    type = db.Column(db.String(20), nullable=False, comment='代理类型')  # http, https, socks4, socks5
    username = db.Column(db.String(100), nullable=True, comment='用户名')
    password = db.Column(db.String(100), nullable=True, comment='密码')
    location = db.Column(db.String(100), nullable=True, comment='地理位置')
    status = db.Column(db.String(20), default='active', comment='状态')  # active, inactive, testing
    response_time = db.Column(db.Integer, nullable=True, comment='响应时间(ms)')
    success_rate = db.Column(db.Float, default=0.0, comment='成功率')
    usage_count = db.Column(db.Integer, default=0, comment='使用次数')
    last_used = db.Column(db.DateTime, nullable=True, comment='最后使用时间')
    last_tested = db.Column(db.DateTime, nullable=True, comment='最后测试时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'host': self.host,
            'port': self.port,
            'type': self.type,
            'username': self.username,
            'location': self.location,
            'status': self.status,
            'response_time': self.response_time,
            'success_rate': self.success_rate,
            'usage_count': self.usage_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'last_tested': self.last_tested.isoformat() if self.last_tested else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# 系统配置模型
class SystemConfig(db.Model):
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(100), unique=True, nullable=False, comment='配置键')
    value = db.Column(db.Text, nullable=True, comment='配置值')
    description = db.Column(db.String(255), nullable=True, comment='配置描述')
    type = db.Column(db.String(20), default='string', comment='配置类型')  # string, int, float, bool, json
    is_public = db.Column(db.Boolean, default=False, comment='是否公开')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'type': self.type,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
