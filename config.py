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
INDUSTRY_CHAIN_DIR = ROOT / "industry_chain"

PROJECT_NAME = "每日AI产业链复盘"
PROJECT_SLUG = "daily-ai-chain-review"

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


LLM_CONFIG = {
    "provider": os.getenv("DAA_LLM_PROVIDER", "openai"),
    "api_key": os.getenv("DAA_LLM_API_KEY", ""),
    "base_url": os.getenv("DAA_LLM_BASE_URL", "https://api.openai.com/v1"),
    "deep_model": os.getenv("DAA_DEEP_MODEL", "gpt-4o"),
    "quick_model": os.getenv("DAA_QUICK_MODEL", "gpt-4o-mini"),
}
