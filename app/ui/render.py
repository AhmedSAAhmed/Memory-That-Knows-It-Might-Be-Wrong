"""HTML renderers for evidence cards and status lines (escaped: memory is data)."""
from __future__ import annotations

from html import escape

BAND_LABEL = {"assert": "sure", "hedge": "might be wrong", "ask": "will ask"}


def evidence_html(evidence: list[dict], used: list[str] | None = None, hedged: list[str] | None = None) -> str:
    if not evidence:
        return ('<div class="navy-panel"><p class="navy-section-title">/// Relying on</p>'
                '<p class="navy-empty">No memories used for this reply yet.</p></div>')
    used_set, hedged_set = set(used or []), set(hedged or [])
    cards = []
    for ev in evidence:
        band = ev.get("band", "ask")
        conf = float(ev.get("confidence", 0.0))
        mark = " · used" if ev.get("id") in used_set else ""
        mark += " · hedged" if ev.get("id") in hedged_set else ""
        cards.append(
            '<div class="ev-card">'
            f'<div class="ev-head"><span class="ev-key">{escape(str(ev.get("key", "")))}</span>'
            f'<span class="badge badge-{escape(band)}">{escape(BAND_LABEL.get(band, band))}</span></div>'
            f'<div class="ev-text">{escape(str(ev.get("text", "")))}</div>'
            f'<div class="ev-bar"><span style="width:{max(0, min(100, conf * 100)):.0f}%"></span></div>'
            f'<div class="ev-meta">{conf:.2f} · {escape(str(ev.get("source", "")))} · '
            f'{escape(str(ev.get("age", "")))}{escape(mark)}</div>'
            f'<blockquote>{escape(str(ev.get("quote", "")))}</blockquote>'
            f'<div class="ev-meta">Evidence ID: {escape(str(ev.get("id", "")))}</div>'
            '</div>'
        )
    return '<div class="navy-panel"><p class="navy-section-title">/// Relying on</p>' + "".join(cards) + "</div>"


def status_html(provider: str, model: str, notes: list[str], injection_score: float | None) -> str:
    parts = []
    if provider:
        parts.append(f"{provider} · {model}")
    if injection_score is not None:
        parts.append(f"guard {injection_score:.2f}")
    parts.extend(notes)
    return f'<div class="navy-status">{escape(" | ".join(parts))}</div>' if parts else ""
