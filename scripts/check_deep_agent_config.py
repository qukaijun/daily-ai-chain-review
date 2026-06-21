# -*- coding: utf-8 -*-
"""Check optional LLM deep-agent configuration without exposing secrets."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import ENV_CONFIG, LLM_CONFIG  # noqa: E402
from data.event_loader import load_events  # noqa: E402
from graph.event_impact_engine import analyze_events  # noqa: E402


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _check_shape(label: str, multi_agent: dict) -> int:
    roles = multi_agent.get("roles", [])
    status = multi_agent.get("deep_agent_status", {})
    print(f"[INFO] {label} mode: {multi_agent.get('mode')}")
    print(f"[INFO] {label} roles: {len(roles) if isinstance(roles, list) else 0}")
    print(f"[INFO] {label} deep_status: {status.get('status') if isinstance(status, dict) else ''}")
    if not isinstance(roles, list) or len(roles) < 5:
        print(f"[FAIL] {label} expected at least 5 roles")
        return 1
    if not isinstance(status, dict):
        print(f"[FAIL] {label} missing deep_agent_status")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check optional deep-agent config")
    parser.add_argument("--live", action="store_true", help="Allow a real LLM call when a key is configured")
    args = parser.parse_args()

    key = str(LLM_CONFIG.get("api_key", ""))
    print("=" * 60)
    print("  Deep Agent Config Check")
    print("=" * 60)
    print(f"[INFO] global_env_path: {ENV_CONFIG.get('global_env_path')}")
    print(f"[INFO] loaded_env_files: {ENV_CONFIG.get('loaded_env_files')}")
    print(f"[INFO] provider: {LLM_CONFIG.get('provider')}")
    print(f"[INFO] base_url: {LLM_CONFIG.get('base_url')}")
    print(f"[INFO] deep_model: {LLM_CONFIG.get('deep_model')}")
    print(f"[INFO] enable_deep_agents_default: {LLM_CONFIG.get('enable_deep_agents')}")
    if key:
        print(f"[OK] DAA_LLM_API_KEY present length={len(key)} masked={mask_key(key)}")
    else:
        print("[WARN] DAA_LLM_API_KEY not configured; deep agents will use deterministic fallback")

    events = load_events()
    issues = 0
    local = analyze_events(events, enable_deep_agents=False).get("multi_agent_analysis", {})
    issues += _check_shape("local", local)
    original_key = os.environ.get("DAA_LLM_API_KEY")
    if key and not args.live:
        os.environ["DAA_LLM_API_KEY"] = ""
        LLM_CONFIG["api_key"] = ""
    fallback = analyze_events(events, enable_deep_agents=True).get("multi_agent_analysis", {})
    if key and not args.live:
        if original_key is None:
            os.environ.pop("DAA_LLM_API_KEY", None)
        else:
            os.environ["DAA_LLM_API_KEY"] = original_key
        LLM_CONFIG["api_key"] = key
    issues += _check_shape("deep_requested", fallback)

    if not args.live and fallback.get("mode") != "deterministic_fallback":
        print("[FAIL] expected deterministic_fallback when deep agents are requested without key")
        issues += 1
    if issues:
        print(f"[FAIL] {issues} issue(s)")
        return 1
    print("[OK] deep-agent config is safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
