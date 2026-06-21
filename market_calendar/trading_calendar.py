# -*- coding: utf-8 -*-
"""Trading-day and review-window governance."""

from __future__ import annotations

import json
from functools import lru_cache
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from config import TRADING_CALENDAR_CONFIG


DATE_FMT = "%Y-%m-%d"
CALENDAR_DIR = Path(__file__).resolve().parent / "calendars"


def _date_set(values: Any) -> set[date]:
    if not isinstance(values, list):
        return set()
    result = set()
    for value in values:
        try:
            result.add(datetime.strptime(str(value), DATE_FMT).date())
        except ValueError:
            continue
    return result


@lru_cache(maxsize=1)
def _bundled_calendar_dates() -> tuple[set[date], set[date], list[dict[str, Any]]]:
    holidays: set[date] = set()
    extra_days: set[date] = set()
    metadata: list[dict[str, Any]] = []
    if not CALENDAR_DIR.exists():
        return holidays, extra_days, metadata
    for path in sorted(CALENDAR_DIR.glob("cn_a_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        holidays |= _date_set(data.get("holidays", []))
        extra_days |= _date_set(data.get("extra_trading_days", []))
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        metadata.append(
            {
                "file": path.name,
                "market": str(data.get("market") or ""),
                "year": data.get("year"),
                "source_title": str(source.get("title") or ""),
                "source_url": str(source.get("url") or ""),
                "published_at": str(source.get("published_at") or ""),
                "holiday_count": len(data.get("holidays", [])) if isinstance(data.get("holidays"), list) else 0,
                "extra_trading_day_count": len(data.get("extra_trading_days", []))
                if isinstance(data.get("extra_trading_days"), list)
                else 0,
            }
        )
    return holidays, extra_days, metadata


def _parse_time(value: str, default: time) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return default


def is_trading_day(day: date) -> bool:
    bundled_holidays, bundled_extra_days, _metadata = _bundled_calendar_dates()
    holidays = bundled_holidays | _date_set(TRADING_CALENDAR_CONFIG.get("holidays", []))
    extra_days = bundled_extra_days | _date_set(TRADING_CALENDAR_CONFIG.get("extra_trading_days", []))
    if day in extra_days:
        return True
    if day in holidays:
        return False
    return day.weekday() < 5


def calendar_metadata() -> dict[str, Any]:
    holidays, extra_days, metadata = _bundled_calendar_dates()
    years = sorted({item.get("year") for item in metadata if item.get("year")})
    return {
        "market": str(TRADING_CALENDAR_CONFIG.get("market", "CN_A")),
        "calendar_dir": str(CALENDAR_DIR),
        "years": years,
        "holiday_count": len(holidays),
        "extra_trading_day_count": len(extra_days),
        "files": metadata,
        "source_title": "；".join(item.get("source_title", "") for item in metadata if item.get("source_title")),
        "source_url": "；".join(item.get("source_url", "") for item in metadata if item.get("source_url")),
        "env_holiday_count": len(_date_set(TRADING_CALENDAR_CONFIG.get("holidays", []))),
        "env_extra_trading_day_count": len(_date_set(TRADING_CALENDAR_CONFIG.get("extra_trading_days", []))),
    }


def previous_trading_day(day: date) -> date:
    cursor = day - timedelta(days=1)
    while not is_trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor


def latest_completed_trading_day(now: datetime | None = None) -> date:
    current = now or datetime.now()
    cutoff = _parse_time(str(TRADING_CALENDAR_CONFIG.get("review_ready_time", "17:00")), time(17, 0))
    day = current.date()
    if is_trading_day(day) and current.time() >= cutoff:
        return day
    return previous_trading_day(day)


def review_window_status(now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now()
    cutoff = _parse_time(str(TRADING_CALENDAR_CONFIG.get("review_ready_time", "17:00")), time(17, 0))
    day = current.date()
    trading_day = is_trading_day(day)
    ready = trading_day and current.time() >= cutoff
    target = latest_completed_trading_day(current)
    return {
        "now": current.strftime("%Y-%m-%d %H:%M:%S"),
        "today": day.strftime(DATE_FMT),
        "is_trading_day": trading_day,
        "review_ready_time": cutoff.strftime("%H:%M"),
        "is_review_window": ready,
        "target_review_date": target.strftime(DATE_FMT),
        "calendar_years": calendar_metadata().get("years", []),
        "note": "盘后窗口内" if ready else "使用最近已完成交易日",
    }


def ymd(day: date) -> str:
    return day.strftime("%Y%m%d")


def parse_review_date(value: str) -> date:
    text = str(value or "").strip()
    if not text:
        return latest_completed_trading_day()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid review date: {value}")
