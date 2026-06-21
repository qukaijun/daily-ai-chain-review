# -*- coding: utf-8 -*-
"""Check automatic verification clusters without generating a full report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.event_loader import load_events  # noqa: E402
from graph.event_impact_engine import analyze_events  # noqa: E402


def main() -> int:
    events = load_events()
    analysis = analyze_events(events, enable_deep_agents=False)
    verification = analysis.get("verification_analysis", {})
    clusters = verification.get("clusters", [])

    print("=" * 60)
    print("  Verification Cluster Check")
    print("=" * 60)
    print(f"[INFO] events: {len(events)}")
    print(f"[INFO] clusters: {verification.get('cluster_count', 0)}")
    print(f"[INFO] duplicates: {verification.get('duplicate_count', 0)}")
    print(f"[INFO] high-evidence clusters: {verification.get('high_evidence_cluster_count', 0)}")
    for cluster in clusters[:5]:
        print(
            f"- {cluster.get('verification_score')}/100 "
            f"{cluster.get('verification_label')} "
            f"events={cluster.get('event_count')} "
            f"title={cluster.get('primary_title')}"
        )
    if not clusters and events:
        print("[FAIL] no verification clusters generated")
        return 1
    print("[OK] verification clusters generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
