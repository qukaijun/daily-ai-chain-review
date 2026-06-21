# 每日AI产业链复盘 - 项目计划

## Current Stage

execution

## Project Manager Posture

progress driver

## Objective

用“每日大A板块报告”的工程底座新建兄弟项目“每日AI产业链复盘”，先实现可运行 MVP，并推送 GitHub。

## Stage Plan

1. 项目骨架与管理档案
   - 输出：目录、README、project-plan、decisions、tasks
   - 验收：项目结构清晰，中文 UTF-8 可读。

2. 产业链地图与股票池
   - 输出：`industry_chain/stock_pool.json`
   - 验收：覆盖算力芯片、AI服务器、光模块、液冷/IDC、云模型、AI应用、端侧AI/机器人。

3. 事件影响引擎 MVP
   - 输出：`graph/event_impact_engine.py`
   - 验收：事件可映射产业链、个股、证据等级、影响方向、验证动作。

4. HTML 复盘页
   - 输出：`templates/dashboard.html`、`output/html_renderer.py`
   - 验收：可生成包含热力图、事件表、个股影响矩阵、验证池的 HTML。

5. GitHub 发布
   - 输出：Git 仓库与远端仓库。
   - 验收：本地检查通过，提交推送成功。

## Boundaries

- 当前版本不自动爬取付费研报。
- 当前版本不把小作文作为核心结论。
- 当前版本不输出自动买卖建议。
- 真实数据接入在 MVP 验收后推进。
