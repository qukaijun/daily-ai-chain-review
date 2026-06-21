# -*- coding: utf-8 -*-
"""Data provider manager with fallback and status logging."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

import requests

from config import ANNOUNCEMENT_CONFIG, DATA_SOURCE_CONFIG, SEARCH_CONFIG
from graph.event_impact_engine import load_stock_pool


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ANNOUNCEMENT_DETAIL_URL = "https://np-cnotice-stock.eastmoney.com/api/content/ann"

PERPLEXITY_EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "published_at": {"type": "string"},
                    "source_name": {"type": "string"},
                    "source_url": {"type": "string"},
                    "summary": {"type": "string"},
                    "chain_segments": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "compute_chips",
                                "ai_servers",
                                "optical_modules",
                                "cooling_idc_power",
                                "cloud_models",
                                "ai_applications",
                                "edge_ai_robotics",
                            ],
                        },
                    },
                    "related_companies": {"type": "array", "items": {"type": "string"}},
                    "direction": {
                        "type": "string",
                        "enum": ["strong_positive", "positive", "neutral", "negative", "strong_negative", "unknown"],
                    },
                    "impact_reason": {"type": "string"},
                    "bull_case": {"type": "string"},
                    "bear_case": {"type": "string"},
                    "required_confirmation": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "published_at",
                    "source_name",
                    "source_url",
                    "summary",
                    "chain_segments",
                    "related_companies",
                    "direction",
                    "impact_reason",
                    "bull_case",
                    "bear_case",
                    "required_confirmation",
                    "confidence",
                    "citations",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}


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
            "akshare_announcements": self._akshare_announcements,
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
            evidence_layer = (
                "audit_source"
                if provider in {"akshare_announcements"}
                else "event"
                if provider in {"eastmoney_flash", "akshare_news", "perplexity_search"}
                else "candidate"
            )
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

    def _ai_stock_codes(self) -> set[str]:
        pool = load_stock_pool()
        codes: set[str] = set()
        for segment in pool.values():
            for stock in segment.get("stocks", []):
                market = str(stock.get("market", ""))
                code = str(stock.get("code", ""))
                if market == "A" and code:
                    codes.add(code)
        return codes

    def _announcement_code_from_url(self, url: str) -> str:
        match = re.search(r"/(AN\d+)\.html", url)
        return match.group(1) if match else ""

    def _parse_response_json(self, text: str) -> dict[str, Any]:
        payload = text.strip()
        if not payload:
            return {}
        if not payload.startswith("{"):
            match = re.search(r"^[^(]+\((.*)\)\s*;?$", payload, re.S)
            if match:
                payload = match.group(1)
        try:
            data = json.loads(payload)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _extract_fact_markers(self, text: str) -> dict[str, Any]:
        compact = re.sub(r"\s+", " ", text or "").strip()
        money = re.findall(r"(?:人民币)?\d+(?:\.\d+)?\s*(?:亿元|万元|元|港元|美元)", compact)
        percentages = re.findall(r"\d+(?:\.\d+)?\s*%", compact)
        dates = re.findall(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}-\d{1,2}-\d{1,2}", compact)
        return {
            "money": money[:8],
            "percentages": percentages[:8],
            "dates": dates[:8],
        }

    def _review_checklist(self, announcement_type: str, text: str) -> list[str]:
        base = [
            "核对公告原文与PDF链接是否一致",
            "核对公告日期、主体公司和证券代码",
            "判断是否与待验证事件存在直接关系",
        ]
        mapping = [
            (["回购"], ["核对回购金额区间、资金来源、用途和实施期限", "核对是否已实施而非仅为预案"]),
            (["股权激励"], ["核对授予对象、考核条件、摊销费用和稀释影响"]),
            (["中标", "合同", "订单"], ["核对合同金额、客户、产品、交付周期和收入确认条件"]),
            (["投资"], ["核对投资金额、项目周期、产能规划和资金来源"]),
            (["业绩"], ["核对利润口径、非经常损益和同比基数"]),
            (["风险", "诉讼", "处罚", "退市"], ["核对风险事项金额、进展阶段、可能损失和整改要求"]),
            (["减持", "增持"], ["核对股东身份、数量区间、价格条件和实施期限"]),
            (["质押", "冻结"], ["核对质押/冻结比例、到期日、平仓风险和解除条件"]),
        ]
        combined = f"{announcement_type} {text[:200]}"
        tasks = list(base)
        for keywords, additions in mapping:
            if any(keyword in combined for keyword in keywords):
                tasks.extend(additions)
        tasks.append("人工判断是否允许从公告候选升级为已验证证据")
        return tasks[:8]

    def _fetch_announcement_detail(self, art_code: str, referer: str) -> dict[str, Any]:
        if not art_code:
            return {"detail_status": "missing_art_code"}
        max_pages = max(int(ANNOUNCEMENT_CONFIG.get("detail_max_pages", 3)), 1)
        contents: list[str] = []
        first_data: dict[str, Any] = {}
        errors: list[str] = []
        pages = 1
        for page_index in range(1, max_pages + 1):
            try:
                response = requests.get(
                    ANNOUNCEMENT_DETAIL_URL,
                    params={"art_code": art_code, "client_source": "web", "page_index": page_index},
                    headers={"User-Agent": UA, "Referer": referer or "https://data.eastmoney.com/"},
                    timeout=15,
                )
                if response.status_code >= 400:
                    errors.append(f"HTTP {response.status_code}")
                    break
                payload = self._parse_response_json(response.text)
                data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
                if not data:
                    errors.append("empty data")
                    break
                if not first_data:
                    first_data = data
                    try:
                        pages = int(data.get("page_size") or 1)
                    except Exception:
                        pages = 1
                content = str(data.get("notice_content") or "").strip()
                if content:
                    contents.append(content)
                if page_index >= min(pages, max_pages):
                    break
            except Exception as exc:
                errors.append(str(exc)[:120])
                break

        full_text = "\n".join(contents).strip()
        if not first_data:
            return {"detail_status": "failed", "detail_error": "；".join(errors[:2])}
        fact_markers = self._extract_fact_markers(full_text)
        return {
            "detail_status": "ok" if full_text else "empty",
            "art_code": art_code,
            "notice_title": first_data.get("notice_title", ""),
            "notice_date": first_data.get("notice_date", ""),
            "pdf_url": first_data.get("attach_url_web") or first_data.get("attach_url") or "",
            "attach_type": first_data.get("attach_type", ""),
            "page_size": pages,
            "detail_pages_fetched": len(contents),
            "content_excerpt": full_text[:1200],
            "fact_markers": fact_markers,
            "detail_error": "；".join(errors[:2]),
        }

    def _akshare_announcements(self) -> dict[str, Any]:
        import akshare as ak

        from config import AI_KEYWORDS

        ai_codes = self._ai_stock_codes()
        lookback_days = max(int(ANNOUNCEMENT_CONFIG.get("lookback_days", 3)), 1)
        max_items = max(int(ANNOUNCEMENT_CONFIG.get("max_items", 80)), 1)
        fetch_detail = bool(ANNOUNCEMENT_CONFIG.get("fetch_detail", True))
        detail_max_items = max(int(ANNOUNCEMENT_CONFIG.get("detail_max_items", 12)), 0)
        items: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        fetch_errors: list[str] = []
        detail_count = 0

        for offset in range(lookback_days):
            day = datetime.now() - timedelta(days=offset)
            date_text = day.strftime("%Y%m%d")
            try:
                df = ak.stock_notice_report(symbol="全部", date=date_text)
            except Exception as exc:
                fetch_errors.append(f"{date_text}: {str(exc)[:120]}")
                continue
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                code = str(row.get("代码", "")).strip()
                title = str(row.get("公告标题", "")).strip()
                announce_type = str(row.get("公告类型", "")).strip()
                text = f"{title} {announce_type}"
                if code not in ai_codes and not any(keyword.lower() in text.lower() for keyword in AI_KEYWORDS):
                    continue
                url = str(row.get("网址", "")).strip()
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                item = {
                    "title": title,
                    "time": str(row.get("公告日期", date_text)),
                    "source": "东方财富公告大全",
                    "code": code,
                    "name": str(row.get("名称", "")).strip(),
                    "announcement_type": announce_type,
                    "url": url,
                    "date": date_text,
                }
                items.append(item)
                if fetch_detail and detail_count < detail_max_items:
                    art_code = self._announcement_code_from_url(url)
                    detail = self._fetch_announcement_detail(art_code, url)
                    item.update(detail)
                    item["review_checklist"] = self._review_checklist(
                        announce_type,
                        " ".join([title, str(detail.get("content_excerpt", ""))]),
                    )
                    detail_count += 1
                if len(items) >= max_items:
                    break
            if len(items) >= max_items:
                break

        result: dict[str, Any] = {
            "count": len(items),
            "items": items,
            "lookback_days": lookback_days,
            "max_items": max_items,
            "detail_count": detail_count,
            "detail_max_items": detail_max_items,
            "source": "akshare.stock_notice_report",
        }
        if fetch_errors:
            result["fetch_errors"] = fetch_errors[:5]
        if not items and fetch_errors:
            result["error"] = "；".join(fetch_errors[:2])
        return result

    def _parse_structured_content(self, content: str) -> tuple[dict[str, Any] | None, str]:
        text = content.strip()
        if not text:
            return None, "empty content"
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            parsed = json.loads(text)
        except Exception as exc:
            return None, f"json parse failed: {exc}"
        if not isinstance(parsed, dict) or not isinstance(parsed.get("events"), list):
            return None, "json shape missing events array"
        return parsed, ""

    def _build_perplexity_items(
        self,
        content: str,
        citations: list[Any],
        search_results: list[Any],
    ) -> tuple[list[dict[str, Any]], bool, str]:
        parsed, parse_error = self._parse_structured_content(content)
        if not parsed:
            return [], False, parse_error

        items: list[dict[str, Any]] = []
        for event in parsed.get("events", [])[:12]:
            if not isinstance(event, dict):
                continue
            event_citations = event.get("citations") if isinstance(event.get("citations"), list) else []
            items.append(
                {
                    "title": event.get("title", ""),
                    "time": event.get("published_at", ""),
                    "source": event.get("source_name", "Perplexity Sonar"),
                    "url": event.get("source_url", ""),
                    "summary": event.get("summary", ""),
                    "content": event.get("impact_reason", ""),
                    "chain_segments": event.get("chain_segments", []),
                    "related_companies": event.get("related_companies", []),
                    "direction": event.get("direction", "unknown"),
                    "bull_case": event.get("bull_case", ""),
                    "bear_case": event.get("bear_case", ""),
                    "required_confirmation": event.get("required_confirmation", ""),
                    "confidence": event.get("confidence", "low"),
                    "citations": event_citations or citations,
                    "search_results": search_results,
                    "structured": True,
                }
            )
        if not items:
            return [], False, "structured response contains no usable events"
        return items, True, ""

    def _post_perplexity(self, payload: dict[str, Any], api_key: str) -> requests.Response:
        url = SEARCH_CONFIG["perplexity_base_url"].rstrip("/") + "/chat/completions"
        return requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45,
        )

    def _perplexity_search(self) -> dict[str, Any]:
        api_key = SEARCH_CONFIG.get("perplexity_api_key", "")
        if not api_key:
            return {"count": 0, "items": [], "error": "PERPLEXITY_API_KEY not configured"}
        payload = {
            "model": SEARCH_CONFIG["perplexity_model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return structured AI industry-chain event candidates with citations. "
                        "Focus on facts, source dates, source URLs, affected segments, related companies, "
                        "and what still needs verification. Do not provide trading advice."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请检索最近24小时全球和中国AI产业链重要变化，覆盖算力、GPU/HBM、"
                        "AI服务器、光模块、液冷、数据中心、大模型、AI应用、机器人。"
                        "请返回 JSON 对象，字段为 events 数组；每条必须说明来源、时间、"
                        "source_url、影响环节、可能相关公司、利好/利空方向、正反影响和需要验证的证据。"
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_chain_events",
                    "schema": PERPLEXITY_EVENT_SCHEMA,
                },
            },
        }
        r = self._post_perplexity(payload, api_key)
        used_structured_request = True
        if r.status_code >= 400 and "response_format" in r.text:
            fallback_payload = dict(payload)
            fallback_payload.pop("response_format", None)
            r = self._post_perplexity(fallback_payload, api_key)
            used_structured_request = False
        if r.status_code >= 400:
            return {"count": 0, "items": [], "error": f"HTTP {r.status_code}: {r.text[:160]}"}
        data = r.json()
        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            content = json.dumps(data, ensure_ascii=False)[:2000]
        citations = data.get("citations", [])
        search_results = data.get("search_results", [])
        if not isinstance(citations, list):
            citations = []
        if not isinstance(search_results, list):
            search_results = []
        items, structured, parse_error = self._build_perplexity_items(content, citations, search_results)
        if items:
            return {
                "count": len(items),
                "items": items,
                "raw_content": content[:4000],
                "citations": citations,
                "search_results": search_results,
                "structured": structured,
                "used_structured_request": used_structured_request,
            }
        return {
            "count": 1,
            "items": [
                {
                    "title": "Perplexity AI产业链检索摘要",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "Perplexity Sonar",
                    "content": content,
                    "citations": citations,
                    "search_results": search_results,
                    "structured": False,
                }
            ],
            "raw_content": content[:4000],
            "citations": citations,
            "search_results": search_results,
            "structured": False,
            "used_structured_request": used_structured_request,
            "parse_error": parse_error,
        }
