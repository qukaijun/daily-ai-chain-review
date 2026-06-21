# -*- coding: utf-8 -*-
"""Scan tracked files for likely API keys."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SECRET_PATTERNS = [re.compile(r"sk-[A-Za-z0-9_-]{20,}")]
ALLOWLIST = {"sk-your-key-here"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    findings = []
    for path in tracked_files():
        if not path.exists() or b"\0" in path.read_bytes()[:2048]:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                if value in ALLOWLIST:
                    continue
                findings.append((rel, text.count("\n", 0, match.start()) + 1))
    if findings:
        print("[FAIL] possible secrets")
        for rel, line in findings:
            print(f"- {rel}:{line}")
        return 1
    print("[OK] No tracked secrets found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
