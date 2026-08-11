"""Streamlit dashboard entry point — modular, clean, modern."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# ── path setup ───────────────────────────────────────────────────────────────
# Pastikan project root & src ada di sys.path agar import idx_bandarmology jalan
_DASHBOARD_DIR = Path(__file__).resolve().parent
_ROOT = _DASHBOARD_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from idx_bandarmology import analysis, broker_api, pipeline, storage

from dashboard.components.formatting import fmt_rp, fmt_pct, fmt_signal, score_tone
from dashboard.components.layout import (
    render_metric_card,
    render_page_header,
    render_alerts,
    render_verdict,
)
from dashboard.utils.data_helpers import (
    price_at_or_before,
    return_to_date,
    flow_row_at,
    latest_activity_date,
    smart_daily_from_activity,
    conviction_score,
    contradiction_alerts,
)

# Import tab views
from dashboard.views import overview, broker_flow, causality, validation, screener, raw_tables


# ── page config & styling ────────────────────────────────────────────────────
st.set_page_config(page_title="IDX Smart Money", layout="wide")

plt.rcParams.update(
    {
        "figure.facecolor": "#ffffff",
        "axes.facecolor": "#ffffff",
        "savefig.facecolor": "#ffffff",
        "axes.edgecolor": "#d9e2ec",
        "axes.labelcolor": "#64748b",
        "axes.titlecolor": "#111827",
        "xtick.color": "#64748b",
        "ytick.color": "#64748b",
        "grid.color": "#e5e7eb",
        "text.color": "#111827",
        "legend.facecolor": "#ffffff",
        "legend.edgecolor": "#d9e2ec",
        "legend.labelcolor": "#111827",
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Arial"],
    }
)

# Load external CSS
_CSS_PATH = _DASHBOARD_DIR / "styles.css"
if _CSS_PATH.exists():
    st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)


# ── cached data helpers ───────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def cached_causality(ticker: str) -> dict[str, object] | None:
    return analysis.causality_foreign_vs_price(ticker, max_lags=5)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_broker_scan(tickers: tuple[str, ...], horizon: int, min_events: int, min_net_value: float) -> pd.DataFrame:
    return analysis.broker_alpha_scan(
        list(tickers),
        horizon=horizon,
        min_events=min_events,
        min_net_value=min_net_value,
        group_by=("ticker", "broker_code"),
    )


# ── load global data ─────────────────────────────────────────────────────────
all_broker = storage.read_broker_flow()
all_activity = storage.read_broker_activity()
all_prices = storage.read_prices()

if not all_broker.empty:
    all_broker["ticker"] = all_broker["ticker"].str.upper()
if not all_activity.empty:
    all_activity["ticker"] = all_activity["ticker"].str.upper()
if not all_prices.empty:
    all_prices["ticker"] = all_prices["ticker"].str.upper()

available_tickers = (
    sorted(set(all_broker["ticker"].unique()).intersection(set(all_activity["ticker"].unique())))
    if not all_broker.empty and not all_activity.empty
    else []
)


# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    if not available_tickers:
        st.warning("No ticker has both broker-flow and broker-activity history yet.")
        st.stop()

    default_universe = ",".join(available_tickers)
    watchlist_input = st.text_input("Universe", value=default_universe)
    watchlist = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
    watchlist = [t for t in watchlist if t in available_tickers]
    if not watchlist:
        st.warning("The selected universe has no broker history.")
        st.stop()

    selected_ticker = st.selectbox("Ticker", watchlist)
    ticker_dates = sorted(all_activity[all_activity["ticker"] == selected_ticker]["date"].dt.date.unique().tolist())
    latest_broker_date = max(ticker_dates) if ticker_dates else None
    ticker_price_dates = sorted(all_prices[all_prices["ticker"] == selected_ticker]["date"].dt.date.unique().tolist())
    latest_price_date = max(ticker_price_dates) if ticker_price_dates else None

    if latest_broker_date:
        st.caption(f"Latest broker data: {latest_broker_date}")
    if latest_price_date and latest_price_date != latest_broker_date:
        st.caption(f"Latest price data: {latest_price_date}")
    if latest_broker_date and latest_broker_date < date.today():
        st.warning("Today is not available until broker-flow data is fetched and stored.")

    analysis_date = st.selectbox("Analysis date", ticker_dates, index=len(ticker_dates) - 1)
    analysis_ts = pd.Timestamp(analysis_date)

    lookback_label = st.selectbox(
        "Broker window",
        ["20 calendar days", "30 calendar days", "60 calendar days", "90 calendar days", "180 calendar days"],
        index=2,
    )
    lookback_days = int(lookback_label.split()[0])

    horizon_label = st.selectbox(
        "Validation horizon",
        ["1 trading day", "3 trading days", "5 trading days", "10 trading days"],
        index=3,
    )
    horizon = int(horizon_label.split()[0])

    min_events = st.number_input("Min broker events", min_value=3, max_value=30, value=5, step=1)
    min_net_buy_b = st.number_input("Min net buy, Rp B", min_value=0.0, value=0.0, step=0.5)

    st.divider()

    if st.button("Run latest pipeline to today"):
        result = pipeline.run(watchlist)
        if result["n_broker"] == 0:
            st.error("No broker-flow rows were stored. Check whether the Stockbit/BROKER_API_TOKEN is still valid.")
        else:
            st.success(f"Stored {result['n_broker']} flow rows and {result.get('n_activity', 0)} activity rows.")
            st.rerun()

    if latest_broker_date and latest_broker_date < date.today():
        missing_start = latest_broker_date + timedelta(days=1)
        if st.button(f"Fetch missing broker dates ({missing_start} to {date.today()})"):
            result = pipeline.backfill_broker_history(watchlist, missing_start, date.today(), refresh_prices=True)
            if result["n_broker"] == 0:
                st.error("No missing broker rows were stored. Refresh the Stockbit token or try again later.")
            else:
                st.success(f"Stored {result['n_broker']} flow rows and {result.get('n_activity', 0)} activity rows.")
                st.rerun()

    backfill_range = st.date_input("Historical backfill range", value=(date.today() - timedelta(days=90), date.today()))
    if st.button("Backfill broker history"):
        if isinstance(backfill_range, tuple) and len(backfill_range) == 2:
            result = pipeline.backfill_broker_history(watchlist, backfill_range[0], backfill_range[1], refresh_prices=True)
            if result["n_broker"] == 0:
                st.error("No broker rows were stored for that range. Refresh the Stockbit token or check dates.")
            else:
                st.success(f"Stored {result['n_broker']} flow rows and {result.get('n_activity', 0)} activity rows.")
                st.rerun()


# ── prepare window data ──────────────────────────────────────────────────────
window_start = analysis_ts - pd.Timedelta(days=lookback_days)

price_df = all_prices[all_prices["ticker"] == selected_ticker].copy()
broker_df = all_broker[all_broker["ticker"] == selected_ticker].copy()
activity_df = all_activity[all_activity["ticker"] == selected_ticker].copy()

price_window = price_df[(price_df["date"] >= window_start) & (price_df["date"] <= analysis_ts)].copy()
broker_window = broker_df[(broker_df["date"] >= window_start) & (broker_df["date"] <= analysis_ts)].copy()
activity_window = activity_df[(activity_df["date"] >= window_start) & (activity_df["date"] <= analysis_ts)].copy()

if broker_window.empty or activity_window.empty:
    st.warning("No broker history exists inside the selected date window.")
    st.stop()

# ── headline metrics ──────────────────────────────────────────────────────────
px_row = price_at_or_before(price_df, analysis_ts)
signal_row = flow_row_at(broker_df, selected_ticker, analysis_ts)
activity_date = latest_activity_date(activity_df, selected_ticker, analysis_ts)
top_buy, top_sell = analysis.top_net_broker_summary(selected_ticker, trade_date=activity_date, top_n=6)

ret_5d = return_to_date(price_df, analysis_ts, 5)
ret_10d = return_to_date(price_df, analysis_ts, 10)
foreign_5d = float(broker_window.sort_values("date").tail(5)["foreign_net_broker"].fillna(0).sum())

daily_smart = smart_daily_from_activity(activity_window)
smart_cum = float(daily_smart["cumulative_net"].iloc[-1]) if not daily_smart.empty else np.nan

top_buyer = top_buy.iloc[0] if not top_buy.empty else None

scan_h = cached_broker_scan(tuple(watchlist), horizon, int(min_events), float(min_net_buy_b) * 1e9)
scan_10d = cached_broker_scan((selected_ticker,), 10, 5, 0.0)

conviction = conviction_score(signal_row.get("bandar_signal"), foreign_5d, scan_10d, selected_ticker)
score_value = float(conviction["score"])
score_tone_name, _ = score_tone(score_value)

alerts = contradiction_alerts(signal_row.get("bandar_signal"), ret_5d, ret_10d, foreign_5d, smart_cum)

# Verdict text
sig_10d = scan_10d[scan_10d["significant"].eq(True)].copy() if not scan_10d.empty else pd.DataFrame()
if sig_10d.empty:
    verdict = (
        f"{selected_ticker} shows {fmt_signal(signal_row.get('bandar_signal'))} with {fmt_pct(ret_5d)} over 5D and "
        f"{fmt_pct(ret_10d)} over 10D. The current read is directional, but broker-specific 10D validation is not yet statistically strong."
    )
else:
    best = sig_10d.sort_values(["p_value_one_sided", "mean_fwd_return"], ascending=[True, False]).iloc[0]
    verdict = (
        f"{selected_ticker} shows {fmt_signal(signal_row.get('bandar_signal'))}. Broker {best['broker_code']} is the strongest 10D validation: "
        f"{int(best['n_events'])} events, mean return {fmt_pct(best['mean_fwd_return'])}, "
        f"win rate {best['win_rate']:.0%}, p-value {best['p_value_one_sided']:.4f}."
    )

breakdown = (
    f"Granger p-value component: {conviction['causality_component']:.0f}/100 "
    f"(p={conviction['p_value'] if conviction['p_value'] is not None and pd.notna(conviction['p_value']) else 'n/a'}); "
    f"Signal component: {conviction['signal_component']:.0f}/100; "
    f"Foreign 5D component: {conviction['foreign_component']:.0f}/100; "
    f"Broker win-rate component: {conviction['broker_component']:.0f}/100 ({conviction['broker_note']})."
)

# ── render header & KPIs ───────────────────────────────────────────────────────
render_page_header(selected_ticker, analysis_ts, window_start, activity_date)

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    render_metric_card("Conviction Score", f"{score_value:.1f}/100", "weighted model", score_tone_name, breakdown)
with k2:
    render_metric_card("Signal", fmt_signal(signal_row.get("bandar_signal")), "selected date")
with k3:
    render_metric_card("5D Return", fmt_pct(ret_5d), "price context", "positive" if (ret_5d or 0) >= 0 else "negative")
with k4:
    render_metric_card("Foreign Net 5D", fmt_rp(foreign_5d), "broker summary", "positive" if foreign_5d >= 0 else "negative")
with k5:
    render_metric_card("Top Buyer", str(top_buyer["broker_code"]) if top_buyer is not None else "-", fmt_rp(top_buyer["net_value"]) if top_buyer is not None else "", "positive")
with k6:
    render_metric_card("Smart Cumulative", fmt_rp(smart_cum), f"{len(daily_smart)} broker days", "positive" if (smart_cum or 0) >= 0 else "negative")

render_alerts(alerts)
render_verdict(verdict)

# ── tabs ─────────────────────────────────────────────────────────────────────
overview_tab, flow_tab, causality_tab, validation_tab, screener_tab, raw_tab = st.tabs(
    ["Overview", "Broker Flow", "Causality Insight", "Validation", "Screener", "Raw Tables"]
)

with overview_tab:
    overview.render(
        selected_ticker=selected_ticker,
        price_df=price_df,
        broker_df=broker_df,
        activity_df=activity_df,
        activity_window=activity_window,
        window_start=window_start,
        analysis_ts=analysis_ts,
        top_buy=top_buy,
        top_sell=top_sell,
    )

with flow_tab:
    broker_flow.render(
        selected_ticker=selected_ticker,
        activity_window=activity_window,
        activity_df=activity_df,
    )

with causality_tab:
    causality.render(
        selected_ticker=selected_ticker,
        score_value=score_value,
        score_tone_name=score_tone_name,
        conviction=conviction,
    )

with validation_tab:
    validation.render(
        selected_ticker=selected_ticker,
        scan_h=scan_h,
        lookback_days=lookback_days,
    )

with screener_tab:
    screener.render(
        watchlist=watchlist,
        analysis_ts=analysis_ts,
        scan_h=scan_h,
        all_prices=all_prices,
        all_flow=all_broker,
        all_activity=all_activity,
    )

with raw_tab:
    raw_tables.render(
        broker_window=broker_window,
        activity_window=activity_window,
    )

st.caption(f"Database: {storage.config.DB_PATH}")
    
