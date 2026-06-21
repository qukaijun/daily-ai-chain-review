# 2026-06-21 Perplexity 增强源验收记录

## Scope

让 Perplexity 成为独立增强情报源，而不是新闻 fallback 队列末位。

## Delivered

- `config.py` 增加 `search_enrichment` 组。
- `data/providers.py` 保留 fallback 机制，同时让 Perplexity 独立运行。
- `scripts/check_data_sources.py` 支持单独检查 provider，例如 `perplexity_search`。
- 文档更新 Perplexity 独立增强源说明。

## Expected

- `news` 组仍优先使用东方财富快讯，失败后 fallback 到 AkShare 新闻。
- `search_enrichment` 组单独尝试 Perplexity。
- 未配置 key 时报告显示 `perplexity_search empty` 和未配置错误。
- 配置 key 后 Perplexity 能独立生成搜索 API 事件。

## Verification

- `python -m py_compile config.py data\providers.py scripts\check_data_sources.py`
- `python scripts\check_data_sources.py perplexity_search`
- `python scripts\check_data_sources.py`
- `python main.py --fetch-market`
- `python scripts\health_check.py`
- `python scripts\check_secrets.py`

## Result

通过。当前未配置 `PERPLEXITY_API_KEY`，单测 Perplexity 返回 `empty`；完整数据源检查仍通过，报告展示 `akshare_market ok`、`eastmoney_flash ok`、`perplexity_search empty`。
