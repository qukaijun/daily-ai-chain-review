# 数据源管理方案

## 目标

将 AkShare、东方财富、同花顺、Perplexity 等来源统一成 provider。一个来源失败时自动切换下一个，同时记录状态、错误、获取时间和证据层级。

## 当前 Provider

| Provider | 用途 | 证据层级 | 说明 |
| --- | --- | --- | --- |
| akshare_market | 板块异动、财经新闻 | candidate/event | 复用大盘底座思路 |
| akshare_news | 财经新闻 | event | AkShare 新闻接口 |
| eastmoney_flash | 东方财富快讯 | event | 直连快讯接口 |
| perplexity_search | AI产业链结构化搜索增强 | event | 需要 `PERPLEXITY_API_KEY`，优先返回事件数组、引用链接和搜索结果 |
| perplexity_research | 公开研报/分析师观点增强 | research_event | 自动检索公开摘要，默认映射为 `broker_research` |
| perplexity_rumors | 市场传闻/小作文增强 | low_evidence | 自动检索传闻线索，默认映射为 `xiaozuowen` |
| akshare_announcements | 东方财富公告大全 | audit_source | 拉取最近公告索引，命中 AI 股票池/关键词后进入公告候选 |

## Fallback 顺序

配置在 `config.py`：

```python
DATA_SOURCE_CONFIG = {
    "market_snapshot": ["akshare_market"],
    "news": ["eastmoney_flash", "akshare_news"],
    "search_enrichment": ["perplexity_search"],
    "research_enrichment": ["perplexity_research"],
    "rumor_enrichment": ["perplexity_rumors"],
    "announcement_index": ["akshare_announcements"],
}
```

说明：`news` 组采用 fallback，第一个可用源成功后不再尝试后续新闻源；`search_enrichment`、`research_enrichment`、`rumor_enrichment` 独立运行，所以配置 Perplexity 后会分别补充产业链新闻、公开研报摘要和传闻线索。

## Perplexity 结构化事件

`perplexity_search`、`perplexity_research`、`perplexity_rumors` 会优先请求 JSON Schema 输出，字段包括：

- `title/published_at/source_name/source_url`
- `chain_segments/related_companies/direction`
- `summary/bull_case/bear_case/required_confirmation`
- `citations/search_results`

如果结构化请求失败，provider 会回退为普通摘要；adapter 会尝试按段落拆分成多个事件，并保留可用引用。

映射规则：

- `perplexity_search` 默认属于 `search_api`；
- `perplexity_research` 默认属于 `broker_research`；
- `perplexity_rumors` 默认属于 `xiaozuowen`。

所有 Perplexity 自动事件验证状态默认为 `pending`，不得单独改变核心假设。

## 验证状态生命周期

| 状态 | 含义 | 写入规则 |
| --- | --- | --- |
| pending | 待验证 | 默认状态，进入验证池 |
| confirmed | 已交叉验证 | 可提高跟踪优先级，但不等于核心假设更新 |
| rejected | 已证伪 | 保留记录，不纳入主判断 |
| expired | 已过期 | 超过验证窗口后停止跟踪 |
| upgraded | 已升级为高等级证据 | 需关联公告、交易所文件或财报后复核 |
| not_required | 无需低证据验证 | 仅适用于高等级来源或人工确认场景 |

## 使用

```powershell
python scripts/check_data_sources.py
python scripts/check_data_sources.py perplexity_search
python scripts/check_data_sources.py perplexity_research
python scripts/check_data_sources.py perplexity_rumors
python scripts/check_announcement_provider.py
python main.py --fetch-market
python scripts/run_daily_review.py
python scripts/check_latest_run.py --require-today --require-market-sources
```

## 公告索引

`akshare_announcements` 复用 AkShare 的 `stock_notice_report(symbol="全部", date="YYYYMMDD")`，按最近若干天拉取东方财富公告大全，再用 AI 股票池和 AI 关键词过滤。

公告索引的写入规则：

- 输出 `company_announcement` 事件，证据层级为 `P0/audit_source`。
- 默认 `verification_status=not_required`，但仍要求人工复核公告原文、金额、期间和会计确认口径。
- 若低证据事件命中同一只股票的公告候选，会在验证池里标记为 `已找到公告候选`，但不会自动认定原事件已被验证。
- 可抓取公告详情接口，保留 `content_excerpt/pdf_url/fact_markers/review_checklist`。
- 配置项：`DAA_ANNOUNCEMENT_LOOKBACK_DAYS`、`DAA_ANNOUNCEMENT_MAX_ITEMS`、`DAA_ANNOUNCEMENT_FETCH_DETAIL`、`DAA_ANNOUNCEMENT_DETAIL_MAX_ITEMS`、`DAA_ANNOUNCEMENT_DETAIL_MAX_PAGES`。

## 公告复核清单

公告详情抓取只生成复核辅助字段，不自动形成投资结论：

- `content_excerpt`：公告正文摘要截取，用于快速判断主题；
- `pdf_url`：公告 PDF 原文链接；
- `fact_markers`：从正文中提取金额、比例和日期等显性字段；
- `review_checklist`：人工复核动作，例如核对公告原文、金额、期间、会计确认口径、是否与原低证据事件直接相关。

