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


def _latest_run_path(output_dir: Path) -> Path:
    return output_dir / "daily_runs" / "latest_run.json"


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
        text = path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception:
            return {}
    try:
        data = json.loads(text.lstrip("\ufeff"))
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


def _severity_from_daily(issues: list[str], source_items: list[dict[str, Any]]) -> str:
    if issues:
        return "failure"
    failed_count = sum(1 for item in source_items if item.get("status") == "failed")
    empty_count = sum(1 for item in source_items if item.get("status") == "empty")
    if failed_count or empty_count:
        return "warning"
    return "success"


def _prefix(severity: str) -> str:
    return {
        "success": "[成功]",
        "warning": "[注意]",
        "failure": "[失败]",
    }.get(severity, "[通知]")


def _read_log_tail(path_text: str, limit: int = 900) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:].strip()


def _failed_command(run_data: dict[str, Any]) -> dict[str, Any]:
    commands = run_data.get("commands", [])
    if not isinstance(commands, list):
        return {}
    for command in commands:
        if isinstance(command, dict) and int(command.get("returncode") or 0) != 0:
            return command
    return {}


def build_daily_notification(output_dir: Path, require_market_sources: bool = False) -> dict[str, Any]:
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
    severity = _severity_from_daily(issues, source_items)
    title = f"{_prefix(severity)} {title}"
    return {
        "kind": "daily",
        "severity": severity,
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


def build_failure_notification(output_dir: Path) -> dict[str, Any]:
    run_path = _latest_run_path(output_dir)
    run_data = _read_json(run_path)
    failed = _failed_command(run_data)
    command = " ".join(str(part) for part in failed.get("command", [])) if failed else ""
    log_file = str(run_data.get("log_file") or "")
    is_failed = bool(failed) or run_data.get("status") == "failed"
    tail = _read_log_tail(log_file) if is_failed else ""
    title = f"{_prefix('failure')} 每日AI产业链复盘自动运行失败"
    lines = [
        f"run_id：{run_data.get('run_id', '')}",
        f"状态：{run_data.get('status', 'unknown')}",
        f"失败命令：{command or '未定位'}",
        f"退出码：{failed.get('returncode', '') if failed else ''}",
        f"日志：{log_file or '未找到'}",
    ]
    if tail:
        lines.append("日志尾部：")
        lines.append(tail)
    issues = []
    if not run_data:
        issues.append("missing latest_run.json")
    elif not failed and run_data.get("status") != "failed":
        issues.append("latest run is not failed")
    return {
        "kind": "failure",
        "severity": "failure",
        "title": title,
        "text": "\n".join(lines),
        "artifacts": {
            "latest_run_path": str(run_path),
            "log_file": log_file,
        },
        "summary": {
            "run_id": str(run_data.get("run_id") or ""),
            "failed_command": command,
            "returncode": int(failed.get("returncode") or 0) if failed else 0,
        },
        "issues": issues,
    }


def build_notification(
    output_dir: Path,
    require_market_sources: bool = False,
    kind: str = "auto",
) -> dict[str, Any]:
    if kind == "failure":
        return build_failure_notification(output_dir)
    if kind == "success":
        return build_daily_notification(output_dir, require_market_sources=require_market_sources)
    run_data = _read_json(_latest_run_path(output_dir))
    if run_data.get("status") == "failed":
        return build_failure_notification(output_dir)
    return build_daily_notification(output_dir, require_market_sources=require_market_sources)
