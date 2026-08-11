"""Validation tab — broker-specific return validation and event study."""

from __future__ import annotations

import streamlit as st

from idx_bandarmology import analysis
from dashboard.components.formatting import fmt_signal
from dashboard.components.layout import style_table
from dashboard.components.charts import interactive_event_ribbon


def render(
    selected_ticker: str,
    scan_h: pd.DataFrame,
    lookback_days: int,
) -> None:
    st.subheader("Broker-Specific Return Validation")
    if scan_h.empty:
        st.caption("No broker passes the current validation settings.")
    else:
        view = scan_h[
            [
                "ticker",
                "broker_code",
                "n_events",
                "mean_fwd_return",
                "median_fwd_return",
                "win_rate",
                "avg_net_value",
                "total_net_value",
                "p_value_one_sided",
                "significant",
            ]
        ].rename(
            columns={
                "ticker": "Ticker",
                "broker_code": "Broker",
                "n_events": "Events",
                "mean_fwd_return": "Mean Return",
                "median_fwd_return": "Median Return",
                "win_rate": "Win Rate",
                "avg_net_value": "Avg Net Buy",
                "total_net_value": "Total Net Buy",
                "p_value_one_sided": "P Value",
                "significant": "Significant",
            }
        )
        st.dataframe(style_table(view, money_cols=["Avg Net Buy", "Total Net Buy"], pct_cols=["Mean Return", "Median Return", "Win Rate"]), use_container_width=True, hide_index=True)

    st.subheader("Accumulation Event Study")
    show_individual = st.toggle("Show individual event paths", value=False)
    event_table = analysis.event_study_table(
        tickers=[selected_ticker],
        horizons=(1, 3, 5, 10),
        lookback_days=lookback_days,
        signals={"STRONG_ACCUMULATION", "ACCUMULATION", "NET_BUY", "AKUMULASI_KUAT", "AKUMULASI"},
    )
    st.plotly_chart(
        interactive_event_ribbon(event_table, horizons=(1, 3, 5, 10), show_individual=show_individual),
        use_container_width=True,
        config={"displayModeBar": True, "scrollZoom": True},
    )
    if not event_table.empty:
        event_view = event_table.rename(
            columns={
                "ticker": "Ticker",
                "signal_date": "Signal Date",
                "bandar_signal": "Signal",
                "bandar_signal_score": "Signal Score",
                "t_plus_0d": "Signal Day",
                "t_plus_1d": "+1D",
                "t_plus_3d": "+3D",
                "t_plus_5d": "+5D",
                "t_plus_10d": "+10D",
            }
        )
        event_view["Signal"] = event_view["Signal"].map(fmt_signal)
        st.dataframe(event_view, use_container_width=True, hide_index=True)
      
