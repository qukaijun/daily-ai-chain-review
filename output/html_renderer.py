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
    url = str(event.get("pdf_url") or event.get("source_url") or "").strip()
    if not url:
        return ""
    label = "PDF" if event.get("pdf_url") else "来源"
    return f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def _manual_verification_html(event: dict[str, Any]) -> str:
    manual = event.get("manual_verification")
    if not isinstance(manual, dict):
        return ""
    note = str(manual.get("decision_note") or "").strip()
    confirmed_by = str(manual.get("confirmed_by") or "").strip()
    confirmed_at = str(manual.get("confirmed_at") or "").strip()
    evidence_source_type = str(manual.get("evidence_source_type") or "").strip()
    evidence_title = str(manual.get("evidence_title") or "").strip()
    evidence_url = str(manual.get("evidence_url") or "").strip()
    evidence_pdf_url = str(manual.get("evidence_pdf_url") or "").strip()
    meta = " / ".join(part for part in (confirmed_by, confirmed_at) if part)
    links = []
    if evidence_title:
        if evidence_url:
            links.append(
                f'<a href="{_esc(evidence_url)}" target="_blank" rel="noopener noreferrer">{_esc(evidence_title)}</a>'
            )
        else:
            links.append(_esc(evidence_title))
    if evidence_pdf_url:
        links.append(f'<a href="{_esc(evidence_pdf_url)}" target="_blank" rel="noopener noreferrer">证据PDF</a>')
    link_html = "；".join(links)
    source_note = f"证据类型：{_esc(evidence_source_type)}" if evidence_source_type else ""
    body = "；".join(part for part in (meta, source_note, link_html, _esc(note)) if part)
    if not body:
        body = "已写入人工确认记录"
    return f'<div class="manual-verification">人工确认：{body}</div>'


def _fact_markers_text(markers: Any) -> str:
    if not isinstance(markers, dict):
        return ""
    parts = []
    labels = {"money": "金额", "percentages": "比例", "dates": "日期"}
    for key in ("money", "percentages", "dates"):
        values = markers.get(key, [])
        if isinstance(values, list) and values:
            parts.append(f"{labels[key]}：" + "、".join(str(v) for v in values[:4]))
    return "；".join(parts)


