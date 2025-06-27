#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Railway数据库初始化脚本
用于在Railway环境中初始化数据库表和默认数据
"""

import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_database_connection():
    """测试数据库连接"""
    try:
        from load_config import Config
        import pymysql
        
        # 解析数据库连接信息
        database_url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
        if not database_url:
            print("❌ 未找到MYSQL_URL或DATABASE_URL环境变量")
            return False
            
        print(f"🔗 数据库连接字符串: {database_url}")
        
        # 解析连接参数
        import urllib.parse as urlparse
        url = urlparse.urlparse(database_url)
        
        # 测试连接
        connection = pymysql.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=url.username,
            password=url.password,
            database=url.path[1:] if url.path else "railway",
            charset='utf8mb4',
            connect_timeout=10
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✅ 数据库连接成功! MySQL版本: {version[0]}")
            
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)}")
        return False

def init_database():
    """初始化数据库表"""
    try:
        from flask import Flask
        from load_config import Config
        from models.models import init_db
        
        # 创建Flask应用
        app = Flask(__name__)
        app.config.from_object(Config)
        
        print("🔧 开始初始化数据库表...")
        
        # 初始化数据库
        with app.app_context():
            init_db(app)
            print("✅ 数据库表初始化成功!")
            
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        return False

def main():
    """主函数"""
    print("🚀 Railway数据库初始化脚本")
    print("=" * 50)
    
    # 检查环境变量
    if not (os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')):
        print("❌ 请先在Railway控制台设置MYSQL_URL环境变量")
        print("   在Railway中设置: MYSQL_URL = ${{ MySQL.MYSQL_URL }}")
        return
    
    # 测试数据库连接
    print("1️⃣ 测试数据库连接...")
    if not test_database_connection():
        print("❌ 数据库连接测试失败，请检查连接字符串")
        return
    
    # 初始化数据库
    print("\n2️⃣ 初始化数据库表...")
    if not init_database():
        print("❌ 数据库初始化失败")
        return
    
    print("\n🎉 Railway数据库初始化完成!")
    print("现在可以正常使用应用的所有功能了。")

if __name__ == '__main__':
    main()
