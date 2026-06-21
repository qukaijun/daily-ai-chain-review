# 2026-06-21 数据源管理验收记录

## Scope

数据源管理与 fallback 第一版。

## Delivered

- `data/providers.py`
- `data/ai_event_adapter.py`
- `scripts/check_data_sources.py`
- `docs/data-source-management.md`
- `main.py --fetch-market`

## Verified

- `python -m py_compile config.py main.py data\providers.py data\ai_event_adapter.py scripts\check_data_sources.py scripts\health_check.py`
- `python scripts\health_check.py`
- `python scripts\validate_events.py`
- `python scripts\check_data_sources.py`
- `python main.py --fetch-market`

## Result

通过。当前环境下 `akshare_market` 与 `eastmoney_flash` 可用；`main.py --fetch-market` 生成 1 条 AI 产业链候选事件并输出报告。

## Notes

- Perplexity provider 已预留，需要 `PERPLEXITY_API_KEY` 后启用。
- 新闻、搜索和行情来源只进入候选/事件层，不直接改核心假设。
