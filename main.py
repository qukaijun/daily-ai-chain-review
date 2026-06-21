# -*- coding: utf-8 -*-
"""每日AI产业链复盘 - 主入口。

Usage:
    python main.py
    python main.py --output output_files/report_full_demo.html
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from config import OUTPUT_DIR
from data.ai_event_adapter import events_from_managed_sources
from data.event_loader import load_events
from data.providers import DataSourceManager
from data.verification_loader import apply_verification_updates, load_verification_updates
from graph.event_impact_engine import analyze_events
from output.html_renderer import render_report


def save_analysis(analysis: dict) -> str:
    path = OUTPUT_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
    print(f"[File] Analysis saved: {path}")
    return str(path)


def save_market_sources(data: dict) -> str:
    path = OUTPUT_DIR / f"market_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"[File] Source data saved: {path}")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily AI Chain Review")
    parser.add_argument("--output", type=str, default=None, help="Output HTML path")
    parser.add_argument("--fetch-market", action="store_true", help="Fetch managed market/news data sources")
    args = parser.parse_args()

    print("=" * 60)
    print("  Daily AI Chain Review")
    print(f"  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    events = load_events()
    print(f"[Data] Loaded manual/template events: {len(events)}")
    if args.fetch_market:
        print("[Data] Fetching managed data sources...")
        manager = DataSourceManager()
        source_data = manager.fetch_all_groups()
        save_market_sources(source_data)
        source_events = events_from_managed_sources(source_data)
        print(f"[Data] Source-derived AI events: {len(source_events)}")
        events.extend(source_events)

    verification_updates = load_verification_updates()
    events, verification_status = apply_verification_updates(events, verification_updates)
    print(
        "[Data] Verification write-backs: "
        f"{verification_status['applied_count']}/{verification_status['update_count']} applied"
    )
    if verification_status["unmatched_event_ids"]:
        preview = ", ".join(verification_status["unmatched_event_ids"][:5])
        print(f"[WARN] Verification updates not matched in this run: {preview}")

    if not events:
        print("[WARN] No events found. Add JSON files to data_sources/events.")

    analysis = analyze_events(events)
    analysis["verification_update_status"] = verification_status
    if args.fetch_market:
        analysis["data_source_status"] = source_data.get("source_status", [])
    save_analysis(analysis)

    html_path = args.output or str(OUTPUT_DIR / f"report_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    render_report(analysis, output_path=html_path)

    print("=" * 60)
    print("[Done] AI chain review generated")
    print(f"  HTML: {html_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
