# -*- coding: utf-8 -*-
"""Check search provider config without exposing secrets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import ENV_CONFIG, SEARCH_CONFIG  # noqa: E402


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def main() -> int:
    key = SEARCH_CONFIG.get("perplexity_api_key", "")
    print("=" * 60)
    print("  Search Provider Config")
    print("=" * 60)
    print(f"[INFO] global_env_path: {ENV_CONFIG.get('global_env_path')}")
    print(f"[INFO] loaded_env_files: {ENV_CONFIG.get('loaded_env_files')}")
    print(f"[INFO] Perplexity Base URL: {SEARCH_CONFIG.get('perplexity_base_url')}")
    print(f"[INFO] Perplexity Model: {SEARCH_CONFIG.get('perplexity_model')}")
    if key:
        print(f"[OK] PERPLEXITY_API_KEY present length={len(key)} masked={mask_key(key)}")
        return 0
    print("[WARN] PERPLEXITY_API_KEY not configured")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
