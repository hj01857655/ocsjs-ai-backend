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
    
    # 如果没有MYSQL_URL，强制设置一个
    if not mysql_url:
        print("⚠️ MYSQL_URL未设置，尝试使用Railway内部连接...")
        # 使用Railway内部MySQL连接
        mysql_url = "mysql://root:oypxmJcTSksIvFwuiIbspwNFRLNHVaAs@mysql.railway.internal:3306/railway"
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
