# 🔒 安全指南

## ⚠️ 重要安全提醒

### 敏感信息保护

**绝对不要在代码中硬编码以下敏感信息：**
- API密钥
- 数据库密码
- 访问令牌
- 私钥
- 任何形式的密码

### 正确的配置管理

#### 1. 使用环境变量
```bash
# 设置环境变量
export API_KEY="your-api-key-here"
export DATABASE_PASSWORD="your-db-password"

# 在代码中读取
import os
api_key = os.getenv('API_KEY')
```

#### 2. 使用配置文件（不提交到Git）
```python
# config.json (已在.gitignore中)
{
  "api_key": "your-api-key-here",
  "database": {
    "password": "your-db-password"
  }
}
```

#### 3. 使用配置模板
- 提供 `config.json.example` 作为模板
- 实际的 `config.json` 不提交到版本控制

### Git安全检查

#### 提交前检查
```bash
# 检查是否包含敏感信息
git diff --cached | grep -i "password\|key\|secret\|token"

# 检查所有文件
grep -r "sk-" . --exclude-dir=.git
```

#### 如果意外提交了敏感信息

1. **立即修复**：
```bash
# 从暂存区移除
git rm --cached sensitive_file.txt

# 修改文件内容
# 重新提交
git add sensitive_file.txt
git commit -m "Security fix: Remove sensitive data"
git push
```

2. **清理Git历史**（如果必要）：
```bash
# 使用git filter-branch清理历史
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch sensitive_file.txt' \
--prune-empty --tag-name-filter cat -- --all

# 强制推送（危险操作）
git push origin --force --all
```

### 部署安全

#### Railway部署
- 使用环境变量配置敏感信息
- 不要在代码中包含生产环境的密钥
- 定期轮换API密钥

#### 环境变量示例
```bash
# Railway环境变量
DATABASE_URL=mysql://user:pass@host:port/db
SECRET_KEY=your-secret-key
API_PROVIDER_KEY=your-api-key
REDIS_URL=redis://host:port
```

### 代码审查清单

提交代码前检查：
- [ ] 没有硬编码的密码或API密钥
- [ ] 敏感配置文件已添加到.gitignore
- [ ] 使用环境变量或安全的配置管理
- [ ] 测试脚本不包含真实的API密钥
- [ ] 日志不输出敏感信息

### 应急响应

如果发现敏感信息泄露：

1. **立即行动**：
   - 撤销/轮换泄露的密钥
   - 修复代码并重新部署
   - 检查是否有未授权访问

2. **通知相关方**：
   - 通知团队成员
   - 如果涉及用户数据，考虑通知用户

3. **事后分析**：
   - 分析泄露原因
   - 改进安全流程
   - 更新安全培训

### 工具推荐

#### Git Hooks
```bash
# pre-commit hook 检查敏感信息
#!/bin/sh
if git diff --cached | grep -E "(password|secret|key|token)" > /dev/null; then
    echo "警告: 检测到可能的敏感信息"
    exit 1
fi
```

#### 扫描工具
- [git-secrets](https://github.com/awslabs/git-secrets)
- [truffleHog](https://github.com/trufflesecurity/trufflehog)
- [detect-secrets](https://github.com/Yelp/detect-secrets)

### 最佳实践

1. **最小权限原则**：只给予必要的权限
2. **定期轮换**：定期更换密钥和密码
3. **监控访问**：监控API使用情况
4. **加密存储**：敏感数据加密存储
5. **安全培训**：定期进行安全意识培训

---

## 📞 报告安全问题

如果发现安全漏洞，请通过以下方式报告：
- 创建私有Issue
- 发送邮件到安全团队
- 不要在公开渠道讨论安全问题

**记住：安全是每个人的责任！**
