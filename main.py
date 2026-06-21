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
from data.event_loader import load_events
from graph.event_impact_engine import analyze_events
from output.html_renderer import render_report


def save_analysis(analysis: dict) -> str:
    path = OUTPUT_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
    print(f"[File] Analysis saved: {path}")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily AI Chain Review")
    parser.add_argument("--output", type=str, default=None, help="Output HTML path")
    args = parser.parse_args()

    print("=" * 60)
    print("  Daily AI Chain Review")
    print(f"  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    events = load_events()
    print(f"[Data] Loaded events: {len(events)}")
    if not events:
        print("[WARN] No events found. Add JSON files to data_sources/events.")

    analysis = analyze_events(events)
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
