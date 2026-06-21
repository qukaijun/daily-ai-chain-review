# -*- coding: utf-8 -*-
"""Check whether the latest generated review is usable."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market_calendar.trading_calendar import latest_completed_trading_day, parse_review_date, ymd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output_files"
TIMESTAMP_RE = re.compile(r"_(\d{8}_\d{6})")


def _latest(pattern: str) -> Path | None:
    files = sorted(OUTPUT_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _token(path: Path | None) -> str:
    if not path:
        return ""
    match = TIMESTAMP_RE.search(path.stem)
    return match.group(1) if match else ""


def _timestamp(path: Path | None) -> datetime | None:
    token = _token(path)
    if token:
        try:
            return datetime.strptime(token, "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    if path and path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime)
    return None


def _age_hours(path: Path | None) -> float:
    ts = _timestamp(path)
    if not ts:
        return 999999.0
    return (datetime.now() - ts).total_seconds() / 3600


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _match_file(prefix: str, token: str, suffix: str) -> Path | None:
    if not token:
        return None
    path = OUTPUT_DIR / f"{prefix}{token}{suffix}"
    return path if path.exists() else None


def _latest_complete_run(
    require_market_sources: bool = False,
    review_date: str = "",
) -> tuple[Path | None, Path | None, Path | None]:
    target_day = parse_review_date(review_date) if review_date else latest_completed_trading_day()
    target_ymd = ymd(target_day)
    analyses = sorted(OUTPUT_DIR.glob("analysis_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    latest = analyses[0] if analyses else None
    for analysis_path in analyses:
        token = _token(analysis_path)
        if target_ymd and not token.startswith(target_ymd):
            continue
        report_path = _match_file("report_full_", token, ".html")
        market_path = _match_file("market_sources_", token, ".json")
        if not report_path:
            continue
        if require_market_sources and not market_path:
            continue
        return analysis_path, report_path, market_path
    if not latest:
        return None, None, None
    token = _token(latest)
    return latest, _match_file("report_full_", token, ".html"), _match_file("market_sources_", token, ".json")


def _source_status(analysis: dict[str, Any], market_data: dict[str, Any]) -> list[dict[str, Any]]:
    status = analysis.get("data_source_status")
    if isinstance(status, list):
        return [item for item in status if isinstance(item, dict)]
    status = market_data.get("source_status")
    if isinstance(status, list):
        return [item for item in status if isinstance(item, dict)]
    return []


def _print_source_status(items: list[dict[str, Any]]) -> None:
    if not items:
        print("[INFO] source_status: none")
        return
    for item in items:
        provider = item.get("provider", "")
        status = str(item.get("status", "")).upper()
        layer = item.get("evidence_layer", "")
        error = item.get("error", "")
        print(f"[INFO] provider {provider}: {status} layer={layer} {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the latest Daily AI Chain Review output")
    parser.add_argument("--max-age-hours", type=float, default=36, help="Maximum allowed age for the latest analysis")
    parser.add_argument("--min-events", type=int, default=1, help="Minimum event count expected in the analysis")
    parser.add_argument("--require-today", action="store_true", help="Require the latest analysis timestamp to be today")
    parser.add_argument("--review-date", default="", help="Target review date YYYY-MM-DD; default latest completed trading day")
    parser.add_argument(
        "--require-market-sources",
        action="store_true",
        help="Require managed market source status from a --fetch-market run",
    )
    args = parser.parse_args()

    target_day = parse_review_date(args.review_date) if args.review_date else latest_completed_trading_day()
    analysis_path, report_path, market_path = _latest_complete_run(
        args.require_market_sources,
        review_date=target_day.strftime("%Y-%m-%d"),
    )
    analysis_token = _token(analysis_path)
    analysis = _read_json(analysis_path)
    market_data = _read_json(market_path)

    issues: list[str] = []
    warnings: list[str] = []

    print("=" * 60)
    print("  Latest Daily Review Check")
    print("=" * 60)
    print(f"[INFO] analysis: {analysis_path or '<missing>'}")
    print(f"[INFO] report:   {report_path or '<missing>'}")
    print(f"[INFO] sources:  {market_path or '<missing>'}")
    print(f"[INFO] target_review_date: {target_day.strftime('%Y-%m-%d')}")

    if not analysis_path:
        issues.append("missing analysis_*.json")
    elif _age_hours(analysis_path) > args.max_age_hours:
        issues.append(f"latest analysis is older than {args.max_age_hours:g} hours")

    analysis_ts = _timestamp(analysis_path)
    if args.require_today and analysis_ts and analysis_ts.strftime("%Y%m%d") != datetime.now().strftime("%Y%m%d"):
        issues.append(f"latest analysis is not from today: {analysis_ts.strftime('%Y-%m-%d')}")
    if analysis_ts and analysis_ts.strftime("%Y%m%d") != target_day.strftime("%Y%m%d"):
        issues.append(f"latest analysis is not from target review date: {analysis_ts.strftime('%Y-%m-%d')}")

    if not report_path or not report_path.exists():
        issues.append("missing matching report_full_*.html")
    elif _age_hours(report_path) > args.max_age_hours:
        issues.append(f"latest report is older than {args.max_age_hours:g} hours")

    event_count = int(analysis.get("summary", {}).get("event_count") or 0)
    verification_count = int(analysis.get("summary", {}).get("verification_count") or 0)
    print(f"[INFO] events={event_count} verification_pool={verification_count}")
    if event_count < args.min_events:
        issues.append(f"event_count {event_count} below minimum {args.min_events}")

    roles = analysis.get("multi_agent_analysis", {}).get("roles", [])
    multi_agent = analysis.get("multi_agent_analysis", {})
    deep_status = multi_agent.get("deep_agent_status", {}) if isinstance(multi_agent, dict) else {}
    role_count = len(roles) if isinstance(roles, list) else 0
    print(f"[INFO] multi_agent_mode={multi_agent.get('mode') if isinstance(multi_agent, dict) else ''}")
    print(f"[INFO] multi_agent_roles={role_count}")
    if isinstance(deep_status, dict):
        print(f"[INFO] deep_agent_status={deep_status.get('status', '')}")
    if role_count < 5:
        issues.append("multi_agent_analysis has fewer than 5 roles")
    if isinstance(multi_agent, dict) and not isinstance(deep_status, dict):
        issues.append("multi_agent_analysis missing deep_agent_status")

    clusters = analysis.get("verification_analysis", {}).get("clusters", [])
    cluster_count = len(clusters) if isinstance(clusters, list) else 0
    print(f"[INFO] verification_clusters={cluster_count}")

    if report_path and report_path.exists():
        html = report_path.read_text(encoding="utf-8", errors="replace")
        for marker in ("数据源状态", "自动验证与去重", "多角色复盘"):
            if marker not in html:
                issues.append(f"HTML missing section marker: {marker}")

    status_items = _source_status(analysis, market_data)
    _print_source_status(status_items)
    if args.require_market_sources and not status_items:
        issues.append("managed data-source status is missing")
    if status_items:
        ok_count = sum(1 for item in status_items if item.get("status") == "ok")
        failed = [str(item.get("provider", "")) for item in status_items if item.get("status") == "failed"]
        empty = [str(item.get("provider", "")) for item in status_items if item.get("status") == "empty"]
        print(f"[INFO] source_ok={ok_count} source_empty={len(empty)} source_failed={len(failed)}")
        if args.require_market_sources and ok_count == 0:
            issues.append("no managed data provider returned ok")
        if failed:
            warnings.append("failed providers: " + ", ".join(failed[:8]))
        if empty:
            warnings.append("empty providers: " + ", ".join(empty[:8]))

    for warning in warnings:
        print(f"[WARN] {warning}")
    if issues:
        print(f"[FAIL] {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[OK] latest daily review is usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
