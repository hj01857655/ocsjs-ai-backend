#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库配置测试脚本
用于验证 Railway 环境变量配置是否正确
"""

import os
import sys

def test_database_config():
    """测试数据库配置"""
    print("=" * 60)
    print("🔍 数据库配置测试")
    print("=" * 60)
    
    # 检测环境
    is_railway = bool(
        os.environ.get('RAILWAY_PROJECT_ID') or 
        os.environ.get('RAILWAY_ENVIRONMENT_ID') or
        os.environ.get('RAILWAY_SERVICE_ID')
    )
    
    print(f"🌍 运行环境: {'Railway' if is_railway else '本地'}")
    
    if is_railway:
        print(f"📋 项目名称: {os.environ.get('RAILWAY_PROJECT_NAME', 'Unknown')}")
        print(f"📋 环境名称: {os.environ.get('RAILWAY_ENVIRONMENT_NAME', 'Unknown')}")
        print(f"📋 服务名称: {os.environ.get('RAILWAY_SERVICE_NAME', 'Unknown')}")
        print(f"🌐 TCP代理: {os.environ.get('RAILWAY_TCP_PROXY_DOMAIN', 'Unknown')}:{os.environ.get('RAILWAY_TCP_PROXY_PORT', 'Unknown')}")
    
    print("\n" + "=" * 60)
    print("🔗 数据库连接配置")
    print("=" * 60)
    
    # 检查数据库环境变量
    db_vars = {
        'DATABASE_URL': os.environ.get('DATABASE_URL'),
        'MYSQL_URL': os.environ.get('MYSQL_URL'),
        'MYSQL_PUBLIC_URL': os.environ.get('MYSQL_PUBLIC_URL'),
        'MYSQL_DATABASE': os.environ.get('MYSQL_DATABASE'),
        'MYSQLUSER': os.environ.get('MYSQLUSER'),
        'MYSQL_ROOT_PASSWORD': os.environ.get('MYSQL_ROOT_PASSWORD'),
        'MYSQLHOST': os.environ.get('MYSQLHOST'),
        'MYSQLPORT': os.environ.get('MYSQLPORT'),
    }
    
    for key, value in db_vars.items():
        if value:
            if 'PASSWORD' in key:
                # 隐藏密码
                display_value = value[:8] + '***' if len(value) > 8 else '***'
            elif 'URL' in key and '@' in str(value):
                # 隐藏URL中的密码
                parts = value.split('@')
                if len(parts) == 2:
                    user_pass = parts[0].split('//')[-1]
                    if ':' in user_pass:
                        user, _ = user_pass.split(':', 1)
                        display_value = f"{parts[0].split('//')[0]}//{user}:***@{parts[1]}"
                    else:
                        display_value = value
                else:
                    display_value = value
            else:
                display_value = value
            
            print(f"✅ {key}: {display_value}")
        else:
            print(f"❌ {key}: 未设置")
    
    print("\n" + "=" * 60)
    print("🎯 连接策略分析")
    print("=" * 60)
    
    # 分析连接策略
    if db_vars['DATABASE_URL'] or db_vars['MYSQL_URL']:
        primary_url = db_vars['DATABASE_URL'] or db_vars['MYSQL_URL']
        print(f"🚀 策略1: 使用完整连接URL")
        print(f"   URL: {primary_url.split('@')[1] if '@' in primary_url else primary_url}")
        
    elif (db_vars['MYSQLUSER'] and db_vars['MYSQL_ROOT_PASSWORD'] and 
          db_vars['MYSQLHOST'] and db_vars['MYSQL_DATABASE']):
        print(f"🔧 策略2: 使用独立环境变量")
        print(f"   连接: {db_vars['MYSQLUSER']}@{db_vars['MYSQLHOST']}:{db_vars['MYSQLPORT']}/{db_vars['MYSQL_DATABASE']}")
        
    elif is_railway and os.environ.get('RAILWAY_TCP_PROXY_DOMAIN'):
        print(f"🌐 策略3: 使用 Railway 原生变量")
        print(f"   连接: root@{os.environ.get('RAILWAY_TCP_PROXY_DOMAIN')}:{os.environ.get('RAILWAY_TCP_PROXY_PORT')}/railway")
        
    else:
        print(f"🏠 策略4: 使用本地配置文件")
        print(f"   连接: localhost:3306/ocs_qa")
    
    print("\n" + "=" * 60)
    print("✅ 配置测试完成")
    print("=" * 60)

if __name__ == '__main__':
    test_database_config()
