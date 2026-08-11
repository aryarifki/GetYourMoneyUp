"""Screener tab — multi-ticker ranking by conviction score."""

from __future__ import annotations

import streamlit as st

from dashboard.components.layout import style_table
from dashboard.utils.data_helpers import build_screener


def render(
    watchlist: list[str],
    analysis_ts: pd.Timestamp,
    scan_h: pd.DataFrame,
    all_prices: pd.DataFrame,
    all_flow: pd.DataFrame,
    all_activity: pd.DataFrame,
) -> None:
    st.subheader("Multi-Ticker Screener")
    only_acc = st.toggle("Show only Accumulation / Strong Accumulation", value=True)
    screener = build_screener(watchlist, analysis_ts, scan_h, all_prices, all_flow, all_activity)
    if only_acc and not screener.empty:
        screener = screener[screener["Signal"].isin(["Accumulation", "Strong Accumulation", "Net Buy"])]
    if screener.empty:
        st.caption("No tickers match the current screener filter.")
    else:
        st.dataframe(
            style_table(screener, money_cols=["Foreign Net (5D)"], pct_cols=["5D Return"]),
            use_container_width=True,
            hide_index=True,
        )
      
