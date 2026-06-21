# -*- coding: utf-8 -*-
"""Create a customer-safe diagnostics report without exposing secrets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output_files"
DIAGNOSTICS_DIR = OUTPUT_DIR / "diagnostics"


def _run(command: list[str], *, required: bool) -> dict[str, object]:
    started = time.time()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("DAA_GLOBAL_ENV_FILE", str(ROOT / "secrets" / "llm.env"))
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return {
        "command": command,
        "required": required,
        "returncode": result.returncode,
        "elapsed_seconds": round(time.time() - started, 2),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _latest_outputs() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for pattern in ("report_full_*.html", "report_single_*.html", "analysis_*.json", "market_sources_*.json"):
        files = sorted(OUTPUT_DIR.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)[:5]
        result[pattern] = [str(path.relative_to(ROOT)) for path in files]
    return result


def _write_text_report(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "Daily AI Chain Review Customer Diagnostics",
        f"Generated at: {payload['generated_at']}",
        f"Project root: {ROOT}",
        "",
        "Secret policy: full API keys, tokens and webhook URLs are not printed by this diagnostics script.",
        "",
        "Latest outputs:",
        json.dumps(payload["latest_outputs"], ensure_ascii=False, indent=2),
        "",
        "Command results:",
    ]
    for item in payload["commands"]:  # type: ignore[index]
        lines.extend(
            [
                "",
                "=" * 80,
                "COMMAND: " + " ".join(item["command"]),  # type: ignore[index]
                f"REQUIRED: {'yes' if item.get('required') else 'no'}",
                f"EXIT: {item['returncode']}  ELAPSED: {item['elapsed_seconds']}s",  # type: ignore[index]
                "- STDOUT -",
                str(item["stdout"]).rstrip(),  # type: ignore[index]
                "- STDERR -",
                str(item["stderr"]).rstrip(),  # type: ignore[index]
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export customer diagnostics for Daily AI Chain Review")
    parser.add_argument("--quick", action="store_true", help="Skip network/data-source checks")
    parser.add_argument("--output-dir", default=str(DIAGNOSTICS_DIR), help="Diagnostics output directory")
    args = parser.parse_args()

    commands: list[tuple[list[str], bool]] = [
        ([sys.executable, "--version"], True),
        ([sys.executable, "-m", "pip", "--version"], True),
        ([sys.executable, "scripts/health_check.py"], True),
        ([sys.executable, "scripts/check_secrets.py"], True),
        ([sys.executable, "scripts/check_search_config.py"], False),
        ([sys.executable, "scripts/check_deep_agent_config.py"], False),
    ]
    if not args.quick:
        commands.extend(
            [
                ([sys.executable, "scripts/check_data_sources.py"], False),
                ([sys.executable, "scripts/check_announcement_provider.py"], False),
            ]
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(ROOT),
        "quick": bool(args.quick),
        "latest_outputs": _latest_outputs(),
        "commands": [_run(command, required=required) for command, required in commands],
    }
    json_path = output_dir / f"diagnostics_{stamp}.json"
    txt_path = output_dir / f"diagnostics_{stamp}.txt"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_text_report(txt_path, payload)
    print(f"[OK] Diagnostics saved: {txt_path}")
    print(f"[OK] Diagnostics JSON: {json_path}")
    failed = [
        item for item in payload["commands"]  # type: ignore[index]
        if item["returncode"] != 0 and item.get("required")
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
