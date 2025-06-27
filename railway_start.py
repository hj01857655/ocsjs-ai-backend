#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Railway专用启动脚本
简化启动流程，确保在Railway环境中能够正常启动
"""

import os
import sys
import time

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """主启动函数"""
    print("🚀 Railway启动脚本开始...")
    
    # 检查关键环境变量
    port = os.environ.get('PORT', '5000')
    mysql_url = os.environ.get('MYSQL_URL')
    
    print(f"📊 环境信息:")
    print(f"   PORT: {port}")
    print(f"   MYSQL_URL: {'已设置' if mysql_url else '未设置'}")
    if mysql_url:
        print(f"   MYSQL_URL前50字符: {mysql_url[:50]}...")
    print(f"   Python版本: {sys.version}")
    print(f"   工作目录: {os.getcwd()}")

    # 显示数据库相关的环境变量
    print(f"🔍 数据库相关环境变量:")
    for key in sorted(os.environ.keys()):
        if any(keyword in key.upper() for keyword in ['MYSQL', 'DATABASE', 'DB_']):
            value = os.environ[key]
            print(f"   {key}: {value[:50]}..." if len(value) > 50 else f"   {key}: {value}")
    
    try:
        # 导入Flask应用
        print("📦 导入应用模块...")
        from load_config import Config
        print("✅ 配置模块导入成功")
        
        from flask import Flask
        print("✅ Flask导入成功")
        
        # 创建最小化的Flask应用
        app = Flask(__name__)
        app.config.from_object(Config)
        
        # 添加基本路由
        @app.route('/')
        def home():
            return {
                'status': 'ok',
                'message': 'EduBrain AI服务运行中',
                'version': '1.0.0'
            }
        
        @app.route('/health')
        def health():
            return {
                'status': 'healthy',
                'timestamp': int(time.time())
            }
        
        print("✅ 基本路由设置完成")
        
        # 尝试导入完整应用
        try:
            print("📦 导入完整应用...")
            from app import create_app
            app = create_app()
            print("✅ 完整应用创建成功")
        except Exception as e:
            print(f"⚠️ 完整应用导入失败，使用简化版本: {e}")
        
        # 启动应用
        print(f"🌐 启动应用在端口 {port}...")
        app.run(
            host='0.0.0.0',
            port=int(port),
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
