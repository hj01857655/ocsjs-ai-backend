#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制设置MySQL连接的启动脚本
"""

import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """主启动函数"""
    print("🚀 强制MySQL连接启动脚本...")
    
    # 检查环境变量
    port = os.environ.get('PORT', '5000')
    mysql_url = os.environ.get('MYSQL_URL')

    print(f"📊 环境检查:")
    print(f"   PORT: {port}")
    print(f"   MYSQL_URL: {'已设置' if mysql_url else '未设置'}")
    if mysql_url:
        print(f"   MYSQL_URL值: {mysql_url[:50]}...")

    # 如果MYSQL_URL为空或者是模板变量未解析，尝试其他方法
    if not mysql_url or mysql_url.startswith('${{'):
        if not mysql_url:
            print("⚠️ MYSQL_URL未设置，尝试从Railway变量构建连接...")
        else:
            print(f"⚠️ MYSQL_URL模板变量未解析: {mysql_url}")
            print("   请确保在应用服务Variables中设置: MYSQL_URL = ${{ MySQL.MYSQL_URL }}")
            print("   尝试从单独变量构建连接...")

        # 获取Railway MySQL的各个组件
        mysql_host = os.environ.get('MYSQLHOST', 'mysql.railway.internal')
        mysql_user = os.environ.get('MYSQLUSER', 'root')
        mysql_password = os.environ.get('MYSQLPASSWORD', 'oypxmJcTSksIvFwuiIbspwNFRLNHVaAs')
        mysql_port = os.environ.get('MYSQLPORT', '3306')
        mysql_database = os.environ.get('MYSQL_DATABASE', 'railway')

        print(f"🔍 MySQL组件变量:")
        print(f"   MYSQLHOST: {mysql_host}")
        print(f"   MYSQLUSER: {mysql_user}")
        print(f"   MYSQLPORT: {mysql_port}")
        print(f"   MYSQL_DATABASE: {mysql_database}")

        # 如果单独变量也没有，使用已知的Railway MySQL连接
        if not mysql_host or mysql_host == 'mysql.railway.internal':
            print("🔧 使用已知的Railway MySQL连接信息...")
            mysql_url = "mysql://root:oypxmJcTSksIvFwuiIbspwNFRLNHVaAs@mysql.railway.internal:3306/railway"
        else:
            # 构建连接字符串
            mysql_url = f"mysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"

        os.environ['MYSQL_URL'] = mysql_url
        print(f"✅ 已设置MYSQL_URL: {mysql_url[:50]}...")
    
    try:
        # 导入配置
        from load_config import Config
        print("✅ 配置导入成功")
        
        # 显示数据库配置
        print(f"🔗 数据库配置:")
        print(f"   URI: {Config.SQLALCHEMY_DATABASE_URI[:80]}...")
        print(f"   HOST: {getattr(Config, 'DB_HOST', 'None')}")
        
        # 创建Flask应用
        from flask import Flask
        app = Flask(__name__)
        app.config.from_object(Config)
        
        # 基本路由
        @app.route('/')
        def home():
            return {'status': 'ok', 'message': 'EduBrain AI运行中'}
        
        @app.route('/health')
        def health():
            return {'status': 'healthy'}
        
        # 尝试导入完整应用
        try:
            from app import create_app
            app = create_app()
            print("✅ 完整应用创建成功")
        except Exception as e:
            print(f"⚠️ 完整应用失败，使用基础版本: {e}")
        
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
