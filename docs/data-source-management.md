# 数据源管理方案

## 目标

将 AkShare、东方财富、同花顺、Perplexity 等来源统一成 provider。一个来源失败时自动切换下一个，同时记录状态、错误、获取时间和证据层级。

## 当前 Provider

| Provider | 用途 | 证据层级 | 说明 |
| --- | --- | --- | --- |
| akshare_market | 板块异动、财经新闻 | candidate/event | 复用大盘底座思路 |
| akshare_news | 财经新闻 | event | AkShare 新闻接口 |
| eastmoney_flash | 东方财富快讯 | event | 直连快讯接口 |
| perplexity_search | AI产业链搜索摘要 | event | 需要 `PERPLEXITY_API_KEY` |

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
