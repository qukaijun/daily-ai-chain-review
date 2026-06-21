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

## Fallback 顺序

配置在 `config.py`：

```python
DATA_SOURCE_CONFIG = {
    "market_snapshot": ["akshare_market"],
    "news": ["eastmoney_flash", "akshare_news"],
    "search_enrichment": ["perplexity_search"],
}
```

说明：`news` 组采用 fallback，第一个可用源成功后不再尝试后续新闻源；`search_enrichment` 独立运行，所以配置 Perplexity 后会单独补充海外/产业链情报。

## Perplexity 结构化事件

`perplexity_search` 会优先请求 JSON Schema 输出，字段包括：

- `title/published_at/source_name/source_url`
- `chain_segments/related_companies/direction`
- `summary/bull_case/bear_case/required_confirmation`
- `citations/search_results`

如果结构化请求失败，provider 会回退为普通摘要；adapter 会尝试按段落拆分成多个事件，并保留可用引用。所有 Perplexity 事件默认属于 `search_api`，验证状态为 `pending`，不得单独改变核心假设。

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
python main.py --fetch-market
```

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
