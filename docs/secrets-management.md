# 密钥管理规范

## 原则

- 不在聊天、代码、README 示例、bat 脚本或任何会提交 GitHub 的文件里写 API key。
- 默认读取全局密钥文件 `E:\AI工具\secrets\llm.env`。
- 项目特殊配置使用 `.env.local` 覆盖。
- `.env`、`.env.local`、`secrets.env`、`llm.env` 都被 `.gitignore` 排除。

## Perplexity 配置

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_search_secrets.ps1
python scripts/check_search_config.py
```

脚本会提示输入 Perplexity API key，并写入全局或项目本地 env 文件。

## 支持字段

```text
PERPLEXITY_API_KEY=...
PERPLEXITY_BASE_URL=https://api.perplexity.ai
PERPLEXITY_MODEL=sonar
```

## 检查

`scripts/check_search_config.py` 只显示 key 是否存在、长度和脱敏片段，不打印完整 key。