def _review_checklist_html(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    lis = "".join(f"<li>{_esc(item)}</li>" for item in items[:5])
    return f'<ul class="review-checklist">{lis}</ul>'


def _upgrade_evidence_note(event: dict[str, Any]) -> str:
    evidence = event.get("upgrade_evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return ""
    links = []
    for item in evidence[:3]:
        if not isinstance(item, dict):
            continue
        title = _esc(item.get("title", "公告候选"))
        url = str(item.get("source_url") or "").strip()
        if url:
            pdf_url = str(item.get("pdf_url") or "").strip()
            pdf = f' <a href="{_esc(pdf_url)}" target="_blank" rel="noopener noreferrer">PDF</a>' if pdf_url else ""
            links.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>{pdf}')
        else:
            links.append(title)
    checklist = []
    first = evidence[0] if isinstance(evidence[0], dict) else {}
    fact_note = _fact_markers_text(first.get("fact_markers", {}))
    review = _review_checklist_html(first.get("review_checklist", []))
    if fact_note:
        checklist.append(f'<div class="fact-markers">{_esc(fact_note)}</div>')
    if review:
        checklist.append(review)
    return '<div class="upgrade-evidence">公告候选：' + "；".join(links) + "".join(checklist) + "</div>"


def _auto_verification_html(event: dict[str, Any]) -> str:
    signal = event.get("auto_verification")
    if not isinstance(signal, dict) or not signal:
        return ""
    duplicate = str(signal.get("duplicate_of") or "").strip()
    duplicate_note = f"；疑似重复于 {duplicate}" if duplicate else ""
    return (
        '<div class="auto-verification">'
        f'自动验证：{_esc(signal.get("verification_label", ""))} '
        f'({int(signal.get("verification_score") or 0)}/100，'
        f'{int(signal.get("cluster_size") or 1)} 条相关事件)'
        f'{_esc(duplicate_note)}'
        f'<br>{_esc(signal.get("verification_note", ""))}'
        '</div>'
    )


def _verification_cluster_rows(clusters: list[dict[str, Any]]) -> str:
    if not clusters:
        return '<tr><td colspan="8">暂无自动验证簇</td></tr>'
    rows = []
    for cluster in clusters[:20]:
        score = int(cluster.get("verification_score") or 0)
        tag_class = "tag-up" if score >= 70 else "tag-warn" if score >= 35 else "tag-neutral"
        links = []
        for event in cluster.get("events", [])[:3]:
            if not isinstance(event, dict):
                continue
            title = str(event.get("title") or "事件")
            url = str(event.get("pdf_url") or event.get("source_url") or "").strip()
            if url:
                links.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer">{_esc(title)}</a>')
            else:
                links.append(_esc(title))
        rows.append(
            "<tr>"
            f"<td><span class=\"tag {tag_class}\">{score}/100</span></td>"
            f"<td>{_esc(cluster.get('verification_label'))}</td>"
            f"<td>{_esc(cluster.get('event_count'))}</td>"
            f"<td>{_esc('、'.join(cluster.get('stock_codes', [])[:8]))}</td>"
            f"<td>{_esc('、'.join(cluster.get('source_types', [])[:6]))}</td>"
            f"<td>{_esc('、'.join(cluster.get('providers', [])[:6]))}</td>"
            f"<td>{'；'.join(links)}</td>"
            f"<td>{_esc(cluster.get('verification_note'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _list_html(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    return "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in items[:5]) + "</ul>"


def _multi_agent_cards(multi_agent: dict[str, Any]) -> str:
    roles = multi_agent.get("roles", []) if isinstance(multi_agent, dict) else []
    if not isinstance(roles, list) or not roles:
        return '<div class="empty">暂无多角色分析</div>'
    cards = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        cards.append(
            '<div class="agent-card">'
            f'<div class="agent-role">{_esc(role.get("role_name"))}</div>'
            f'<div class="agent-stance">{_esc(role.get("stance"))}</div>'
            f'<div class="agent-block"><strong>观察</strong>{_list_html(role.get("observations", []))}</div>'
            f'<div class="agent-block"><strong>依据</strong>{_list_html(role.get("evidence", []))}</div>'
            f'<div class="agent-block"><strong>风险</strong>{_list_html(role.get("risks", []))}</div>'
            f'<div class="agent-block"><strong>下一步</strong>{_list_html(role.get("next_checks", []))}</div>'
            "</div>"
        )
    consensus = multi_agent.get("consensus", {}) if isinstance(multi_agent, dict) else {}
    if isinstance(consensus, dict) and consensus:
        cards.append(
            '<div class="agent-card consensus">'
            '<div class="agent-role">一致结论</div>'
            f'<div class="agent-stance">{_esc(consensus.get("stance"))}</div>'
            f'<p>{_esc(consensus.get("quality_gate"))}</p>'
            f'{_list_html(consensus.get("focus", []))}'
            "</div>"
        )
    return "\n".join(cards)


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
            f"<td>{_esc(event.get('required_confirmation', ''))}{_manual_verification_html(event)}{_auto_verification_html(event)}</td>"
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


def _verification_update_note(status: Any) -> str:
    if not isinstance(status, dict):
        return ""
    update_count = int(status.get("update_count") or 0)
    applied_count = int(status.get("applied_count") or 0)
    unmatched = status.get("unmatched_event_ids", [])
    if not isinstance(unmatched, list):
        unmatched = []
    unmatched_text = ""
    if unmatched:
        unmatched_text = "；未匹配：" + "、".join(_esc(item) for item in unmatched[:5])
    return (
        '<div class="source-note">人工确认写回：'
        f'{applied_count}/{update_count} 已应用'
        f'{unmatched_text}'
        '</div>'
    )


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
        fact_note = _fact_markers_text(event.get("fact_markers", {}))
        fact_html = f'<div class="fact-markers">{_esc(fact_note)}</div>' if fact_note else ""
        review = _review_checklist_html(event.get("review_checklist", []))
        cards.append(
            '<div class="verification-card">'
            f'<div class="card-top"><span class="tag tag-warn">{_esc(quality.get("tier"))}</span>'
            f'<span>{_esc(quality.get("label"))}</span>'
            f'<span class="tag {_status_tag_class(status)}">{_esc(event.get("verification_status_label", status))}</span></div>'
            f'<h3>{_esc(event.get("title"))}</h3>'
            f'<p>{_esc(event.get("summary"))}</p>'
            f'<div class="verify-action">验证：{_esc(event.get("required_confirmation"))}</div>'
            f'<div class="verify-policy">{_esc(event.get("verification_policy_note", ""))}</div>'
            f'{_manual_verification_html(event)}'
            f'{_auto_verification_html(event)}'
            f'{fact_html}'
            f'{review}'
            f'{_upgrade_evidence_note(event)}'
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
        "{{VERIFICATION_UPDATE_NOTE}}": _verification_update_note(analysis.get("verification_update_status", {})),
        "{{VERIFICATION_CLUSTER_ROWS}}": _verification_cluster_rows(
            analysis.get("verification_analysis", {}).get("clusters", [])
        ),
        "{{MULTI_AGENT_CARDS}}": _multi_agent_cards(analysis.get("multi_agent_analysis", {})),
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
