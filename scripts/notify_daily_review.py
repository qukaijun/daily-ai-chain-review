# -*- coding: utf-8 -*-
"""Send or preview a compact daily-review notification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import NOTIFICATION_CONFIG, OUTPUT_DIR  # noqa: E402
from output.notification_builder import build_notification  # noqa: E402


def _mask_url(url: str) -> str:
    if not url:
        return ""
    if len(url) <= 16:
        return "*" * len(url)
    return url[:12] + "*" * (len(url) - 20) + url[-8:]


def _wecom_payload(notification: dict[str, Any]) -> dict[str, Any]:
    title = str(notification.get("title") or "每日AI产业链复盘")
    text = str(notification.get("text") or "")
    return {"msgtype": "markdown", "markdown": {"content": f"**{title}**\n\n{text}"}}


def _send_wecom(webhook_url: str, notification: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = requests.post(webhook_url, json=_wecom_payload(notification), timeout=timeout)
    if response.status_code >= 400:
        return {"status": "failed", "error": f"HTTP {response.status_code}: {response.text[:160]}"}
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:160]}
    errcode = data.get("errcode") if isinstance(data, dict) else None
    if errcode not in (None, 0):
        return {"status": "failed", "error": json.dumps(data, ensure_ascii=False)[:200]}
    return {"status": "sent", "response": data}


def _emit(notification: dict[str, Any]) -> None:
    severity = str(notification.get("severity") or "")
    kind = str(notification.get("kind") or "")
    print("=" * 60)
    print("  Daily Review Notification")
    print("=" * 60)
    print(f"[INFO] kind={kind} severity={severity}")
    print(notification.get("title", ""))
    print(str(notification.get("text") or ""))
    if notification.get("issues"):
        print("[WARN] issues: " + "；".join(str(item) for item in notification.get("issues", [])))


def main() -> int:
    parser = argparse.ArgumentParser(description="Notify Daily AI Chain Review summary")
    parser.add_argument("--provider", default=NOTIFICATION_CONFIG.get("provider", "console"), help="console or wecom")
    parser.add_argument("--send", action="store_true", help="Actually send to the configured provider")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, never send")
    parser.add_argument("--require-market-sources", action="store_true", help="Require market-source artifacts")
    parser.add_argument("--kind", choices=["auto", "success", "failure"], default="auto", help="Notification template")
    parser.add_argument("--json", action="store_true", help="Print notification JSON")
    args = parser.parse_args()

    notification = build_notification(
        OUTPUT_DIR,
        require_market_sources=args.require_market_sources,
        kind=args.kind,
    )
    if args.json:
        print(json.dumps(notification, ensure_ascii=False, indent=2))
    else:
        _emit(notification)

    if notification.get("issues"):
        return 0 if args.dry_run else 1

    provider = str(args.provider or "console").lower()
    enabled = bool(NOTIFICATION_CONFIG.get("enabled"))
    should_send = args.send and not args.dry_run and enabled
    if provider == "console" or not should_send:
        if provider != "console" and args.send and not enabled:
            print("[WARN] notification sending disabled; set DAA_NOTIFY_ENABLED=1 to send")
        return 0

    if provider == "wecom":
        webhook_url = str(NOTIFICATION_CONFIG.get("webhook_url") or "")
        if not webhook_url:
            print("[FAIL] DAA_NOTIFY_WEBHOOK_URL not configured")
            return 1
        result = _send_wecom(
            webhook_url,
            notification,
            int(NOTIFICATION_CONFIG.get("timeout_seconds") or 15),
        )
        print(f"[INFO] webhook={_mask_url(webhook_url)}")
        print(f"[INFO] send_status={result.get('status')}")
        if result.get("status") != "sent":
            print(f"[FAIL] {result.get('error', 'send failed')}")
            return 1
        return 0

    print(f"[FAIL] unsupported notification provider: {provider}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
