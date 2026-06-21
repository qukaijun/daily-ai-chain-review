# 数据导入指南

## 目录

```text
data_sources/events/             # 新闻、产业数据、海外科技动态等通用事件
data_sources/research_reports/   # 券商研报摘要
data_sources/rumors/             # 小作文、传闻、待验证线索
data_sources/announcements/      # 公司公告、交易所文件、财报摘要
data_sources/_templates/         # 导入模板，不参与报告生成
```

## 使用方式

1. 从 `data_sources/_templates/` 复制模板。
2. 改名放入对应目录，例如 `data_sources/research_reports/2026-06-21-optical.json`。
3. 填写结构化字段。
4. 运行：

```powershell
python scripts/validate_events.py
python main.py
```

## 证据写入规则

| 来源 | source_type | 写入策略 |
| --- | --- | --- |
| 交易所文件 | exchange_filing | 复核后可影响核心假设 |
| 公司公告 | company_announcement | 复核后可影响核心假设 |
| 财报 | financial_report | 复核后可影响核心假设 |
| 公司IR/调研 | company_ir | 需要交叉验证 |
| 多家券商研报 | multi_broker_research | 可提高跟踪优先级 |
| 单家券商研报 | broker_research | 进入事件池，需验证 |
| 新闻/产业媒体 | news/media/overseas_news | 进入事件池 |
| 小作文/传闻 | xiaozuowen/rumor | 进入验证池，不改核心假设 |

## 字段说明

- `id`：全局唯一，建议 `source-YYYYMMDD-001`。
- `title`：一句话事件标题。
- `source_type`：来源类型，必须匹配配置。
- `source_name`：来源名称，例如券商、交易所、媒体。
- `published_at`：发布时间。
- `chain_segments`：产业链环节 ID，见 `industry_chain/stock_pool.json`。
- `direction`：`strong_positive`、`positive`、`neutral`、`negative`、`strong_negative`、`unknown`。
- `weight`：事件重要性，1-5。
- `summary`：自己的摘要，不粘贴大段研报原文。
- `affected_stocks`：股票代码列表。
- `bull_case`：看多路径。
- `bear_case`：风险/证伪路径。
- `required_confirmation`：下一步验证动作。
- `verification_status`：验证状态，可选 `pending`、`confirmed`、`rejected`、`expired`、`upgraded`、`not_required`。
- `verification_note`：验证进展说明。

## 验证状态

| 状态 | 使用场景 |
| --- | --- |
| pending | 默认待验证，适用于小作文、新闻、搜索 API、单家研报 |
| confirmed | 已有多来源交叉验证，但还未升级为公告/财报等高等级证据 |
| rejected | 后续证据证明事件不成立 |
| expired | 超过验证窗口仍无证据，停止跟踪 |
| upgraded | 已找到公告、交易所文件或财报等高等级证据，等待复核写入 |
| not_required | 高等级来源或人工已确认场景；低证据事件不能使用 |

## 注意

- 小作文不要写入个人隐私、截图水印、群名、客户姓名、手机号。
- 研报只保留摘要和结构化判断，不保存全文。
- 新闻和小作文不能单独改变核心利润假设。
