# -*- coding: utf-8 -*-
"""Check deterministic multi-role analysis output."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.event_loader import load_events  # noqa: E402
from graph.event_impact_engine import analyze_events  # noqa: E402


def main() -> int:
    analysis = analyze_events(load_events(), enable_deep_agents=False)
    multi_agent = analysis.get("multi_agent_analysis", {})
    roles = multi_agent.get("roles", [])

    print("=" * 60)
    print("  Multi-Agent Layer Check")
    print("=" * 60)
    print(f"[INFO] mode: {multi_agent.get('mode')}")
    print(f"[INFO] roles: {len(roles)}")
    for role in roles:
        print(f"- {role.get('role_name')}: {role.get('stance')}")
    if len(roles) < 5:
        print("[FAIL] expected at least 5 role outputs")
        return 1
    print("[OK] multi-agent layer generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
