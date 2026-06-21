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

初始化 Git 仓库，跑密钥扫描，创建 GitHub 远端并推送。

## Verification

- `python -m py_compile ...` 通过。
- `python scripts/health_check.py` 通过。
- `python main.py` 已生成首版 HTML 和分析 JSON。
- `python scripts/screenshot_report.py` 已生成浏览器截图，报告与 Chart.js 均被本地 HTTP 服务成功加载。
