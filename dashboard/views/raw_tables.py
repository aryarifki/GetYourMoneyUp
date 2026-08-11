"""Raw Tables tab — underlying broker-flow and broker-activity rows."""

from __future__ import annotations

import streamlit as st

from dashboard.components.formatting import fmt_signal, participant_label
from dashboard.components.layout import style_table


def render(
    broker_window: pd.DataFrame,
    activity_window: pd.DataFrame,
) -> None:
    st.subheader("Broker-Flow Rows")
    flow_view = broker_window[
        ["date", "bandar_signal", "bandar_signal_score", "foreign_net_broker", "local_net_broker", "total_value"]
    ].rename(
        columns={
            "date": "Date",
            "bandar_signal": "Signal",
            "bandar_signal_score": "Score",
            "foreign_net_broker": "Foreign Net",
            "local_net_broker": "Local Net",
            "total_value": "Value",
        }
    )
    flow_view["Signal"] = flow_view["Signal"].map(fmt_signal)
    st.dataframe(style_table(flow_view, money_cols=["Foreign Net", "Local Net", "Value"]), use_container_width=True, hide_index=True)

    st.subheader("Broker Activity Rows")
    activity_view = activity_window[
        ["date", "broker_code", "participant_type", "buy_value", "sell_value", "net_value", "frequency"]
    ].rename(
        columns={
            "date": "Date",
            "broker_code": "Broker",
            "participant_type": "Type",
            "buy_value": "Buy",
            "sell_value": "Sell",
            "net_value": "Net",
            "frequency": "Freq",
        }
    )
    activity_view["Type"] = activity_view["Type"].map(participant_label)
    st.dataframe(style_table(activity_view, money_cols=["Buy", "Sell", "Net"]), use_container_width=True, hide_index=True)
  
