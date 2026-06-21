# -*- coding: utf-8 -*-
"""Lightweight trading-day and review-window governance."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from config import TRADING_CALENDAR_CONFIG


DATE_FMT = "%Y-%m-%d"


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


def _parse_time(value: str, default: time) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return default


def is_trading_day(day: date) -> bool:
    holidays = _date_set(TRADING_CALENDAR_CONFIG.get("holidays", []))
    extra_days = _date_set(TRADING_CALENDAR_CONFIG.get("extra_trading_days", []))
    if day in extra_days:
        return True
    if day in holidays:
        return False
    return day.weekday() < 5


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
