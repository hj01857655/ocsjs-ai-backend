#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API接口测试脚本
"""
import requests
import json

BASE_URL = "https://ocsjs-ai-backend-production.up.railway.app"

def test_login():
    """测试登录接口"""
    url = f"{BASE_URL}/api/auth/login"
    data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"登录接口测试:")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                token = result['data']['token']
                print(f"✅ 登录成功，获得token: {token[:50]}...")
                return token
            else:
                print(f"❌ 登录失败: {result.get('message')}")
        else:
            print(f"❌ 登录请求失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 登录异常: {str(e)}")
    
    return None

def test_questions_search():
    """测试搜题接口"""
    url = f"{BASE_URL}/api/questions/search"
    data = {
        "question": "什么是人工智能？"
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"\n搜题接口测试:")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ 搜题接口正常")
        else:
            print(f"❌ 搜题接口失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 搜题异常: {str(e)}")

def test_db_monitor():
    """测试数据库监控接口"""
    url = f"{BASE_URL}/api/db-monitor/test-connection"
    
    try:
        response = requests.post(url, timeout=10)
        print(f"\n数据库监控测试:")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ 数据库监控接口正常")
        else:
            print(f"❌ 数据库监控失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 数据库监控异常: {str(e)}")

def test_proxy_management(token):
    """测试代理管理接口"""
    if not token:
        print("\n❌ 无token，跳过代理管理测试")
        return
        
    url = f"{BASE_URL}/api/api-proxy-management/list"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"\n代理管理测试:")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ 代理管理接口正常")
        else:
            print(f"❌ 代理管理失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 代理管理异常: {str(e)}")

if __name__ == "__main__":
    print("🧪 开始API接口测试...")
    
    # 测试登录并获取token
    token = test_login()
    
    # 测试其他接口
    test_questions_search()
    test_db_monitor()
    test_proxy_management(token)
    
    print("\n🏁 测试完成")
