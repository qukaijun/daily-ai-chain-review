# Daily AI Chain Review (每日AI产业链复盘)

基于“每日大A板块报告”的工程底座改造的新项目，用于把 AI 产业链新闻、券商研报、小作文、公告和产业数据结构化为每日复盘报告。

## 目标

- 识别 AI 产业链当日主线。
- 将事件映射到算力芯片、AI服务器、光模块、液冷、云模型、AI应用、端侧AI/机器人等环节。
- 将事件影响映射到 A股、港股、美股相关个股。
- 区分利好、利空、中性和待验证。
- 保留证据等级和下一步验证动作，避免把小作文直接当作事实。

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
python scripts/health_check.py
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
python main.py
```

具体规则见 `docs/data-import-guide.md`。

## Roadmap

1. 复制并清理大盘日报工程底座。
2. 建立 AI 产业链地图和股票池。
3. 实现事件影响引擎 MVP。
4. 接入研报、小作文、公告的文件导入。
5. 改造 HTML 页面为产业链热力图、事件表、个股影响矩阵。
6. 后续加入 TradingAgents 式多角色分析。
