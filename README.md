# OCSJS AI - 智能题库系统后端

> **重大更新通知**: 本项目已升级为第三方API代理池架构，支持多个第三方API服务的负载均衡和故障转移。

这是一个基于Python和多第三方AI API的新一代智能题库服务后端，专为[OCS (Online Course Script)](https://github.com/ocsjs/ocsjs)设计，可以通过AI自动回答题目。此服务实现了与OCS AnswererWrapper兼容的API接口。

## ⚠️ 重要提示

> [!IMPORTANT]
> - 本项目仅供个人学习使用，不保证稳定性，且不提供任何技术支持。
> - 使用者必须在遵循各第三方AI服务提供商的使用条款以及**法律法规**的情况下使用，不得用于非法用途。
> - 根据[《生成式人工智能服务管理暂行办法》](http://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)的要求，请勿对中国地区公众提供一切未经备案的生成式人工智能服务。

## 🌟 后端功能特点

- 🌐 **第三方API代理池**：支持多个第三方API服务的负载均衡和故障转移
- 💡 **多AI供应商支持**：支持OpenAI、Anthropic、Google等多个AI供应商
- 🔄 **OCS兼容**：完全兼容OCS的AnswererWrapper题库接口
- 🚀 **高性能缓存**：Redis + 内存双重缓存，快速响应请求
- 🔒 **安全可靠**：支持访问令牌验证，完整的用户权限管理
- 💬 **多种题型**：支持单选、多选、判断、填空等题型
- 📊 **数据统计**：实时监控服务状态和使用情况
- 👥 **用户管理**：完整的用户注册、登录、权限管理系统
- 🔑 **代理池监控**：智能代理选择、密钥轮换和实时监控
- 🖼️ **图片代理**：解决超星平台图片403问题
- 📚 **题库管理**：完整的题库增删改查和导出功能
- ⚡ **智能故障转移**：自动检测代理状态，无缝切换到可用代理
- 🎯 **负载均衡**：支持多种代理选择策略，优化性能和可靠性

## 📋 系统要求

- Python 3.8+ (推荐 Python 3.9+)
- MySQL 8.0+ (用于数据存储)
- Redis (可选，用于缓存)
- 第三方AI API密钥（支持OpenAI兼容接口的服务）

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置文件

复制并编辑配置文件：

```bash
cp config/config.py.example config/config.py
```

编辑 `config/config.py` 文件，配置数据库连接和API密钥。

### 3. 数据库初始化

```bash
# 创建数据库表
python -c "from models.models import init_db; init_db()"
```

### 4. 启动服务

```bash
# 开发环境
python app.py

# 生产环境
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📁 项目结构

```
backend/
├── app.py                 # 主应用入口
├── config/                # 配置文件
│   ├── config.py         # 主配置文件
│   └── config.py.example # 配置模板
├── models/                # 数据模型
│   ├── models.py         # 数据库模型定义
│   └── __init__.py
├── routes/                # API路由
│   ├── auth.py           # 认证相关路由
│   ├── questions.py      # 题目相关路由
│   ├── users.py          # 用户管理路由
│   ├── logs.py           # 日志管理路由
│   ├── api_proxy_management.py  # API代理管理
│   ├── proxy_management.py      # 网络代理管理
│   ├── system_monitor.py        # 系统监控
│   └── db_monitor.py            # 数据库监控
├── services/              # 业务服务
│   ├── ai_service.py     # AI服务核心
│   ├── api_proxy_pool.py # API代理池
│   ├── cache.py          # 缓存服务
│   └── search.py         # 搜索服务
├── utils/                 # 工具函数
│   ├── auth.py           # 认证工具
│   ├── logger.py         # 日志工具
│   ├── db_monitor.py     # 数据库监控工具
│   ├── system_monitor.py # 系统监控工具
│   └── error_handler.py  # 错误处理工具
├── scripts/               # 脚本文件
├── logs/                  # 日志文件
├── requirements.txt       # Python依赖
└── README.md             # 项目文档
```

## 🔧 API接口

### 认证接口

- `POST /api/auth/login` - 用户登录
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/logout` - 用户登出

### 题目搜索接口

- `POST /api/questions/search` - 搜索题目答案
- `POST /api/questions/batch-search` - 批量搜索题目

### 管理接口

- `GET /api/system-monitor/stats` - 获取系统状态
- `GET /api/db-monitor/health` - 数据库健康检查
- `GET /api/api-proxy-management/status` - API代理状态

### 健康检查

- `GET /health` - 服务健康检查

## 🔧 配置说明

### 数据库配置

```python
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'your_username',
    'password': 'your_password',
    'database': 'edubrain_ai'
}
```

### API代理池配置

```python
API_PROXIES = [
    {
        'name': 'openai-proxy-1',
        'base_url': 'https://api.openai.com/v1',
        'api_key': 'your-api-key',
        'model': 'gpt-4o-mini',
        'priority': 1
    }
]
```

## 🚀 部署指南

### Docker部署

```bash
# 构建镜像
docker build -t edubrain-backend .

# 运行容器
docker run -d -p 5000:5000 \
  -e DATABASE_URL=mysql://user:pass@host:3306/db \
  edubrain-backend
```

### 系统服务部署

```bash
# 创建systemd服务文件
sudo cp scripts/edubrain-backend.service /etc/systemd/system/

# 启动服务
sudo systemctl enable edubrain-backend
sudo systemctl start edubrain-backend
```

## 📊 监控和日志

- 系统监控：`/api/system-monitor/stats`
- 数据库监控：`/api/db-monitor/health`
- 日志文件：`logs/` 目录
- 错误追踪：集成的错误处理和日志记录

## 🤝 开发指南

### 代码规范

- 遵循PEP 8 Python代码规范
- 使用类型提示
- 编写单元测试
- 添加适当的文档字符串

### 测试

```bash
# 运行测试
python -m pytest tests/

# 代码覆盖率
python -m pytest --cov=. tests/
```

## 📄 许可证

本项目仅供学习和研究使用。

## 🔗 相关链接

- [前端项目](https://github.com/hj01857655/ocsjs-ai-frontend)
- [OCS项目](https://github.com/ocsjs/ocsjs)
- [API文档](./docs/api.md)

---

**最后更新**: 2025-01-25
**版本**: v2.0.0
**维护者**: OCSJS AI Team
