# -*- coding: utf-8 -*-
"""每日AI产业链复盘 - 全局配置"""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output_files"
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_SOURCES_DIR = ROOT / "data_sources"
EVENTS_DIR = DATA_SOURCES_DIR / "events"
RESEARCH_REPORTS_DIR = DATA_SOURCES_DIR / "research_reports"
RUMORS_DIR = DATA_SOURCES_DIR / "rumors"
ANNOUNCEMENTS_DIR = DATA_SOURCES_DIR / "announcements"
TEMPLATES_DIR = DATA_SOURCES_DIR / "_templates"
INDUSTRY_CHAIN_DIR = ROOT / "industry_chain"
CACHE_DIR = ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

PROJECT_NAME = "每日AI产业链复盘"
PROJECT_SLUG = "daily-ai-chain-review"

_ORIGINAL_ENV = set(os.environ)
_LOADED_ENV_FILES: list[str] = []
_TOOLS_ROOT = ROOT.parent.parent if len(ROOT.parents) >= 2 else ROOT.parent
_GLOBAL_ENV_PATH = Path(os.getenv("DAA_GLOBAL_ENV_FILE", str(_TOOLS_ROOT / "secrets" / "llm.env")))
_PLACEHOLDER_VALUES = {
    "",
    "sk-your-key-here",
    "your-api-key",
    "[密钥]",
    "<YOUR_API_KEY>",
    "<YOUR_LLM_API_KEY>",
    "<YOUR_PERPLEXITY_API_KEY>",
    "YOUR_API_KEY",
}


def _load_env_file(path: Path) -> None:
    """Load env files without overriding variables already set by the shell."""
    if not path.exists():
        return
    loaded_any = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in _ORIGINAL_ENV:
            continue
        os.environ[key] = value
        loaded_any = True
    if loaded_any:
        _LOADED_ENV_FILES.append(str(path))


for _path in (ROOT / ".env", _GLOBAL_ENV_PATH, ROOT / ".env.local", ROOT / "secrets.env"):
    _load_env_file(_path)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    lowered = value.lower()
    if (
        value in _PLACEHOLDER_VALUES
        or (name.endswith("API_KEY") and ("your" in lowered or value.startswith("<") or value.startswith("[")))
    ):
        return default
    return value

SOURCE_WEIGHTS = {
    "exchange_filing": 1.0,
    "company_announcement": 1.0,
    "financial_report": 1.0,
    "company_ir": 0.85,
    "earnings_call": 0.85,
    "multi_broker_research": 0.7,
    "broker_research": 0.6,
    "industry_data": 0.6,
    "news": 0.45,
    "overseas_news": 0.45,
    "media": 0.4,
    "rumor": 0.25,
    "xiaozuowen": 0.25,
    "manual": 0.35,
    "search_api": 0.4,
}

SOURCE_LABELS = {
    "exchange_filing": "交易所文件",
    "company_announcement": "公司公告",
    "financial_report": "财报",
    "company_ir": "公司IR/调研",
    "earnings_call": "业绩会",
    "multi_broker_research": "多家券商研报",
    "broker_research": "券商研报",
    "industry_data": "产业数据",
    "news": "新闻",
    "overseas_news": "海外科技动态",
    "media": "产业媒体",
    "rumor": "传闻",
    "xiaozuowen": "小作文",
    "manual": "手动判断",
    "search_api": "搜索API",
}

IMPACT_DIRECTION_SCORES = {
    "strong_positive": 2,
    "positive": 1,
    "neutral": 0,
    "negative": -1,
    "strong_negative": -2,
    "unknown": 0,
}

IMPACT_DIRECTION_LABELS = {
    "strong_positive": "强利好",
    "positive": "利好",
    "neutral": "中性",
    "negative": "利空",
    "strong_negative": "强利空",
    "unknown": "待验证",
}

DEFAULT_EVENT_WEIGHT = 3

AI_KEYWORDS = [
    "AI", "人工智能", "大模型", "算力", "GPU", "英伟达", "NVDA",
    "光模块", "CPO", "服务器", "液冷", "数据中心", "IDC",
    "HBM", "先进封装", "机器人", "端侧AI", "AI PC", "AI手机",
    "Agent", "云计算", "推理", "训练", "芯片",
]

DATA_SOURCE_CONFIG = {
    "market_snapshot": ["akshare_market"],
    "news": ["eastmoney_flash", "akshare_news"],
    "search_enrichment": ["perplexity_search"],
    "announcement_index": ["akshare_announcements"],
}

ANNOUNCEMENT_CONFIG = {
    "lookback_days": int(_env("DAA_ANNOUNCEMENT_LOOKBACK_DAYS", "3") or 3),
    "max_items": int(_env("DAA_ANNOUNCEMENT_MAX_ITEMS", "80") or 80),
}


LLM_CONFIG = {
    "provider": _env("DAA_LLM_PROVIDER", "openai"),
    "api_key": _env("DAA_LLM_API_KEY", ""),
    "base_url": _env("DAA_LLM_BASE_URL", "https://api.openai.com/v1"),
    "deep_model": _env("DAA_DEEP_MODEL", "gpt-4o"),
    "quick_model": _env("DAA_QUICK_MODEL", "gpt-4o-mini"),
}

SEARCH_CONFIG = {
    "perplexity_api_key": _env("PERPLEXITY_API_KEY", ""),
    "perplexity_base_url": _env("PERPLEXITY_BASE_URL", "https://api.perplexity.ai"),
    "perplexity_model": _env("PERPLEXITY_MODEL", "sonar"),
}

ENV_CONFIG = {
    "global_env_path": str(_GLOBAL_ENV_PATH),
    "loaded_env_files": list(_LOADED_ENV_FILES),
}
