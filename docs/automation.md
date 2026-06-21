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
5. `scripts/check_multi_agent_layer.py`
6. `scripts/check_deep_agent_config.py`
7. `scripts/check_verification_clusters.py`
8. `main.py --fetch-market`
9. `scripts/check_latest_run.py --require-today --require-market-sources`

日志和运行摘要写入：

```text
output_files/daily_runs/
```

这些文件属于运行产物，不提交 GitHub。

## 单独巡检

```powershell
python scripts/check_latest_run.py --require-today --require-market-sources
```

巡检会检查：

- 最新分析 JSON 是否在允许时间内生成；
- HTML 报告是否存在；
- 事件数量是否大于最小阈值；
- 多角色复盘是否生成至少 5 个角色；
- 自动验证与去重、数据源状态、多角色复盘模块是否出现在 HTML；
- 数据源是否全部不可用。

Perplexity 未配置时，对应 provider 会显示 `empty`，但只要其他数据源可用，不视为阻断。

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

## Codex 定时器

推荐把 Codex 定时器作为通知和异常诊断层：

- 定时运行 `python scripts/run_daily_review.py`；
- 成功时报告最新 HTML 路径和 provider 状态；
- 失败时先读取 `output_files/daily_runs/latest_run.json` 和日志定位问题；
- 不打印 API key，不提交 `output_files/` 运行产物。
- 默认不启用 LLM 深度复盘；如需启用，在自动化 prompt 或脚本参数中显式加入 `--deep-agents`。

## 治理规则

- 自动化只生成研究辅助报告，不构成投资建议。
- 自动数据源的新闻、研报、传闻只进入事件层或验证池。
- 只有公告、交易所文件、财报等高等级证据在人工复核后才可进入核心假设复核。
- 每次自动运行必须留下日志、运行摘要和可巡检产物。
- LLM 深度多角色复盘只增强研究解释，不改变证据等级、验证状态或核心假设。
