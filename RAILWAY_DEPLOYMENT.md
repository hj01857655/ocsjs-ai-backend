# Railway 部署指南

## 🚀 快速部署到Railway

### 1. 准备工作

1. 注册 [Railway](https://railway.app) 账号
2. 连接你的GitHub账号
3. 准备好数据库和API密钥

### 2. 部署后端

#### 步骤1：创建新项目
1. 在Railway控制台点击 "New Project"
2. 选择 "Deploy from GitHub repo"
3. 选择 `ocsjs-ai-backend` 仓库

#### 步骤2：配置环境变量

在Railway项目设置中添加以下环境变量：

```bash
# 数据库配置
DATABASE_URL=mysql://username:password@host:port/database_name

# 或者分别配置
DB_HOST=your-mysql-host
DB_PORT=3306
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=your-database-name

# Redis配置（可选）
REDIS_URL=redis://username:password@host:port/db

# 应用配置
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=production
PORT=5000

# API密钥（根据你使用的服务配置）
OPENAI_API_KEY=sk-your-openai-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
# 其他API密钥...

# 安全配置
ACCESS_TOKEN=your-access-token-if-needed
```

#### 步骤3：数据库设置

**选项1：使用Railway MySQL**
1. 在项目中添加MySQL服务
2. Railway会自动提供 `DATABASE_URL`

**选项2：使用外部数据库**
1. 使用PlanetScale、AWS RDS等
2. 手动配置 `DATABASE_URL`

### 3. 部署前端

#### 步骤1：创建前端项目
1. 创建新的Railway项目
2. 连接 `ocsjs-ai-frontend` 仓库

#### 步骤2：配置环境变量

```bash
# API配置
VITE_API_BASE_URL=https://your-backend-domain.railway.app/api

# 构建配置
NODE_ENV=production
```

### 4. 配置文件处理

由于 `config.json` 包含敏感信息，不应提交到Git。在Railway中有两种处理方式：

#### 方式1：环境变量（推荐）
修改后端代码读取环境变量而不是config.json：

```python
import os
import json

# 优先使用环境变量，fallback到config.json
def load_config():
    if os.getenv('DATABASE_URL'):
        # 从环境变量加载配置
        return {
            'database': {
                'url': os.getenv('DATABASE_URL')
            },
            'security': {
                'secret_key': os.getenv('SECRET_KEY')
            }
            # ... 其他配置
        }
    else:
        # 从config.json加载配置
        with open('config.json', 'r') as f:
            return json.load(f)
```

#### 方式2：Railway Volumes（高级）
1. 在Railway中创建Volume
2. 上传config.json到Volume
3. 挂载到应用容器

### 5. 自动部署

Railway支持自动部署：
1. 推送代码到GitHub
2. Railway自动检测变更
3. 自动构建和部署

### 6. 域名配置

#### 后端域名
- Railway提供免费域名：`your-app.railway.app`
- 可以绑定自定义域名

#### 前端域名
- 同样提供免费域名
- 更新前端的API_BASE_URL指向后端域名

### 7. 监控和日志

- Railway控制台提供实时日志
- 可以查看部署状态和错误信息
- 支持指标监控

### 8. 数据库迁移

首次部署后需要初始化数据库：

```bash
# 在Railway控制台的终端中执行
python -c "from models.models import init_db; init_db()"
```

### 9. 环境变量示例

完整的环境变量配置示例：

```bash
# === 数据库配置 ===
DATABASE_URL=mysql://user:pass@host:3306/dbname

# === 应用配置 ===
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=production
PORT=5000
DEBUG=false

# === API配置 ===
# 根据你的API提供商配置
API_PROVIDER_1_KEY=sk-your-key-1
API_PROVIDER_1_BASE=https://api.provider1.com
API_PROVIDER_2_KEY=sk-your-key-2
API_PROVIDER_2_BASE=https://api.provider2.com

# === 缓存配置 ===
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_EXPIRATION=2592000

# === 安全配置 ===
ACCESS_TOKEN=your-access-token-if-needed
CORS_ORIGINS=https://your-frontend-domain.railway.app

# === 日志配置 ===
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 10. 故障排除

#### 常见问题：

1. **数据库连接失败**
   - 检查DATABASE_URL格式
   - 确认数据库服务正在运行

2. **API密钥错误**
   - 检查环境变量名称
   - 确认密钥有效性

3. **前端无法连接后端**
   - 检查VITE_API_BASE_URL配置
   - 确认CORS设置

4. **构建失败**
   - 检查依赖版本
   - 查看构建日志

### 11. 成本优化

- Railway提供免费额度
- 监控使用量避免超额
- 考虑使用睡眠模式节省资源

---

## 📞 支持

如果遇到部署问题：
1. 查看Railway文档
2. 检查项目日志
3. 参考GitHub Issues

**部署成功后，你的应用将可以通过以下地址访问：**
- 后端API: `https://your-backend.railway.app`
- 前端界面: `https://your-frontend.railway.app`
