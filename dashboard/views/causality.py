"""Causality Insight tab — Granger causality tests."""

from __future__ import annotations

import streamlit as st

from idx_bandarmology import analysis
from dashboard.components.formatting import english_text
from dashboard.components.layout import render_metric_card, score_tone


def render(selected_ticker: str, score_value: float, score_tone_name: str, conviction: dict) -> None:
    st.subheader("Causality Insight")
    foreign_causality = analysis.causality_foreign_vs_price(selected_ticker, max_lags=5)
    c1, c2, c3 = st.columns(3)
    with c1:
        if foreign_causality:
            render_metric_card(
                "Foreign Flow Granger",
                "Significant" if foreign_causality["is_significant"] else "Not Significant",
                f"p={foreign_causality['min_p_value']:.4f}, lag {foreign_causality['best_lag']}",
                "positive" if foreign_causality["is_significant"] else "warning",
            )
        else:
            render_metric_card("Foreign Flow Granger", "Unavailable", "insufficient observations", "warning")
    with c2:
        render_metric_card("Conviction Model", f"{score_value:.1f}/100", "hover score card for formula", score_tone_name)
    with c3:
        render_metric_card("Broker Validation", conviction["broker_note"], "historical forward returns")

    left, right = st.columns(2)
    with left:
        st.subheader("Participant Type")
        part_causality = analysis.causality_by_participant(selected_ticker, max_lags=5)
        if part_causality.empty:
            st.caption("Insufficient participant history.")
        else:
            part_view = part_causality.rename(
                columns={"participant_type": "Participant", "best_lag": "Lag", "p_value": "P Value", "significant": "Significant"}
            )
            part_view["Participant"] = part_view["Participant"].map(english_text)
            st.dataframe(part_view.style.format({"P Value": "{:.4f}"}), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Top Broker Causality")
        broker_causality = analysis.causality_by_broker(selected_ticker, top_n=15, max_lags=5)
        if broker_causality.empty:
            st.caption("Insufficient broker history.")
        else:
            broker_view = broker_causality.rename(
                columns={"broker_code": "Broker", "best_lag": "Lag", "p_value": "P Value", "significant": "Significant"}
            )
            st.dataframe(broker_view.style.format({"P Value": "{:.4f}"}), use_container_width=True, hide_index=True)
          
