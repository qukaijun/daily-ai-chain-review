# Daily AI Chain Review (每日AI产业链复盘)

基于“每日大A板块报告”的工程底座改造的新项目，用于把 AI 产业链新闻、券商研报、小作文、公告和产业数据结构化为每日复盘报告。

## 目标

- 识别 AI 产业链当日主线。
- 将事件映射到算力芯片、AI服务器、光模块、液冷、云模型、AI应用、端侧AI/机器人等环节。
- 将事件影响映射到 A股、港股、美股相关个股。
- 区分利好、利空、中性和待验证。
- 保留证据等级和下一步验证动作，避免把小作文直接当作事实。
- 自动生成多角色复盘意见，拆分事件、公告、产业链、风险和总结视角。

## 当前 MVP

第一版先跑通本地闭环：

```text
结构化事件 JSON -> 事件影响引擎 -> 产业链/个股映射 -> HTML 复盘页
```

示例事件位于：

```text
data_sources/events/sample_events.json
```

## Quick Start

```powershell
pip install -r requirements.txt
python main.py
python main.py --fetch-market
python main.py --fetch-market --deep-agents
python scripts/health_check.py
python scripts/run_daily_review.py
python scripts/notify_daily_review.py --dry-run
python scripts/notify_daily_review.py --dry-run --kind failure
python scripts/check_trading_window.py
```

输出文件在：

```text
output_files/
```

## 数据治理

证据等级遵循以下原则：

- 交易所文件、公司公告、财报：复核后可影响核心假设。
- 公司 IR、业绩会：可辅助判断，需要交叉验证。
- 多家券商研报：可提高跟踪优先级。
- 新闻/产业媒体：进入事件池，不单独改变核心假设。
- 小作文/传闻：进入验证池，不直接进入正式结论。

本工具只做研究辅助和复盘，不构成投资建议。

## 导入研报/小作文/公告

模板在：

```text
data_sources/_templates/
```

复制模板到对应目录后运行：

```powershell
python scripts/validate_events.py
python scripts/validate_verifications.py
python main.py
```

具体规则见 `docs/data-import-guide.md`。

人工确认公告候选时，复制 `data_sources/_templates/verification_update.template.json` 到 `data_sources/verifications/`。写回只覆盖验证状态和人工复核说明，不自动改原始事件或估值模型。

## 数据源管理

第一版数据源管理层位于：

```text
data/providers.py
data/ai_event_adapter.py
scripts/check_data_sources.py
```

它会按配置尝试多个 provider，一个失败时切到下一个，并记录 `provider/status/retrieved_at/error/evidence_layer`。

当前支持：

- `akshare_market`
- `akshare_news`
- `eastmoney_flash`
- `perplexity_search`，需要 `PERPLEXITY_API_KEY`
- `perplexity_research`，自动检索公开研报/分析师观点摘要，默认进入券商研报事件层
- `perplexity_rumors`，自动检索市场传闻/小作文线索，默认进入低证据验证池
- `akshare_announcements`，东方财富公告大全索引，命中 AI 股票池/关键词后进入高等级证据候选

`perplexity_search`、`perplexity_research` 和 `perplexity_rumors` 属于独立增强源，配置 key 后会在 `python main.py --fetch-market` 中单独运行，不会被东方财富快讯或 AkShare 新闻挡住。

`akshare_announcements` 属于独立公告索引源。系统会把同个股的低证据事件标记为“已找到公告候选”，但不会自动改核心假设，仍需人工核对公告原文、金额、期间和会计确认口径。

## 每日自动化

每日自动生成脚本：

```powershell
python scripts/run_daily_review.py
```

脚本会执行健康检查、事件校验、验证写回校验、密钥泄露扫描、多角色层检查、自动验证聚类检查、`main.py --fetch-market` 和最新产物巡检。日志写入 `output_files/daily_runs/`。

如需启用可选 LLM 深度多角色复盘：

```powershell
python scripts/run_daily_review.py --deep-agents
```

未配置 `DAA_LLM_API_KEY` 时会自动降级为本地确定性多角色层。

如需日报摘要通知：

```powershell
python scripts/notify_daily_review.py --dry-run
python scripts/run_daily_review.py --notify
```

默认只预览或在未启用 `DAA_NOTIFY_ENABLED=1` 时跳过发送；企业微信/兼容 webhook 地址使用环境变量配置，不写入仓库。
通知分为 `success/warning/failure` 三类：数据源存在 empty/failed 时为 warning，自动运行失败时从 `latest_run.json` 和日志尾部生成 failure 告警。
通知尝试会写入 `output_files/notification_logs/`，并支持 webhook 失败重试退避。

巡检和通知默认使用最近已完成交易日作为目标复盘日，避免午夜测试报告干扰上一交易日市场源日报。可用 `--review-date YYYY-MM-DD` 指定日期。

安装 Windows 交易日计划任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1
```

详细规则见 `docs/automation.md`。

### Perplexity 密钥

项目会自动读取全局密钥文件和项目本地覆盖文件：

```text
E:\AI工具\secrets\llm.env
.env.local
```

配置 Perplexity：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_search_secrets.ps1
python scripts/check_search_config.py
```

脚本只检查 key 是否存在和长度，不打印完整 key。

## Roadmap

1. 复制并清理大盘日报工程底座。
2. 建立 AI 产业链地图和股票池。
3. 实现事件影响引擎 MVP。
4. 接入研报、小作文、公告的文件导入。
5. 改造 HTML 页面为产业链热力图、事件表、个股影响矩阵。
6. 已加入本地确定性的 TradingAgents 式多角色分析，并可显式启用 LLM 深度版。
7. 已加入每日自动生成脚本、最新产物巡检和 Windows 计划任务安装脚本。
8. 已加入可选 LLM 深度多角色复盘，默认关闭，失败自动降级。
9. 已加入日报摘要通知底座，支持本地预览和企业微信 webhook。
10. 已加入通知异常分级和失败告警模板。
11. 已加入通知发送记录和 webhook 重试退避。
12. 已加入交易日历和盘后运行窗口治理。
