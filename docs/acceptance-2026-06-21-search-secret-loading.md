# 2026-06-21 搜索密钥加载验收记录

## Scope

复用大盘日报的“不暴露 API key”密钥加载机制，并接入 Perplexity 搜索配置。

## Delivered

- `config.py` 支持读取全局 `E:\AI工具\secrets\llm.env`、项目 `.env.local`、项目 `secrets.env`。
- `scripts/setup_search_secrets.ps1` 用安全输入写入 `PERPLEXITY_API_KEY`。
- `scripts/check_search_config.py` 只输出 key 是否存在、长度和脱敏片段。
- `docs/secrets-management.md` 记录密钥管理规则。

## Verification

- `python -m py_compile config.py scripts\check_search_config.py scripts\health_check.py data\providers.py`
- `python scripts\check_search_config.py`
- `python scripts\health_check.py`
- `python scripts\check_secrets.py`

## Result

通过。项目可以读取全局 env 文件；当前全局文件里有 `DAA_LLM_API_KEY`，但尚未配置 `PERPLEXITY_API_KEY`。

## Next

运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_search_secrets.ps1
python scripts/check_search_config.py
python scripts/check_data_sources.py
```
