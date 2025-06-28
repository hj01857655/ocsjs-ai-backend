#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件创建脚本 - 用于 Railway 部署
从环境变量创建 config.json 文件
"""

import os
import json
import sys

def create_config_from_env():
    """从环境变量创建配置文件"""
    
    # 检查是否已存在配置文件
    config_file = 'config.json'
    if os.path.exists(config_file):
        print(f"配置文件已存在: {config_file}")
        return True
    
    print("配置文件不存在，尝试从环境变量创建...")
    
    # 基础配置
    config = {
        "service": {
            "host": "0.0.0.0",
            "port": int(os.environ.get('PORT', 5000)),
            "debug": os.environ.get('DEBUG', 'false').lower() == 'true'
        },
        "third_party_apis": [],
        "cache": {
            "enable": True,
            "expiration": 2592000
        },
        "security": {
            "access_token": os.environ.get('ACCESS_TOKEN'),
            "secret_key": os.environ.get('SECRET_KEY', 'edubrain-ai-secret-key-2025')
        },
        "database": {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "123456",
            "name": "ocs_qa"
        },
        "redis": {
            "enabled": True,
            "host": "localhost",
            "port": 6379,
            "password": "",
            "db": 0
        },
        "record": {
            "enable": True
        }
    }
    
    # 从环境变量添加第三方API配置
    # 格式: API_1_NAME, API_1_BASE, API_1_KEYS, API_1_MODEL, API_1_MODELS
    api_count = 0
    for i in range(1, 21):  # 支持最多20个API
        name_key = f'API_{i}_NAME'
        base_key = f'API_{i}_BASE'
        keys_key = f'API_{i}_KEYS'
        model_key = f'API_{i}_MODEL'
        models_key = f'API_{i}_MODELS'
        
        if all(key in os.environ for key in [name_key, base_key, keys_key, model_key]):
            api_config = {
                "name": os.environ[name_key],
                "api_base": os.environ[base_key],
                "api_keys": os.environ[keys_key].split(','),
                "model": os.environ[model_key],
                "models": os.environ.get(models_key, os.environ[model_key]).split(','),
                "available_models": [],
                "is_active": os.environ.get(f'API_{i}_ACTIVE', 'true').lower() == 'true',
                "priority": int(os.environ.get(f'API_{i}_PRIORITY', 1))
            }
            config["third_party_apis"].append(api_config)
            api_count += 1
            print(f"添加API配置: {api_config['name']}")
    
    if api_count == 0:
        print("警告: 没有找到任何API配置环境变量")
        # 添加一个示例配置
        config["third_party_apis"].append({
            "name": "示例API",
            "api_base": "https://api.example.com/v1",
            "api_keys": ["your-api-key-here"],
            "model": "gpt-3.5-turbo",
            "models": ["gpt-3.5-turbo"],
            "available_models": [],
            "is_active": False,
            "priority": 1
        })
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"成功创建配置文件: {config_file}")
        print(f"包含 {len(config['third_party_apis'])} 个API配置")
        return True
        
    except Exception as e:
        print(f"创建配置文件失败: {str(e)}")
        return False

if __name__ == '__main__':
    success = create_config_from_env()
    sys.exit(0 if success else 1)
