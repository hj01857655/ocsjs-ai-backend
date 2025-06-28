# Railway 环境变量配置指南

系统支持环境自适应数据库配置：
- **本地开发**：使用 `config.json` 中的本地 MySQL 配置
- **Railway 部署**：使用环境变量中的 Railway MySQL 服务

## 数据库配置（必需）

系统支持多种 Railway MySQL 连接方式，按优先级排序：

### 方式1：使用完整连接URL（推荐）
Railway 自动提供以下环境变量，系统会自动检测并使用：
```
DATABASE_URL=mysql://${{MYSQLUSER}}:${{MYSQL_ROOT_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{MYSQL_DATABASE}}
MYSQL_URL=mysql://${{MYSQLUSER}}:${{MYSQL_ROOT_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{MYSQL_DATABASE}}
MYSQL_PUBLIC_URL=mysql://${{MYSQLUSER}}:${{MYSQL_ROOT_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}/${{MYSQL_DATABASE}}
```

### 方式2：使用独立环境变量
如果没有完整URL，系统会使用以下独立变量：
```
MYSQLUSER=root
MYSQL_ROOT_PASSWORD=kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk
MYSQLHOST=${{RAILWAY_PRIVATE_DOMAIN}}
MYSQLPORT=3306
MYSQL_DATABASE=railway
```

### Railway 提供的完整环境变量列表
```
# 数据库基本信息
MYSQL_DATABASE="railway"
MYSQLDATABASE="${{MYSQL_DATABASE}}"
MYSQLUSER="root"
MYSQL_ROOT_PASSWORD="kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk"
MYSQLPASSWORD="${{MYSQL_ROOT_PASSWORD}}"
MYSQLHOST="${{RAILWAY_PRIVATE_DOMAIN}}"
MYSQLPORT="3306"

# Railway 网络配置
RAILWAY_TCP_PROXY_DOMAIN="interchange.proxy.rlwy.net"
RAILWAY_TCP_PROXY_PORT="49225"

# 完整连接URL（系统会自动使用这些）
MYSQL_PUBLIC_URL="mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway"
MYSQL_URL="mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway"
DATABASE_URL="mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway"
```

### 实际连接URL
基于您提供的完整信息，Railway MySQL 的连接URL是：
```
mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway
```

## API 配置（必需）

### 基础配置
```
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN=your-access-token-here
DEBUG=false
```

### API 配置
为每个第三方API配置以下环境变量（数字从1开始）：

#### API 1 (Veloera API)
```
API_1_NAME=Veloera API
API_1_BASE=https://veloera.wei.bi
API_1_KEYS=sk-DhXIFahI8F1p9kxLC19ihpq43rcemGFE3zIWHkU0rcKT6eRX
API_1_MODEL=deepseek-ai/DeepSeek-R1
API_1_MODELS=deepseek-ai/DeepSeek-R1,gpt-4o-mini,gpt-4o
API_1_ACTIVE=true
API_1_PRIORITY=1
```

#### API 2 (Huan API)
```
API_2_NAME=Huan API
API_2_BASE=https://ai.huan666.de
API_2_KEYS=sk-Ldybvza2Ex8v95LNmRp0MfeAdO88ercCtWMyfIRK8IthXFRQ
API_2_MODEL=gpt-4o
API_2_MODELS=gpt-4o,gpt-4o-mini,deepseek-r1
API_2_ACTIVE=true
API_2_PRIORITY=1
```

#### API 3 (Super API)
```
API_3_NAME=Super API
API_3_BASE=https://api.cngov.top
API_3_KEYS=sk-hBaK17L5OZp4BWDi106rgPw1yJxp9PeGNZ6hpRfYGhX3svn6
API_3_MODEL=gpt-4.1-mini
API_3_MODELS=gpt-4.1-mini,gpt-4o-mini,deepseek-r1
API_3_ACTIVE=true
API_3_PRIORITY=1
```

