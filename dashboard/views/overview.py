"""Overview tab — price context, top brokers, performance, smart flow, profile flow."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from idx_bandarmology import analysis
from dashboard.components.formatting import fmt_rp, fmt_pct
from dashboard.components.layout import render_profile_flow, style_table
from dashboard.components.charts import interactive_price_context, interactive_smart_flow
from dashboard.utils.data_helpers import (
    top_broker_compact_table, profile_compact_table, profile_broker_detail_table,
    smart_daily_from_activity, profile_flow_from_activity,
)


def render(
    selected_ticker: str,
    price_df: pd.DataFrame,
    broker_df: pd.DataFrame,
    activity_df: pd.DataFrame,
    activity_window: pd.DataFrame,
    window_start: pd.Timestamp,
    analysis_ts: pd.Timestamp,
    top_buy: pd.DataFrame,
    top_sell: pd.DataFrame,
) -> None:
    import pandas as pd  # local import to avoid top-level circularity if any

    left, right = st.columns([1.55, 0.95])
    with left:
        st.subheader("Price, Volume, and Signal Context")
        st.plotly_chart(
            interactive_price_context(price_df, broker_df, selected_ticker, window_start, analysis_ts),
            use_container_width=True,
            config={"displayModeBar": True, "scrollZoom": True},
        )
    with right:
        st.subheader("Top Brokers")
        broker_summary = top_broker_compact_table(top_buy, top_sell, activity_df, analysis_ts)
        if broker_summary.empty:
            st.caption("No broker rows for the selected date.")
        else:
            st.caption("This table shows broker net buy or sell on the selected analysis date only.")
            st.dataframe(style_table(broker_summary, money_cols=["Net on Analysis Date"]), use_container_width=True, hide_index=True, height=246)

        perf = analysis.price_performance_table(selected_ticker)
        if not perf.empty:
            st.caption("Price Performance")
            perf = perf[perf["timeframe"].isin(["1D", "1W", "1M", "3M", "6M", "YTD"])]
            perf_view = perf.rename(columns={"timeframe": "Period", "return": "Return"})
            st.dataframe(style_table(perf_view, pct_cols=["Return"]), use_container_width=True, hide_index=True, height=142)

    lower_left, lower_right = st.columns([1.1, 0.9])
    with lower_left:
        st.subheader("Smart-Money Daily Flow")
        daily_smart = smart_daily_from_activity(activity_window)
        st.plotly_chart(interactive_smart_flow(daily_smart), use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
    with lower_right:
        st.subheader("Profile Net Flow")
        profile_df = profile_flow_from_activity(activity_window)
        profile_view = profile_compact_table(profile_df)
        if profile_view.empty:
            st.caption("No profile flow for this window.")
        else:
            st.dataframe(style_table(profile_view, money_cols=["Net"]), use_container_width=True, hide_index=True, height=246)
            with st.expander("Broker detail by profile", expanded=False):
                detail_view = profile_broker_detail_table(activity_window)
                st.dataframe(
                    style_table(detail_view, money_cols=["Buy", "Sell", "Net", "Avg Value / Tx"]),
                    use_container_width=True,
                    hide_index=True,
                    height=320,
                )
              
