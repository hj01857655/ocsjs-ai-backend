#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 https://new.crond.dev API 端点
"""
import requests
import json
import time
import sys
import os
import urllib3
import concurrent.futures
from typing import Dict, Tuple

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API基础URL
API_BASE = "https://new.crond.dev"

# 测试API密钥 (需要替换为实际的API密钥)
API_KEY = "sk-X97KBeoGxSSb1nk6ZlvQLTDNIreXF63PSWhiXYahdJzX4aQW"

# 要测试的模型列表
TEST_MODELS = [
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "claude-3-sonnet",
    "claude-3-haiku",
    "gemini-1.5-pro",
    "gemini-pro",
    "mistral-large",
    "mistral-medium",
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    "glm-4"
]

# 测试配置
MAX_WORKERS = 20  # 并行测试的最大线程数
CONNECT_TIMEOUT = 5  # 连接超时时间（秒）
READ_TIMEOUT = 10  # 读取超时时间（秒）
MAX_RETRIES = 1  # 最大重试次数

def test_models_endpoint():
    """测试 /v1/models 端点"""
    print("\n===== 测试 /v1/models 端点 =====")
    
    url = f"{API_BASE}/v1/models"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            models = [model.get("id") for model in data.get("data", [])]
            print(f"可用模型 ({len(models)}):")
            for model in models:
                print(f"  - {model}")
            return models
        else:
            print(f"请求失败 (状态码: {response.status_code}):")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
                # 尝试提取错误信息
                if "error" in error_data:
                    error_msg = error_data["error"].get("message", "未知错误")
                    print(f"错误信息: {error_msg}")
            except:
                print(f"响应内容: {response.text}")
            return []
    except Exception as e:
        print(f"请求异常: {str(e)}")
        return []

def test_chat_completion(model: str) -> Tuple[str, bool, Dict]:
    result_data = {
        "model": model,
        "success": False,
        "status_code": None,
        "response_time": 0,
        "error": None,
        "content": None,
        "tokens": None
    }
    
    url = f"{API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "简短回复"},
            {"role": "user", "content": "测试"}
        ],
        "temperature": 0.3,
        "max_tokens": 20
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, verify=False, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        elapsed = time.time() - start_time
        
        result_data["status_code"] = response.status_code
        result_data["response_time"] = round(elapsed, 2)
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            result_data["success"] = True
            result_data["content"] = content
            result_data["tokens"] = result.get("usage")
            
            return model, True, result_data
        else:
            try:
                error_data = response.json()
                if "error" in error_data:
                    result_data["error"] = error_data["error"].get("message", "未知错误")
            except:
                result_data["error"] = f"HTTP {response.status_code}"
            
            return model, False, result_data
    except Exception as e:
        result_data["error"] = str(e)
        return model, False, result_data

def print_test_result(result: Tuple[str, bool, Dict]):
    """打印单个测试结果"""
    model, success, data = result
    
    if success:
        print(f"\n✅ 模型: {model} - 成功 ({data['response_time']}秒)")
        if data.get("content"):
            print(f"   回复: {data['content']}")
        if data.get("tokens"):
            tokens = data["tokens"]
            print(f"   Token: 输入={tokens.get('prompt_tokens', 0)}, 输出={tokens.get('completion_tokens', 0)}, 总计={tokens.get('total_tokens', 0)}")
    else:
        print(f"\n❌ 模型: {model} - 失败 ({data.get('status_code', 'N/A')})")
        print(f"   错误: {data.get('error', '未知错误')}")

def main():
    """主函数"""
    print("开始快速测试 https://new.crond.dev API...")
    
    # 检查API密钥是否已设置
    global API_KEY
    if API_KEY == "your_api_key_here":
        # 尝试从环境变量或命令行参数获取
        API_KEY = os.environ.get("CROND_API_KEY", "")
        if not API_KEY and len(sys.argv) > 1:
            API_KEY = sys.argv[1]
        
        if not API_KEY:
            print("错误: 请提供API密钥。可以通过以下方式设置:")
            print("1. 直接在脚本中设置 API_KEY 变量")
            print("2. 设置环境变量 CROND_API_KEY")
            print("3. 作为命令行参数传递")
            print("\n使用方法: python test_crond_api.py YOUR_API_KEY")
            return
    
    # 测试 /v1/models 端点
    start_time = time.time()
    available_models = test_models_endpoint()
    
    # 确定要测试的模型列表
    if available_models:
        print("\n使用从API获取的模型列表进行测试")
        test_models = available_models
    else:
        print("\n从API获取模型列表失败，使用预定义的模型列表进行测试")
        test_models = TEST_MODELS
    
    print(f"\n开始并行测试 {len(test_models)} 个模型 (最大并行数: {MAX_WORKERS})...")
    
    # 测试结果统计
    successful_models = []
    failed_models = []
    all_results = []
    
    # 并行测试所有模型
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_model = {executor.submit(test_chat_completion, model): model for model in test_models}
        
        for future in concurrent.futures.as_completed(future_to_model):
            model = future_to_model[future]
            try:
                result = future.result()
                all_results.append(result)
                print_test_result(result)
                
                model, success, data = result
                if success:
                    successful_models.append(model)
                else:
                    failed_models.append(model)
            except Exception as e:
                print(f"\n❌ 模型: {model} - 测试异常: {str(e)}")
                failed_models.append(model)
    
    # 计算总耗时
    total_time = time.time() - start_time
    
    # 打印测试结果摘要
    print("\n===== 测试结果摘要 =====")
    print(f"总耗时: {total_time:.2f}秒")
    print(f"测试模型总数: {len(test_models)}")
    print(f"成功模型数: {len(successful_models)}")
    print(f"失败模型数: {len(failed_models)}")
    
    if successful_models:
        print("\n成功的模型:")
        for model in successful_models:
            print(f"  - {model}")
    
    if failed_models:
        print("\n失败的模型:")
        for model in failed_models:
            print(f"  - {model}")
    
    # 保存测试结果到文件
    result_file = "crond_api_test_results.json"
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "api_base": API_BASE,
                "total_time": round(total_time, 2),
                "total_models": len(test_models),
                "successful_models": successful_models,
                "failed_models": failed_models,
                "detailed_results": [result[2] for result in all_results]
            }, f, indent=2, ensure_ascii=False)
        print(f"\n测试结果已保存到: {result_file}")
    except Exception as e:
        print(f"\n保存测试结果失败: {str(e)}")

if __name__ == "__main__":
    main() 