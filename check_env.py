#!/usr/bin/env python3
"""
检查Railway环境变量的脚本
"""
import os

print("🔍 Railway环境变量检查")
print("=" * 50)

# 检查关键环境变量
key_vars = ['PORT', 'MYSQL_URL', 'RAILWAY_ENVIRONMENT']

for var in key_vars:
    value = os.environ.get(var)
    if value:
        # 对于敏感信息，只显示前后几个字符
        if 'URL' in var and len(value) > 20:
            masked = value[:10] + "..." + value[-10:]
            print(f"✅ {var}: {masked}")
        else:
            print(f"✅ {var}: {value}")
    else:
        print(f"❌ {var}: 未设置")

print("\n🔍 所有包含数据库关键词的环境变量:")
for key in sorted(os.environ.keys()):
    if any(keyword in key.upper() for keyword in ['MYSQL', 'DATABASE', 'DB']):
        value = os.environ[key]
        if len(value) > 50:
            print(f"   {key}: {value[:25]}...{value[-15:]}")
        else:
            print(f"   {key}: {value}")

print(f"\n📊 总共有 {len(os.environ)} 个环境变量")
