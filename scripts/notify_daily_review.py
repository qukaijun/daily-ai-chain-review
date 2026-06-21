# -*- coding: utf-8 -*-
"""Send or preview a compact daily-review notification."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import NOTIFICATION_CONFIG, OUTPUT_DIR  # noqa: E402
from output.notification_builder import build_notification  # noqa: E402

LOG_DIR = OUTPUT_DIR / "notification_logs"


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
    try:
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
    except Exception as exc:
        return {"status": "failed", "error": str(exc)[:200]}


def _send_with_retries(provider: str, webhook_url: str, notification: dict[str, Any]) -> dict[str, Any]:
    max_retries = max(int(NOTIFICATION_CONFIG.get("max_retries") or 0), 0)
    backoff = max(float(NOTIFICATION_CONFIG.get("retry_backoff_seconds") or 0), 0)
    attempts = []
    for attempt in range(max_retries + 1):
        if provider == "wecom":
            result = _send_wecom(
                webhook_url,
                notification,
                int(NOTIFICATION_CONFIG.get("timeout_seconds") or 15),
            )
        else:
            result = {"status": "failed", "error": f"unsupported notification provider: {provider}"}
        result["attempt"] = attempt + 1
        attempts.append(result)
        if result.get("status") == "sent":
            return {"status": "sent", "attempts": attempts, "attempt_count": len(attempts)}
        if attempt < max_retries and backoff:
            time.sleep(backoff * (2 ** attempt))
    return {"status": "failed", "attempts": attempts, "attempt_count": len(attempts)}


def _write_delivery_log(
    notification: dict[str, Any],
    *,
    provider: str,
    requested_send: bool,
    enabled: bool,
    result: dict[str, Any],
    webhook_url: str = "",
) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    log_path = LOG_DIR / f"notification_{now.strftime('%Y%m%d')}.jsonl"
    attempts = result.get("attempts", []) if isinstance(result.get("attempts"), list) else []
    last_attempt = attempts[-1] if attempts else {}
    record = {
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "provider": provider,
        "webhook": _mask_url(webhook_url),
        "requested_send": requested_send,
        "enabled": enabled,
        "delivery_status": result.get("status", "preview"),
        "attempt_count": int(result.get("attempt_count") or 0),
        "last_error": str(last_attempt.get("error") or result.get("error") or "")[:240],
        "kind": notification.get("kind", ""),
        "severity": notification.get("severity", ""),
        "title": notification.get("title", ""),
        "issues": notification.get("issues", []),
        "artifacts": notification.get("artifacts", {}),
        "summary": notification.get("summary", {}),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log_path


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
        log_path = _write_delivery_log(
            notification,
            provider=provider,
            requested_send=bool(args.send),
            enabled=enabled,
            result={"status": "preview" if not should_send else "skipped", "attempt_count": 0},
        )
        print(f"[INFO] delivery_log={log_path}")
        return 0

    if provider == "wecom":
        webhook_url = str(NOTIFICATION_CONFIG.get("webhook_url") or "")
        if not webhook_url:
            print("[FAIL] DAA_NOTIFY_WEBHOOK_URL not configured")
            log_path = _write_delivery_log(
                notification,
                provider=provider,
                requested_send=bool(args.send),
                enabled=enabled,
                result={"status": "failed", "error": "DAA_NOTIFY_WEBHOOK_URL not configured", "attempt_count": 0},
            )
            print(f"[INFO] delivery_log={log_path}")
            return 1
        result = _send_with_retries(provider, webhook_url, notification)
        print(f"[INFO] webhook={_mask_url(webhook_url)}")
        print(f"[INFO] send_status={result.get('status')}")
        print(f"[INFO] attempts={result.get('attempt_count')}")
        log_path = _write_delivery_log(
            notification,
            provider=provider,
            requested_send=bool(args.send),
            enabled=enabled,
            result=result,
            webhook_url=webhook_url,
        )
        print(f"[INFO] delivery_log={log_path}")
        if result.get("status") != "sent":
            attempts = result.get("attempts", []) if isinstance(result.get("attempts"), list) else []
            last_error = attempts[-1].get("error", "send failed") if attempts else "send failed"
            print(f"[FAIL] {last_error}")
            return 1
        return 0

    print(f"[FAIL] unsupported notification provider: {provider}")
    log_path = _write_delivery_log(
        notification,
        provider=provider,
        requested_send=bool(args.send),
        enabled=enabled,
        result={"status": "failed", "error": f"unsupported notification provider: {provider}", "attempt_count": 0},
    )
    print(f"[INFO] delivery_log={log_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
