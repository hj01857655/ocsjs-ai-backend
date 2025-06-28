#!/usr/bin/env python3
"""
批量移除表管理接口的认证要求
"""
import re

def remove_auth_from_file(file_path):
    """移除文件中的认证装饰器和current_user参数"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除 @token_required 装饰器
    content = re.sub(r'@token_required\n', '', content)
    
    # 移除函数参数中的 current_user
    content = re.sub(r'def (\w+)\(current_user(, )?([^)]*)\):', r'def \1(\3):', content)
    content = re.sub(r'def (\w+)\(current_user\):', r'def \1():', content)
    
    # 移除 current_user 相关的日志和错误处理
    content = re.sub(r'current_user\.id if current_user else None', 'None', content)
    content = re.sub(r'current_user\.username', '"anonymous"', content)
    content = re.sub(r'getattr\(current_user, \'is_admin\', False\)', 'True', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"已处理文件: {file_path}")

if __name__ == '__main__':
    remove_auth_from_file('routes/table_management.py')
    print("认证移除完成！")
