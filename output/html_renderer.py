# -*- coding: utf-8 -*-
"""Render AI chain review HTML."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tag_class(score: float) -> str:
    if score > 0:
        return "tag-up"
    if score < 0:
        return "tag-down"
    return "tag-neutral"


def _status_tag_class(status: str) -> str:
    if status in {"confirmed", "upgraded", "not_required"}:
        return "tag-up"
    if status in {"rejected", "expired"}:
        return "tag-down"
    return "tag-warn"


def _source_link(event: dict[str, Any]) -> str:
    url = str(event.get("source_url") or "").strip()
    if not url:
        return ""
    return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">来源</a>'


def _events_rows(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<tr><td colspan="11">暂无事件</td></tr>'
    rows = []
    for event in events:
        score = float(event.get("score", 0))
        quality = event.get("source_quality", {})
        provider = event.get("provider") or event.get("_source_file") or event.get("source_bucket") or "manual"
        status = str(event.get("verification_status") or "not_required")
        status_label = str(event.get("verification_status_label") or status)
        stocks = "、".join(
            f'{s.get("name", "")}({s.get("code", "")})'
            for s in event.get("related_stocks", [])[:8]
        )
        rows.append(
            "<tr>"
            f"<td>{_esc(event.get('published_at', ''))}</td>"
            f"<td>{_esc(event.get('title', ''))}</td>"
            f"<td>{_esc(quality.get('label', event.get('source_type', '')))}</td>"
            f"<td>{_esc(provider)}</td>"
            f"<td><span class=\"tag {_tag_class(score)}\">{_esc(event.get('direction_label'))}</span></td>"
            f"<td>{_esc('、'.join(event.get('chain_labels', [])))}</td>"
            f"<td>{_esc(stocks)}</td>"
            f"<td>{score:+.2f}</td>"
            f"<td><span class=\"tag {_status_tag_class(status)}\">{_esc(status_label)}</span></td>"
            f"<td>{_esc(event.get('required_confirmation', ''))}</td>"
            f"<td>{_source_link(event)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _source_status_rows(status_items: list[dict[str, Any]]) -> str:
    if not status_items:
        return '<tr><td colspan="6">未启用自动数据源；当前报告仅使用本地事件文件。</td></tr>'
    rows = []
    for item in status_items:
        status = str(item.get("status", ""))
        tag = "tag-up" if status == "ok" else ("tag-neutral" if status == "empty" else "tag-down")
        data = item.get("data", {})
        if isinstance(data, dict):
            count = data.get("count", "")
            if count == "" and isinstance(data.get("news"), dict):
                count = data.get("news", {}).get("count", "")
            if count == "" and isinstance(data.get("board_change"), dict):
                count = data.get("board_change", {}).get("count", "")
        else:
            count = ""
        rows.append(
            "<tr>"
            f"<td>{_esc(item.get('provider'))}</td>"
            f"<td><span class=\"tag {tag}\">{_esc(status)}</span></td>"
            f"<td>{_esc(item.get('evidence_layer'))}</td>"
            f"<td>{_esc(item.get('retrieved_at'))}</td>"
            f"<td>{_esc(count)}</td>"
            f"<td>{_esc(item.get('error'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _segment_cards(segments: list[dict[str, Any]]) -> str:
    cards = []
    for seg in segments:
        score = float(seg.get("score", 0))
        cards.append(
            f'<div class="metric-card {("positive" if score > 0 else "negative" if score < 0 else "neutral")}">'
            f'<div class="metric-title">{_esc(seg.get("label"))}</div>'
            f'<div class="metric-value">{score:+.2f}</div>'
            f'<div class="metric-sub">{_esc(seg.get("direction"))}</div>'
            f'<p>{_esc(seg.get("description"))}</p>'
            "</div>"
        )
    return "\n".join(cards)


def _stock_rows(stocks: list[dict[str, Any]]) -> str:
    if not stocks:
        return '<tr><td colspan="6">暂无个股影响</td></tr>'
    rows = []
    for stock in stocks:
        score = float(stock.get("score", 0))
        rows.append(
            "<tr>"
            f"<td>{_esc(stock.get('market'))}</td>"
            f"<td>{_esc(stock.get('code'))}</td>"
            f"<td>{_esc(stock.get('name'))}</td>"
            f"<td>{_esc(stock.get('segment_label'))}</td>"
            f"<td><span class=\"tag {_tag_class(score)}\">{_esc(stock.get('direction'))}</span></td>"
            f"<td>{score:+.2f}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _verification_cards(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<div class="empty">暂无待验证小作文或低证据事件</div>'
    cards = []
    for event in events:
        quality = event.get("source_quality", {})
        status = str(event.get("verification_status") or "pending")
        source_link = _source_link(event)
        citation_note = str(event.get("citation_note") or "")
        cards.append(
            '<div class="verification-card">'
            f'<div class="card-top"><span class="tag tag-warn">{_esc(quality.get("tier"))}</span>'
            f'<span>{_esc(quality.get("label"))}</span>'
            f'<span class="tag {_status_tag_class(status)}">{_esc(event.get("verification_status_label", status))}</span></div>'
            f'<h3>{_esc(event.get("title"))}</h3>'
            f'<p>{_esc(event.get("summary"))}</p>'
            f'<div class="verify-action">验证：{_esc(event.get("required_confirmation"))}</div>'
            f'<div class="verify-policy">{_esc(event.get("verification_policy_note", ""))}</div>'
            f'<div class="source-note">{source_link} {_esc(citation_note[:240])}</div>'
            "</div>"
        )
    return "\n".join(cards)


def render_report(analysis: dict[str, Any], output_path: str | Path | None = None) -> str:
    template_path = ROOT / "templates" / "dashboard.html"
    template = template_path.read_text(encoding="utf-8")
    summary = analysis.get("summary", {})
    top_segments = summary.get("top_segments", [])
    mainline = "、".join(s.get("label", "") for s in top_segments) or "暂无主线"

    reps = {
        "{{GENERATED_AT}}": analysis.get("generated_at", ""),
        "{{EVENT_COUNT}}": str(summary.get("event_count", 0)),
        "{{POSITIVE_COUNT}}": str(summary.get("positive_count", 0)),
        "{{NEGATIVE_COUNT}}": str(summary.get("negative_count", 0)),
        "{{VERIFY_COUNT}}": str(summary.get("verification_count", 0)),
        "{{MAINLINE}}": _esc(mainline),
        "{{SEGMENT_CARDS}}": _segment_cards(analysis.get("segment_heat", [])),
        "{{EVENT_ROWS}}": _events_rows(analysis.get("events", [])),
        "{{SOURCE_STATUS_ROWS}}": _source_status_rows(analysis.get("data_source_status", [])),
        "{{STOCK_ROWS}}": _stock_rows(analysis.get("stock_impact", [])),
        "{{VERIFICATION_CARDS}}": _verification_cards(analysis.get("verification_pool", [])),
        "{{SEGMENT_LABELS_JSON}}": json.dumps([s.get("label", "") for s in analysis.get("segment_heat", [])], ensure_ascii=False),
        "{{SEGMENT_SCORES_JSON}}": json.dumps([s.get("score", 0) for s in analysis.get("segment_heat", [])], ensure_ascii=False),
        "{{SEGMENT_COLORS_JSON}}": json.dumps([
            "#4D8F71" if float(s.get("score", 0)) > 0 else "#B94B42" if float(s.get("score", 0)) < 0 else "#8A817A"
            for s in analysis.get("segment_heat", [])
        ], ensure_ascii=False),
    }

    html = template
    for key, value in reps.items():
        html = html.replace(key, str(value))

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        chart_src = ROOT / "templates" / "chartjs.min.js"
        chart_dst = path.parent / "chartjs.min.js"
        if chart_src.exists() and not chart_dst.exists():
            shutil.copy2(chart_src, chart_dst)
        print(f"[HTML] Report saved: {path}")
    return html
