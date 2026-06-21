# -*- coding: utf-8 -*-
"""Build compact notifications from generated daily review outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TIMESTAMP_RE = re.compile(r"_(\d{8}_\d{6})")


@dataclass
class ReviewArtifacts:
    analysis_path: Path | None
    report_path: Path | None
    market_sources_path: Path | None


def _token(path: Path | None) -> str:
    if not path:
        return ""
    match = TIMESTAMP_RE.search(path.stem)
    return match.group(1) if match else ""


def _match_file(output_dir: Path, prefix: str, token: str, suffix: str) -> Path | None:
    if not token:
        return None
    path = output_dir / f"{prefix}{token}{suffix}"
    return path if path.exists() else None


def latest_complete_artifacts(output_dir: Path, require_market_sources: bool = False) -> ReviewArtifacts:
    analyses = sorted(output_dir.glob("analysis_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for analysis_path in analyses:
        token = _token(analysis_path)
        report_path = _match_file(output_dir, "report_full_", token, ".html")
        market_path = _match_file(output_dir, "market_sources_", token, ".json")
        if not report_path:
            continue
        if require_market_sources and not market_path:
            continue
        return ReviewArtifacts(analysis_path, report_path, market_path)
    return ReviewArtifacts(None, None, None)


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _source_status(analysis: dict[str, Any], market_data: dict[str, Any]) -> list[dict[str, Any]]:
    status = analysis.get("data_source_status")
    if isinstance(status, list):
        return [item for item in status if isinstance(item, dict)]
    status = market_data.get("source_status")
    if isinstance(status, list):
        return [item for item in status if isinstance(item, dict)]
    return []


def _top_segments(analysis: dict[str, Any]) -> str:
    segments = analysis.get("summary", {}).get("top_segments", [])
    if not isinstance(segments, list):
        return "暂无"
    labels = [str(item.get("label") or "") for item in segments if isinstance(item, dict) and item.get("label")]
    return "、".join(labels[:3]) or "暂无"


def _provider_line(items: list[dict[str, Any]]) -> str:
    if not items:
        return "未启用自动数据源"
    counts = {"ok": 0, "empty": 0, "failed": 0}
    failed = []
    empty = []
    for item in items:
        status = str(item.get("status") or "")
        if status in counts:
            counts[status] += 1
        if status == "failed":
            failed.append(str(item.get("provider") or ""))
        elif status == "empty":
            empty.append(str(item.get("provider") or ""))
    parts = [f"ok={counts['ok']}", f"empty={counts['empty']}", f"failed={counts['failed']}"]
    if failed:
        parts.append("failed: " + "、".join(failed[:5]))
    elif empty:
        parts.append("empty: " + "、".join(empty[:5]))
    return "；".join(parts)


def _deep_agent_line(analysis: dict[str, Any]) -> str:
    multi_agent = analysis.get("multi_agent_analysis", {})
    if not isinstance(multi_agent, dict):
        return "missing"
    status = multi_agent.get("deep_agent_status", {})
    if not isinstance(status, dict):
        return str(multi_agent.get("mode") or "")
    mode = str(multi_agent.get("mode") or status.get("mode") or "")
    state = str(status.get("status") or "")
    return f"{mode}/{state}"


def build_notification(output_dir: Path, require_market_sources: bool = False) -> dict[str, Any]:
    artifacts = latest_complete_artifacts(output_dir, require_market_sources=require_market_sources)
    analysis = _read_json(artifacts.analysis_path)
    market_data = _read_json(artifacts.market_sources_path)
    summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}
    source_items = _source_status(analysis, market_data)
    generated_at = str(analysis.get("generated_at") or "")
    title = f"每日AI产业链复盘 {generated_at or datetime.now().strftime('%Y-%m-%d')}"
    report_path = str(artifacts.report_path) if artifacts.report_path else ""
    lines = [
        f"事件数：{summary.get('event_count', 0)}，利好：{summary.get('positive_count', 0)}，利空：{summary.get('negative_count', 0)}，验证池：{summary.get('verification_count', 0)}",
        f"今日主线：{_top_segments(analysis)}",
        f"多角色：{_deep_agent_line(analysis)}",
        f"数据源：{_provider_line(source_items)}",
        f"报告：{report_path or '未找到'}",
        "边界：研究辅助，不构成投资建议；低证据事件需公告/财报等高等级证据复核。",
    ]
    issues = []
    if not artifacts.analysis_path:
        issues.append("missing analysis")
    if not artifacts.report_path:
        issues.append("missing report")
    if require_market_sources and not source_items:
        issues.append("missing data-source status")
    return {
        "title": title,
        "text": "\n".join(lines),
        "artifacts": {
            "analysis_path": str(artifacts.analysis_path) if artifacts.analysis_path else "",
            "report_path": report_path,
            "market_sources_path": str(artifacts.market_sources_path) if artifacts.market_sources_path else "",
        },
        "summary": {
            "event_count": int(summary.get("event_count") or 0),
            "verification_count": int(summary.get("verification_count") or 0),
            "top_segments": _top_segments(analysis),
            "deep_agent": _deep_agent_line(analysis),
            "source_status": _provider_line(source_items),
        },
        "issues": issues,
    }