#### API 4 (Noobie API)
```
API_4_NAME=Noobie API
API_4_BASE=https://api.nuuuu.de
API_4_KEYS=sk-qWzNVkOgBXuvsDhB2VTf3m4CeNIpyIjzyFeqY8LpIPGk7YQf
API_4_MODEL=DeepSeek-R1-Distill-Qwen-32B
API_4_MODELS=DeepSeek-R1-Distill-Qwen-32B,gpt-4o-mini
API_4_ACTIVE=true
API_4_PRIORITY=1
```

#### API 5 (colin1112)
```
API_5_NAME=colin1112
API_5_BASE=https://api.colin1112.dpdns.org
API_5_KEYS=sk-XrZwTvYYCGwydj3t2eqQ6sgiNtc1oBscXZXNcigxugSI21Qq
API_5_MODEL=gpt-4o-mini
API_5_MODELS=gpt-4o-mini,deepseek-ai/DeepSeek-R1-0528,gpt-4.1-nano
API_5_ACTIVE=true
API_5_PRIORITY=1
```

## 配置步骤

1. 登录 Railway 控制台
2. 进入项目设置
3. 找到 "Variables" 或"环境变量"选项
4. 逐个添加上述环境变量
5. 重新部署应用

## 注意事项

- API_KEYS 如果有多个，用逗号分隔
- API_MODELS 用逗号分隔多个模型
- API_ACTIVE 设置为 true 或 false
- API_PRIORITY 设置为数字（1-10）
- 最多支持 20 个 API 配置（API_1 到 API_20）

## 验证配置

### 1. 验证数据库连接
```
POST https://your-app.railway.app/api/db-monitor/test-connection
Headers: Authorization: Bearer <your-token>
```

成功响应示例：
```json
{
  "success": true,
  "data": {
    "database_info": {
      "host": "interchange.proxy.rlwy.net",
      "port": 49225,
      "database": "railway",
      "user": "root",
      "connection_string": "interchange.proxy.rlwy.net:49225/railway"
    },
    "connection_time": 45.67,
    "database_version": "8.0.35",
    "connection_status": "success"
  },
  "message": "数据库连接测试成功"
}
```

### 2. 验证API代理配置
```
https://your-app.railway.app/api/api-proxy-management/test-status
```

应该能看到配置的API列表和数量。

### 3. 检查应用日志
在 Railway 控制台查看应用启动日志，应该看到：
```
🚀 使用 Railway MySQL 数据库: interchange.proxy.rlwy.net:49225/railway
```

如果看到：
```
🏠 使用本地 MySQL 数据库: localhost:3306/ocs_qa
```
说明环境变量配置有问题。

## 📋 当前 Railway 环境变量配置

### ✅ 已配置的环境变量（后端服务）
```
DATABASE_URL="${{MySQL.DATABASE_URL}}"
MYSQL_URL="${{MySQL.MYSQL_URL}}"
```

这些模板变量会自动解析为：
```
DATABASE_URL=mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway
MYSQL_URL=mysql://root:kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk@interchange.proxy.rlwy.net:49225/railway
```

### 🔧 Railway MySQL 服务自动提供的环境变量
```
MYSQL_DATABASE=railway
MYSQLUSER=root
MYSQL_ROOT_PASSWORD=kBipFtzTRrpZzQrLOGEeYaXxUHUHIhXk
MYSQLHOST=${{RAILWAY_PRIVATE_DOMAIN}}
MYSQLPORT=3306
RAILWAY_TCP_PROXY_DOMAIN=interchange.proxy.rlwy.net
RAILWAY_TCP_PROXY_PORT=49225
```

### 🎯 配置状态
- ✅ **数据库连接**：已配置模板变量
- ✅ **环境检测**：系统会自动检测 Railway 环境
- ✅ **多重备用**：支持多种连接方式
- ✅ **本地兼容**：本地开发无需修改
