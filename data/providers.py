# -*- coding: utf-8 -*-
"""Data provider manager with fallback and status logging."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import requests

from config import DATA_SOURCE_CONFIG, SEARCH_CONFIG


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class ProviderResult:
    provider: str
    status: str
    data: Any
    retrieved_at: str
    error: str = ""
    evidence_layer: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "data": self.data,
            "retrieved_at": self.retrieved_at,
            "error": self.error,
            "evidence_layer": self.evidence_layer,
        }


class DataSourceManager:
    """Try providers in configured order and keep failures visible."""

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], Any]] = {
            "akshare_market": self._akshare_market,
            "akshare_news": self._akshare_news,
            "eastmoney_flash": self._eastmoney_flash,
            "perplexity_search": self._perplexity_search,
        }
        self.status_log: list[dict[str, Any]] = []

    def fetch_first(self, source_group: str) -> ProviderResult:
        providers = DATA_SOURCE_CONFIG.get(source_group, [])
        if not providers:
            return self._result(source_group, "failed", {}, error="no providers configured")
        last_result: ProviderResult | None = None
        for provider in providers:
            result = self.fetch_provider(provider)
            if result.status == "ok":
                return result
            last_result = result
        return last_result or self._result(source_group, "failed", {}, error="no provider attempted")

    def fetch_group(self, source_group: str) -> ProviderResult:
        """Fetch a logical source group.

        Most groups use fallback-first semantics. Search enrichment is
        intentionally independent so a working news source does not prevent
        Perplexity from running when configured.
        """
        return self.fetch_first(source_group)

    def fetch_all_groups(self) -> dict[str, Any]:
        data = {}
        for group in DATA_SOURCE_CONFIG:
            data[group] = self.fetch_group(group).to_dict()
        data["source_status"] = self.status_log
        return data

    def fetch_provider(self, provider: str) -> ProviderResult:
        fn = self._providers.get(provider)
        if not fn:
            result = self._result(provider, "failed", {}, error="unknown provider")
            self.status_log.append(result.to_dict())
            return result
        try:
            data = fn()
            ok = bool(data) and not (isinstance(data, dict) and data.get("error"))
            status = "ok" if ok else "empty"
            error = data.get("error", "") if isinstance(data, dict) else ""
            evidence_layer = "event" if provider in {"eastmoney_flash", "akshare_news", "perplexity_search"} else "candidate"
            result = self._result(provider, status, data, error=error, evidence_layer=evidence_layer)
        except Exception as exc:
            result = self._result(provider, "failed", {}, error=str(exc)[:200])
        self.status_log.append(result.to_dict())
        return result

    def _result(
        self,
        provider: str,
        status: str,
        data: Any,
        *,
        error: str = "",
        evidence_layer: str = "candidate",
    ) -> ProviderResult:
        return ProviderResult(
            provider=provider,
            status=status,
            data=data,
            error=error,
            evidence_layer=evidence_layer,
            retrieved_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _akshare_market(self) -> dict[str, Any]:
        import akshare as ak

        result: dict[str, Any] = {"fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        try:
            board_df = ak.stock_board_change_em()
            top = []
            if board_df is not None and not board_df.empty:
                for _, row in board_df.nlargest(20, "涨跌幅").iterrows():
                    top.append(
                        {
                            "name": str(row.get("板块名称", "")),
                            "change_pct": float(row.get("涨跌幅", 0) or 0),
                            "main_flow": round(float(row.get("主力净流入", 0) or 0) / 1e4, 2),
                            "anomaly_count": int(row.get("板块异动总次数", 0) or 0),
                        }
                    )
            result["board_change"] = {"count": len(top), "top": top}
        except Exception as exc:
            result["board_change"] = {"count": 0, "top": [], "error": str(exc)[:200]}

        try:
            news_df = ak.stock_news_em()
            items = []
            if news_df is not None and not news_df.empty:
                for _, row in news_df.head(50).iterrows():
                    items.append(
                        {
                            "title": str(row.get("新闻标题", "")),
                            "time": str(row.get("发布时间", "")),
                            "source": str(row.get("文章来源", "")),
                        }
                    )
            result["news"] = {"count": len(items), "items": items}
        except Exception as exc:
            result["news"] = {"count": 0, "items": [], "error": str(exc)[:200]}
        return result

    def _akshare_news(self) -> dict[str, Any]:
        data = self._akshare_market()
        return data.get("news", {"count": 0, "items": []})

    def _eastmoney_flash(self) -> dict[str, Any]:
        url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_40_1_.html"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        json_str = re.search(r"ajaxResult=({.*})", r.text, re.DOTALL)
        if not json_str:
            return {"count": 0, "items": [], "error": "parse failed"}
        data = json.loads(json_str.group(1))
        items = []
        for item in data.get("LivesList", []):
            items.append(
                {
                    "title": item.get("title", item.get("digest", "")),
                    "time": item.get("showtime", item.get("ctime", "")),
                    "source": "东方财富快讯",
                    "url": item.get("url_w", ""),
                }
            )
        return {"count": len(items), "items": items}

    def _perplexity_search(self) -> dict[str, Any]:
        api_key = SEARCH_CONFIG.get("perplexity_api_key", "")
        if not api_key:
            return {"count": 0, "items": [], "error": "PERPLEXITY_API_KEY not configured"}
        url = SEARCH_CONFIG["perplexity_base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": SEARCH_CONFIG["perplexity_model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return concise AI industry-chain news with source citations. "
                        "Focus on facts, source dates, and what still needs verification. "
                        "Do not provide trading advice."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请检索最近24小时全球和中国AI产业链重要变化，覆盖算力、GPU/HBM、"
                        "AI服务器、光模块、液冷、数据中心、大模型、AI应用、机器人。"
                        "每条请说明来源、时间、影响环节、可能相关公司和需要验证的证据。"
                    ),
                },
            ],
        }
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            return {"count": 0, "items": [], "error": f"HTTP {r.status_code}: {r.text[:160]}"}
        data = r.json()
        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            content = json.dumps(data, ensure_ascii=False)[:2000]
        citations = data.get("citations", [])
        return {
            "count": 1,
            "items": [
                {
                    "title": "Perplexity AI产业链检索摘要",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "Perplexity Sonar",
                    "content": content,
                    "citations": citations,
                }
            ],
        }