只有人工确认公告与原事件存在直接关系后，低证据事件才能从“公告候选”进一步转为“已交叉验证”。

## 人工确认写回

公告候选确认采用独立写回层，不覆盖原始新闻、搜索或小作文事件：

```text
data_sources/verifications/
data_sources/_templates/verification_update.template.json
```

运行顺序：

```powershell
python scripts/validate_verifications.py
python main.py --fetch-market
```

写回规则：

- `verification_status=confirmed`：人工确认原低证据事件与公告/文件/财报直接相关；退出验证池，保留人工确认说明。
- `verification_status=rejected`：公告或后续证据证伪原事件；退出验证池，不进入正向/负向主判断。
- `verification_status=expired`：超过验证窗口仍无证据；退出验证池。
- `verification_status=upgraded`：找到高等级证据候选但尚未完成核心事实核对；继续保留在验证池。
- `model_update_candidate=true`：必须有人工确认、`confirmed/upgraded/not_required` 状态，并明确 `evidence_source_type` 为公告、交易所文件或财报；这只代表“进入核心假设复核候选”，不自动改估值模型。

如果同一个 `event_id` 在多个写回文件里出现，按文件名排序后的最后一条记录生效。

自动数据源生成的事件 ID 使用发布时间、标题、来源链接和公告代码生成，便于同一事件在重复运行时被人工确认文件匹配。

## 自动验证评分与去重

系统会在报告生成时自动按个股、产业链环节和日期聚类，识别：

- `公告/高等级证据候选`：同个股命中公告、交易所文件或财报；
- `多来源共振`：多个 provider 或多个来源类型提到同一股票/主题；
- `疑似重复线索`：同一来源或同类来源重复出现；
- `待验证`：暂无高等级证据或多来源交叉验证。

自动验证分数只用于排序和复核提示，不代表事实确认，也不自动改变核心假设。低证据事件即使命中公告候选，也仍需人工核对公告原文、金额、期间、会计确认口径和与原事件的直接关系。

## 多角色复盘层

报告生成时会自动输出本地确定性多角色分析，模拟 TradingAgents 的分工：

- 新闻/事件分析员；
- 公告证据分析员；
- 产业链传导分析员；
- 风险与证伪分析员；
- 复盘总结员。

多角色层只读取已经结构化的事件、产业链热力、个股影响、验证池和自动验证簇，输出观察、依据、风险和下一步验证。它不调用交易接口，不输出买卖建议，也不自动修改核心假设。

## 密钥加载

项目读取密钥的优先级：

```text
系统环境变量 > 项目 secrets.env > 项目 .env.local > 全局 E:\AI工具\secrets\llm.env > 项目 .env
```

配置 Perplexity：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_search_secrets.ps1
python scripts/check_search_config.py
```

密钥文件已被 `.gitignore` 排除，不进入 GitHub。

## 页面展示

运行 `python main.py --fetch-market` 后，HTML 会展示：

- Provider 名称；
- 状态：`ok`、`empty`、`failed`；
- 证据层级；
- 获取时间；
- 数量；
- 错误信息；
- 每条事件的 Provider 或本地文件来源。

## 治理规则

- 所有 provider 输出必须保留 `provider/status/retrieved_at/error/evidence_layer`。
- 新闻、搜索 API、行情和第三方数据只进入候选层或事件层。
- 只有公告、交易所文件、财报等高等级证据可在复核后影响核心假设。
- provider 失败必须记录，不静默吞掉。
- 小作文、传闻、搜索增强事件必须保留 `verification_status` 和下一步验证动作。
- 自动研报和自动传闻只进入事件层/验证池，不自动改核心假设。
- 自动验证评分和去重只输出复核提示，不自动确认或证伪事件。
- 多角色复盘只做研究辅助和验证动作拆解，不输出自动交易建议。
- 公告索引只能作为高等级证据候选；是否升级核心假设必须人工核对原文。
- 公告详情摘要和事实标记只用于复核效率，不替代公告原文。
- 人工确认写回必须保留证据标题、链接、复核结论和是否进入模型复核候选。

## 每日自动生成与巡检

`scripts/run_daily_review.py` 是当前推荐的生产入口。它会先做健康检查和输入校验，再运行 `main.py --fetch-market`，最后用 `scripts/check_latest_run.py` 校验最新 HTML/JSON 产物。

巡检只判断报告是否可用，不把自动新闻、研报或传闻升级为事实确认。Perplexity 未配置时会记录为 `empty`，只要仍有其他 provider 可用，不阻断日报生成。

Windows 计划任务安装脚本见 `scripts/install_daily_task.ps1`，详细说明见 `docs/automation.md`。

## 可选 LLM 深度多角色复盘

默认报告使用本地确定性多角色层。需要更深入的复盘解释时，可以显式启用：

```powershell
python main.py --fetch-market --deep-agents
python scripts/run_daily_review.py --deep-agents
```

深度版通过 OpenAI-compatible Chat Completions 接口读取已结构化的分析摘要，只输出五类角色卡片和一致结论，不改写事件、验证状态、证据等级或估值模型。若未配置 `DAA_LLM_API_KEY` 或调用失败，会自动降级为本地确定性层，并在 HTML 的“多角色模式”卡片中显示状态。
