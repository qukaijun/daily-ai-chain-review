# 每日自动生成与巡检

## 目标

N23 的自动化闭环包括三层：

- 一键生成：运行完整复盘、保存日志和运行摘要。
- 产物巡检：检查最新 `analysis/report/market_sources` 是否新鲜、完整、可阅读。
- 外部定时：可用 Windows 计划任务或 Codex 定时器每天触发。

## 本地一键运行

```powershell
python scripts/run_daily_review.py
```

默认会运行：

1. `scripts/health_check.py`
2. `scripts/validate_events.py`
3. `scripts/validate_verifications.py`
4. `scripts/check_secrets.py`
5. `scripts/check_trading_calendar.py`
6. `scripts/check_multi_agent_layer.py`
7. `scripts/check_deep_agent_config.py`
8. `scripts/check_verification_clusters.py`
9. `main.py --fetch-market`
10. `scripts/check_latest_run.py --require-market-sources`

日志和运行摘要写入：

```text
output_files/daily_runs/
```

这些文件属于运行产物，不提交 GitHub。

## 单独巡检

```powershell
python scripts/check_latest_run.py --require-market-sources
python scripts/check_latest_run.py --review-date 2026-06-21 --require-market-sources
```

巡检会检查：

- 最新分析 JSON 是否在允许时间内生成；
- HTML 报告是否存在；
- 事件数量是否大于最小阈值；
- 多角色复盘是否生成至少 5 个角色；
- 自动验证与去重、数据源状态、多角色复盘模块是否出现在 HTML；
- 数据源是否全部不可用。

Perplexity 未配置时，对应 provider 会显示 `empty`，但只要其他数据源可用，不视为阻断。

## 交易日与盘后窗口

系统默认使用“最近已完成交易日”作为复盘目标日，而不是简单使用自然日。规则：

- 周一至周五默认为候选交易日；
- 默认盘后可用时间为 `17:00`；
- 交易日 `17:00` 之后，目标复盘日为当天；
- 交易日 `17:00` 之前、周末或节假日，目标复盘日为上一交易日；
- 优先读取 `market_calendar/calendars/cn_a_YYYY.json` 年度日历文件；
- 可通过 `DAA_MARKET_HOLIDAYS` 和 `DAA_MARKET_EXTRA_TRADING_DAYS` 临时补充节假日和补班交易日。

检查当前窗口：

```powershell
python scripts/check_trading_window.py
python scripts/check_trading_calendar.py
python scripts/check_trading_window.py --now "2026-06-22 00:10:00"
python scripts/run_daily_review.py --review-date 2026-06-21 --no-fetch-market
```

当前内置年度文件：

```text
market_calendar/calendars/cn_a_2026.json
```

该文件记录来源、发布日期、URL、工作日休市日期和补充交易日。周末默认非交易日，不需要重复写入年度文件。

配置项：

```text
DAA_REVIEW_READY_TIME=17:00
DAA_MARKET_HOLIDAYS=2026-01-01,2026-02-17
DAA_MARKET_EXTRA_TRADING_DAYS=
```

## Windows 计划任务

安装交易日 18:30 自动任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1
```

修改时间：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1 -At "19:00"
```

只跑本地事件、不抓取市场源：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1 -NoFetchMarket
```

启用可选 LLM 深度多角色复盘：

```powershell
python scripts/run_daily_review.py --deep-agents
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1 -DeepAgents
```

如果未配置 `DAA_LLM_API_KEY`，系统会自动降级为本地确定性多角色层。日常健康检查不会真实调用 LLM；只有 `python scripts/check_deep_agent_config.py --live` 会测试真实模型调用。

启用日报摘要通知：

```powershell
python scripts/notify_daily_review.py --dry-run
python scripts/run_daily_review.py --notify
powershell -ExecutionPolicy Bypass -File scripts/install_daily_task.ps1 -Notify
```

默认 `DAA_NOTIFY_ENABLED=0`，即使传入 `--notify` 也只会在日志中提示未启用发送。配置企业微信机器人或兼容 webhook：

```text
DAA_NOTIFY_ENABLED=1
DAA_NOTIFY_PROVIDER=wecom
DAA_NOTIFY_WEBHOOK_URL=https://...
DAA_NOTIFY_MAX_RETRIES=2
DAA_NOTIFY_RETRY_BACKOFF_SECONDS=2
```

通知只发送紧凑摘要：事件数、验证池、主线、多角色状态、数据源状态和本地 HTML 报告路径，不发送 API key 或报告全文。

通知发送记录写入：

```text
output_files/notification_logs/
```

记录包含 provider、通知级别、是否请求发送、是否启用、发送状态、尝试次数、错误摘要、报告路径和摘要字段；不保存完整 webhook 明文。

通知模板分级：

- `success`：日报生成和巡检通过，数据源无异常。
- `warning`：日报生成和巡检通过，但存在 provider `empty/failed` 或其他非阻断问题。
- `failure`：自动运行失败，从 `output_files/daily_runs/latest_run.json` 和日志尾部生成告警。

发送重试规则：

- 仅真实发送 webhook 时启用；
- 默认最多重试 2 次，即最多 3 次尝试；
- 默认退避为 2 秒、4 秒；
- 每次最终结果都会写入通知日志。

手动预览：

```powershell
python scripts/notify_daily_review.py --dry-run --kind success --require-market-sources
python scripts/notify_daily_review.py --dry-run --kind failure
python scripts/notify_daily_review.py --dry-run --kind auto
```

## Codex 定时器

推荐把 Codex 定时器作为通知和异常诊断层：

- 定时运行 `python scripts/run_daily_review.py`；
- 成功时报告最新 HTML 路径和 provider 状态；
- 失败时先读取 `output_files/daily_runs/latest_run.json` 和日志定位问题；
- 不打印 API key，不提交 `output_files/` 运行产物。
- 默认不启用 LLM 深度复盘；如需启用，在自动化 prompt 或脚本参数中显式加入 `--deep-agents`。
- 默认不启用 webhook 通知；如需外部推送，在脚本参数中显式加入 `--notify` 并配置环境变量。
- 自动化失败且传入 `--notify` 时，会额外尝试发送 failure 模板；未启用 webhook 时仍只写入日志。

## 治理规则

- 自动化只生成研究辅助报告，不构成投资建议。
- 自动数据源的新闻、研报、传闻只进入事件层或验证池。
- 只有公告、交易所文件、财报等高等级证据在人工复核后才可进入核心假设复核。
- 每次自动运行必须留下日志、运行摘要和可巡检产物。
- LLM 深度多角色复盘只增强研究解释，不改变证据等级、验证状态或核心假设。
- 通知通道只发送摘要和路径；webhook 地址属于密钥配置，不进入 GitHub。
- 通知发送记录属于运行产物，不提交 GitHub；记录中只保留 webhook 脱敏片段。
