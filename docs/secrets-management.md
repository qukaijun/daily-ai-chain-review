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

DAA_LLM_API_KEY=...
DAA_LLM_BASE_URL=https://api.openai.com/v1
DAA_DEEP_MODEL=gpt-4o
DAA_ENABLE_DEEP_AGENTS=0
DAA_LLM_TIMEOUT_SECONDS=45
DAA_LLM_MAX_TOKENS=2200

DAA_NOTIFY_ENABLED=0
DAA_NOTIFY_PROVIDER=console
DAA_NOTIFY_WEBHOOK_URL=...
DAA_NOTIFY_TIMEOUT_SECONDS=15
```

## 检查

`scripts/check_search_config.py` 只显示 key 是否存在、长度和脱敏片段，不打印完整 key。

`scripts/check_deep_agent_config.py` 只检查深度多角色配置和降级路径，不打印完整 key；默认不会真实调用 LLM。只有显式运行 `python scripts/check_deep_agent_config.py --live` 才允许一次真实深度模型调用。

`scripts/notify_daily_review.py --dry-run` 只预览通知内容，不发送 webhook；真实发送需要 `DAA_NOTIFY_ENABLED=1` 且配置 `DAA_NOTIFY_WEBHOOK_URL`。脚本不会打印完整 webhook 地址。
