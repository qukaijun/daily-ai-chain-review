# -*- coding: utf-8 -*-
"""Run the daily review pipeline with logs and post-run QA."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output_files"
RUN_DIR = OUTPUT_DIR / "daily_runs"


def _command_label(args: list[str]) -> str:
    return " ".join(args)


def _run(args: list[str], log_file: Path) -> dict[str, Any]:
    started = datetime.now()
    start_ts = time.time()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    print(f"[RUN] {_command_label(args)}")
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    elapsed = round(time.time() - start_ts, 2)
    status = "ok" if result.returncode == 0 else "failed"
    print(f"[{status.upper()}] exit={result.returncode} elapsed={elapsed}s")
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())

    with log_file.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"COMMAND: {_command_label(args)}\n")
        f.write(f"STARTED: {started.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"EXIT: {result.returncode}\n")
        f.write(f"ELAPSED_SECONDS: {elapsed}\n")
        f.write("- STDOUT -\n")
        f.write(result.stdout or "")
        f.write("\n- STDERR -\n")
        f.write(result.stderr or "")
        f.write("\n")

    return {
        "command": args,
        "status": status,
        "returncode": result.returncode,
        "elapsed_seconds": elapsed,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _write_summary(summary_path: Path, payload: dict[str, Any]) -> None:
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = RUN_DIR / "latest_run.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Daily AI Chain Review with QA")
    parser.add_argument("--no-fetch-market", action="store_true", help="Generate report from local files only")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip input and project health checks")
    parser.add_argument("--skip-postflight", action="store_true", help="Skip latest report QA")
    parser.add_argument("--deep-agents", action="store_true", help="Enable optional LLM deep multi-agent review")
    parser.add_argument("--notify", action="store_true", help="Send configured notification after successful QA")
    parser.add_argument("--max-age-hours", type=float, default=36, help="Max report age accepted by postflight QA")
    args = parser.parse_args()

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = RUN_DIR / f"daily_review_{run_id}.log"
    summary_path = RUN_DIR / f"daily_review_{run_id}.json"

    commands: list[list[str]] = []
    if not args.skip_preflight:
        commands.extend(
            [
                [sys.executable, "scripts/health_check.py"],
                [sys.executable, "scripts/validate_events.py"],
                [sys.executable, "scripts/validate_verifications.py"],
                [sys.executable, "scripts/check_secrets.py"],
                [sys.executable, "scripts/check_multi_agent_layer.py"],
                [sys.executable, "scripts/check_deep_agent_config.py"],
                [sys.executable, "scripts/check_verification_clusters.py"],
            ]
        )

    main_cmd = [sys.executable, "main.py"]
    if not args.no_fetch_market:
        main_cmd.append("--fetch-market")
    if args.deep_agents:
        main_cmd.append("--deep-agents")
    commands.append(main_cmd)

    if not args.skip_postflight:
        postflight_cmd = [
            sys.executable,
            "scripts/check_latest_run.py",
            "--require-today",
            "--max-age-hours",
            str(args.max_age_hours),
        ]
        if not args.no_fetch_market:
            postflight_cmd.append("--require-market-sources")
        commands.append(postflight_cmd)
        if args.notify:
            notify_cmd = [sys.executable, "scripts/notify_daily_review.py", "--send"]
            if not args.no_fetch_market:
                notify_cmd.append("--require-market-sources")
            commands.append(notify_cmd)

    print("=" * 60)
    print("  Daily AI Chain Review Runner")
    print(f"  Run ID: {run_id}")
    print(f"  Log: {log_file}")
    print("=" * 60)

    results: list[dict[str, Any]] = []
    final_status = "ok"
    for command in commands:
        result = _run(command, log_file)
        results.append(result)
        if result["returncode"] != 0:
            final_status = "failed"
            break

    payload = {
        "run_id": run_id,
        "status": final_status,
        "started_at": run_id,
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "log_file": str(log_file),
        "notification_requested": bool(args.notify),
        "commands": results,
    }
    _write_summary(summary_path, payload)
    print("=" * 60)
    print(f"[{final_status.upper()}] daily review run summary: {summary_path}")
    print("=" * 60)
    return 0 if final_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
