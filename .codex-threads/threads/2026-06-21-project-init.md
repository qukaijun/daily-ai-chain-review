# 每日AI产业链复盘项目初始化

## Current Objective

用每日大盘日报工程底座新建“每日AI产业链复盘”项目，实现可运行 MVP 并推送 GitHub。

## Project Path

`E:\AI工具\agent学习\每日AI产业链复盘`

## Status

active

## Decisions

- 新项目作为“每日大A板块报告”的兄弟项目。
- MVP 先走结构化事件 JSON，不依赖外部爬虫。
- 研报、新闻、小作文统一进入事件影响引擎，但按证据等级分层。
- 小作文/传闻进入验证池，不直接更新核心假设。

## Next Action

推进下一阶段：增加真实公告/交易所文件抓取或导入索引、研报摘要批量导入助手、小作文验证状态追踪。

## Verification

- `python -m py_compile ...` 通过。
- `python scripts/health_check.py` 通过。
- `python main.py` 已生成首版 HTML 和分析 JSON。
- `python scripts/screenshot_report.py` 已生成浏览器截图，报告与 Chart.js 均被本地 HTTP 服务成功加载。
- GitHub 仓库已创建并推送：`https://github.com/qukaijun/daily-ai-chain-review`
- 已增加 `data_sources/_templates/`、`data_sources/announcements/` 与 `scripts/validate_events.py`。
- `python scripts/validate_events.py` 通过，模板未污染真实事件加载。
- 已增加数据源管理器与 fallback：`data/providers.py`、`data/ai_event_adapter.py`、`scripts/check_data_sources.py`。
- `python main.py --fetch-market` 已验证可从当前可用数据源生成 AI 产业链候选事件。
- HTML 已展示数据源状态和事件 Provider/文件来源，便于追踪自动事件来源与 provider 故障。
- 已复用大盘日报的全局 env 密钥加载机制；当前尚未配置 `PERPLEXITY_API_KEY`，配置后可启用 `perplexity_search` provider。
