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
    "news": ["eastmoney_flash", "akshare_news", "perplexity_search"],
}
```

## 使用

```powershell
python scripts/check_data_sources.py
python main.py --fetch-market
```

## 治理规则

- 所有 provider 输出必须保留 `provider/status/retrieved_at/error/evidence_layer`。
- 新闻、搜索 API、行情和第三方数据只进入候选层或事件层。
- 只有公告、交易所文件、财报等高等级证据可在复核后影响核心假设。
- provider 失败必须记录，不静默吞掉。
