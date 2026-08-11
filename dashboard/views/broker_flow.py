"""Broker Flow tab — broker drill-down, comparison, profile flow, distribution sankey."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from idx_bandarmology import broker_api
from dashboard.components.formatting import fmt_rp, participant_label, broker_subtype
from dashboard.components.layout import render_profile_flow, style_table
from dashboard.components.charts import interactive_broker_compare, broker_distribution_sankey
from dashboard.utils.data_helpers import profile_flow_from_activity, profile_broker_detail_table, broker_summary_table


@st.cache_data(ttl=1800, show_spinner=False)
def cached_broker_distribution_api(ticker: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict[str, object]:
    return broker_api.fetch_broker_distribution(ticker, start_date, end_date=end_date)


def render(
    selected_ticker: str,
    activity_window: pd.DataFrame,
    activity_df: pd.DataFrame,
) -> None:
    st.subheader("Broker Drill-Down")
    broker_codes = sorted(activity_window["broker_code"].dropna().unique().tolist())
    ranked_codes = (
        activity_window.assign(abs_net=activity_window["net_value"].abs())
        .groupby("broker_code")["abs_net"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    default_codes = ranked_codes[:3] if ranked_codes else broker_codes[:3]
    c1, c2, c3, c4 = st.columns([0.8, 0.9, 1.7, 0.9])
    with c1:
        compare_mode = st.toggle("Compare mode", value=True)
    with c2:
        max_brokers = st.selectbox("Max brokers", [3, 5, 8, 12, "All"], index=1)
    with c3:
        max_selections = None if max_brokers == "All" else int(max_brokers)
        default_selection = default_codes[: min(len(default_codes), max_selections or len(default_codes))]
        selected_brokers = st.multiselect("Broker codes", broker_codes, default=default_selection, max_selections=max_selections)
    with c4:
        flow_mode = st.selectbox("Flow mode", ["Cumulative", "Daily"])
    st.caption("Cumulative mode sums broker net flow across the selected broker window. Daily mode shows each date separately.")
    st.plotly_chart(interactive_broker_compare(activity_window, selected_brokers, flow_mode), use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})

    left, right = st.columns([0.95, 1.05])
    with left:
        st.subheader("Broker Profile Flow")
        profile_df = profile_flow_from_activity(activity_window)
        render_profile_flow(profile_df)
        profile_options = ["All Profiles"] + [row["label"] for _, row in profile_df.iterrows()] if not profile_df.empty else ["All Profiles"]
        selected_profile_label = st.selectbox("Profile detail", profile_options)
        selected_profile_key = None
        if selected_profile_label != "All Profiles" and not profile_df.empty:
            selected_profile_key = profile_df[profile_df["label"] == selected_profile_label]["profile"].iloc[0]
        detail_view = profile_broker_detail_table(activity_window, selected_profile_key)
        if detail_view.empty:
            st.caption("No broker detail for this profile.")
        else:
            st.dataframe(
                style_table(detail_view, money_cols=["Buy", "Sell", "Net", "Avg Value / Tx"]),
                use_container_width=True,
                hide_index=True,
                height=360,
            )
    with right:
        st.subheader("Broker Distribution")
        available_dist_dates = sorted(activity_window["date"].dt.date.unique().tolist())
        d1, d2 = st.columns([0.8, 1.2])
        with d1:
            distribution_mode = st.selectbox("Distribution mode", ["Single day", "Date range"])
        with d2:
            if distribution_mode == "Single day":
                dist_date = st.selectbox("Distribution date", available_dist_dates, index=len(available_dist_dates) - 1)
                dist_start = pd.Timestamp(dist_date)
                dist_end = pd.Timestamp(dist_date)
            else:
                default_start = available_dist_dates[max(0, len(available_dist_dates) - 5)]
                range_value = st.date_input(
                    "Distribution range",
                    value=(default_start, available_dist_dates[-1]),
                    min_value=available_dist_dates[0],
                    max_value=available_dist_dates[-1],
                )
                if isinstance(range_value, tuple) and len(range_value) == 2:
                    dist_start = pd.Timestamp(range_value[0])
                    dist_end = pd.Timestamp(range_value[1])
                else:
                    dist_start = pd.Timestamp(available_dist_dates[-1])
                    dist_end = pd.Timestamp(available_dist_dates[-1])

        dist = activity_window[
            (activity_window["date"] >= dist_start) & (activity_window["date"] <= dist_end)
        ].copy()
        if not dist.empty:
            dist = (
                dist.groupby(["broker_code", "participant_type"], dropna=False)
                .agg(
                    buy_value=("buy_value", "sum"),
                    sell_value=("sell_value", "sum"),
                    net_value=("net_value", "sum"),
                    frequency=("frequency", "sum"),
                    buy_lot=("buy_lot", "sum"),
                    sell_lot=("sell_lot", "sum"),
                    buy_avg_price=("buy_avg_price", "mean"),
                    sell_avg_price=("sell_avg_price", "mean"),
                )
                .reset_index()
            )
        if dist.empty:
            st.caption("No distribution rows for this date range.")
        else:
            distribution_api = {}
            try:
                distribution_api = cached_broker_distribution_api(selected_ticker, dist_start, dist_end)
            except Exception as exc:  # noqa: BLE001
                distribution_api = {}
                st.caption(f"Live distribution API unavailable for this date: {type(exc).__name__}. Falling back to estimated matching.")
            if distribution_api:
                st.caption("The flow chart below uses broker-to-broker distribution edges returned by the live API.")
            else:
                st.caption("Exact broker-to-broker counterparties are unavailable. The flow chart below falls back to estimated same-day matching based on broker net buy and sell totals.")
            st.plotly_chart(
                broker_distribution_sankey(dist, dist_end, distribution_data=distribution_api, top_n=8),
                use_container_width=True,
                config={"displayModeBar": True, "scrollZoom": True},
            )
            st.caption("Broker Summary")
            summary_view = broker_summary_table(dist, distribution_data=distribution_api, top_n=10)
            st.dataframe(
                summary_view.style.format(
                    {
                        "Buy Value": fmt_rp,
                        "Sell Value": fmt_rp,
                        "Buy Lot": lambda v: "-" if pd.isna(v) else f"{float(v):,.1f}K" if abs(float(v)) >= 1_000 else f"{float(v):,.0f}",
                        "Sell Lot": lambda v: "-" if pd.isna(v) else f"{float(v):,.1f}K" if abs(float(v)) >= 1_000 else f"{float(v):,.0f}",
                        "Buy Avg": lambda v: "-" if pd.isna(v) else f"{float(v):,.0f}",
                        "Sell Avg": lambda v: "-" if pd.isna(v) else f"{float(v):,.0f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                height=320,
            )
            st.caption("Detailed broker rows")
            dist_view = dist[["broker_code", "participant_type", "buy_value", "sell_value", "net_value", "frequency"]].rename(
                columns={
                    "broker_code": "Broker",
                    "participant_type": "Type",
                    "buy_value": "Buy",
                    "sell_value": "Sell",
                    "net_value": "Net",
                    "frequency": "Freq",
                }
            )
            dist_view["Type"] = dist_view["Type"].map(participant_label)
            dist_view["Avg Value / Tx"] = dist_view.apply(lambda r: abs(float(r["Net"] or 0)) / max(float(r["Freq"] or 0), 1), axis=1)
            dist_view["Sub-type"] = dist_view.apply(broker_subtype, axis=1)
            st.dataframe(style_table(dist_view, money_cols=["Buy", "Sell", "Net", "Avg Value / Tx"]), use_container_width=True, hide_index=True)
  
