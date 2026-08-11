"""UI layout components — cards, headers, alerts, verdicts, profile panels."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from .formatting import fmt_rp, fmt_pct, participant_label, signed_color


def render_metric_card(label: str, value: str, note: str = "", tone: str = "neutral", title: str = "") -> None:
    color = {"positive": "#0f9f6e", "negative": "#dc3545", "warning": "#b7791f"}.get(tone, "#94a3b8")
    st.markdown(
        f"""
        <div class="metric-card" title="{escape(title)}" style="--accent:{color}">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value" style="color:{color}">{escape(value)}</div>
            <div class="metric-note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(ticker: str, analysis_ts: pd.Timestamp, window_start: pd.Timestamp, activity_date: pd.Timestamp | None) -> None:
    data_date = activity_date.strftime("%Y-%m-%d") if activity_date is not None else "-"
    st.markdown(
        f"""
        <div class="page-header">
            <div>
                <div class="eyebrow">IDX Broker Flow Research</div>
                <div class="page-title">Smart Money Dashboard</div>
            </div>
            <div class="header-meta">
                <span>{escape(ticker)}</span>
                <span>Analysis {analysis_ts:%Y-%m-%d}</span>
                <span>Broker data {escape(data_date)}</span>
                <span>Window {window_start:%Y-%m-%d} to {analysis_ts:%Y-%m-%d}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_alerts(alerts: list[str]) -> None:
    if not alerts:
        return
    html = "".join(f"<div>{escape(item)}</div>" for item in alerts)
    st.markdown(f'<div class="alert-panel">{html}</div>', unsafe_allow_html=True)


def render_verdict(text: str) -> None:
    st.markdown(
        f"""
        <div class="verdict-panel">
            <div class="panel-kicker">Current read</div>
            <div class="verdict-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_profile_flow(profile_df: pd.DataFrame) -> None:
    if profile_df.empty:
        st.caption("No broker-profile flow for this date window.")
        return
    max_abs = max(float(profile_df["net"].abs().max()), 1.0)
    html = ['<div class="profile-panel">']
    for row in profile_df.sort_values("net", ascending=False).itertuples():
        net = float(row.net)
        width = max(3, min(100, abs(net) / max_abs * 100))
        color = signed_color(net)
        chips = []
        for broker in row.top_brokers:
            b_net = float(broker.get("net") or 0)
            chips.append(
                '<span class="broker-chip">'
                f'{escape(str(broker.get("broker_code", "-")))}'
                f'<span>{escape(participant_label(broker.get("participant_type")))}</span>'
                f'<b style="color:{signed_color(b_net)}">{escape(fmt_rp(b_net))}</b>'
                "</span>"
            )
        html.append(
            '<div class="profile-row">'
            '<div class="profile-head">'
            f"<div><b>{escape(row.label)}</b><small>{escape(row.description)}</small></div>"
            f'<strong style="color:{color}">{escape(fmt_rp(net))}</strong>'
            "</div>"
            '<div class="bar-track">'
            f'<div class="bar-fill" style="width:{width:.1f}%; background:{color};"></div>'
            "</div>"
            f'<div class="chip-row">{"".join(chips)}</div>'
            "</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def style_table(df: pd.DataFrame, money_cols: list[str] | None = None, pct_cols: list[str] | None = None):
    money_cols = money_cols or []
    pct_cols = pct_cols or []
    fmt = {col: fmt_rp for col in money_cols if col in df.columns}
    fmt.update({col: fmt_pct for col in pct_cols if col in df.columns})
    return df.style.format(fmt)
  
