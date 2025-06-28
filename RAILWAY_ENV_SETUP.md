# Railway 环境变量配置指南

由于 `config.json` 文件包含敏感信息不会提交到 GitHub，需要在 Railway 中配置环境变量来创建配置文件。

## 必需的环境变量

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

部署完成后，访问以下接口验证配置是否正确：
```
https://your-app.railway.app/api/api-proxy-management/test-status
```

应该能看到配置的API列表和数量。
