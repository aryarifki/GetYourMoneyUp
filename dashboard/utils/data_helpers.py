"""Data helpers — price lookups, flow calculations, profile aggregations, screener logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from idx_bandarmology import analysis, broker_api, storage
from dashboard.components.formatting import (
    fmt_rp, fmt_signal, fmt_pct, participant_label,
    PROFILE_META, SMART_PROFILES,
)


def price_at_or_before(price_df: pd.DataFrame, ts: pd.Timestamp) -> pd.Series | None:
    sub = price_df[price_df["date"] <= ts].sort_values("date")
    return None if sub.empty else sub.iloc[-1]


def return_to_date(price_df: pd.DataFrame, ts: pd.Timestamp, periods: int) -> float | None:
    sub = price_df[price_df["date"] <= ts].sort_values("date")
    if len(sub) <= periods:
        return None
    latest = float(sub.iloc[-1]["close"])
    base = float(sub.iloc[-periods - 1]["close"])
    return latest / base - 1 if base else None


def flow_row_at(flow_df: pd.DataFrame, ticker: str, ts: pd.Timestamp) -> dict[str, object]:
    sub = flow_df[(flow_df["ticker"] == ticker) & (flow_df["date"] <= ts)].sort_values("date")
    return {} if sub.empty else sub.iloc[-1].to_dict()


def latest_activity_date(activity_df: pd.DataFrame, ticker: str, ts: pd.Timestamp) -> pd.Timestamp | None:
    sub = activity_df[(activity_df["ticker"] == ticker) & (activity_df["date"] <= ts)]
    if sub.empty:
        return None
    return pd.Timestamp(sub["date"].max())


def profile_flow_from_activity(activity: pd.DataFrame) -> pd.DataFrame:
    if activity.empty:
        return pd.DataFrame()
    df = activity.copy()
    df["profile"] = df["broker_code"].map(analysis.broker_profile_of)
    broker_rows = (
        df.groupby(["profile", "broker_code", "participant_type"], dropna=False)
        .agg(net=("net_value", "sum"), buy=("buy_value", "sum"), sell=("sell_value", "sum"))
        .reset_index()
    )
    rows = []
    for profile, (label, desc) in PROFILE_META.items():
        members = broker_rows[broker_rows["profile"] == profile].copy()
        if members.empty:
            continue
        members["abs_net"] = members["net"].abs()
        rows.append(
            {
                "profile": profile,
                "label": label,
                "description": desc,
                "net": float(members["net"].sum()),
                "top_brokers": members.sort_values("abs_net", ascending=False)
                .head(6)[["broker_code", "participant_type", "net"]]
                .to_dict("records"),
            }
        )
    return pd.DataFrame(rows)


def smart_daily_from_activity(activity: pd.DataFrame) -> pd.DataFrame:
    if activity.empty:
        return pd.DataFrame()
    df = activity.copy()
    df["profile"] = df["broker_code"].map(analysis.broker_profile_of)
    df = df[df["profile"].isin(SMART_PROFILES)]
    if df.empty:
        return pd.DataFrame()
    daily = df.groupby("date")["net_value"].sum().reset_index(name="smart_net").sort_values("date")
    daily["cumulative_net"] = daily["smart_net"].cumsum()
    return daily


def sparkline_values(activity: pd.DataFrame, broker_code: str, end_ts: pd.Timestamp, days: int = 5) -> str:
    sub = activity[(activity["broker_code"] == broker_code) & (activity["date"] <= end_ts)].sort_values("date").tail(days)
    if sub.empty:
        return "-----"
    chars = []
    for value in sub["net_value"].fillna(0):
        chars.append("+" if value > 0 else "-" if value < 0 else "0")
    return "".join(chars)


def top_broker_compact_table(top_buy: pd.DataFrame, top_sell: pd.DataFrame, activity: pd.DataFrame, end_ts: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for side, df in (("Buy", top_buy.head(3)), ("Sell", top_sell.head(3))):
        for row in df.itertuples():
            rows.append(
                {
                    "Side": side,
                    "Broker": row.broker_code,
                    "Type": participant_label(row.participant_type),
                    "Net on Analysis Date": row.net_value,
                    "5D Flow": sparkline_values(activity, row.broker_code, end_ts),
                }
            )
    return pd.DataFrame(rows)


def profile_compact_table(profile_df: pd.DataFrame) -> pd.DataFrame:
    if profile_df.empty:
        return pd.DataFrame()
    out = profile_df[["label", "net"]].copy()
    out = out.sort_values("net", ascending=False).head(6)
    out = out.rename(columns={"label": "Profile", "net": "Net"})
    return out.reset_index(drop=True)


def profile_broker_detail_table(activity: pd.DataFrame, profile_key: str | None = None) -> pd.DataFrame:
    if activity.empty:
        return pd.DataFrame()
    df = activity.copy()
    df["Profile Key"] = df["broker_code"].map(analysis.broker_profile_of)
    if profile_key:
        df = df[df["Profile Key"] == profile_key]
    if df.empty:
        return pd.DataFrame()
    grouped = (
        df.groupby(["Profile Key", "broker_code", "participant_type"], dropna=False)
        .agg(
            Buy=("buy_value", "sum"),
            Sell=("sell_value", "sum"),
            Net=("net_value", "sum"),
            Freq=("frequency", "sum"),
            Days=("date", "nunique"),
        )
        .reset_index()
    )
    grouped["Profile"] = grouped["Profile Key"].map(lambda key: PROFILE_META.get(key, (key, ""))[0])
    grouped["Broker"] = grouped["broker_code"]
    grouped["Type"] = grouped["participant_type"].map(participant_label)
    grouped["Avg Value / Tx"] = grouped.apply(lambda r: abs(float(r["Net"] or 0)) / max(float(r["Freq"] or 0), 1), axis=1)
    grouped = grouped.sort_values(["Profile", "Net"], ascending=[True, False])
    return grouped[["Profile", "Broker", "Type", "Buy", "Sell", "Net", "Freq", "Days", "Avg Value / Tx"]].reset_index(drop=True)


def broker_summary_table(dist: pd.DataFrame, distribution_data: dict[str, object] | None = None, top_n: int = 10) -> pd.DataFrame:
    by_value = (distribution_data or {}).get("by_value") or {}
    if by_value.get("top_broker_buy") or by_value.get("top_broker_sell"):
        buy_rows = by_value.get("top_broker_buy") or []
        sell_rows = by_value.get("top_broker_sell") or []
        rows: list[dict[str, object]] = []
        max_len = max(len(buy_rows), len(sell_rows), 0)
        for i in range(min(max_len, top_n)):
            row: dict[str, object] = {}
            if i < len(buy_rows):
                b = buy_rows[i].get("detail") or {}
                row.update(
                    {
                        "Buy Broker": b.get("code", ""),
                        "Buy Type": participant_label(b.get("type")),
                        "Buy Value": b.get("amount"),
                        "Buy Lot": np.nan,
                        "Buy Avg": np.nan,
                    }
                )
            else:
                row.update({"Buy Broker": "", "Buy Type": "", "Buy Value": np.nan, "Buy Lot": np.nan, "Buy Avg": np.nan})
            if i < len(sell_rows):
                s = sell_rows[i].get("detail") or {}
                row.update(
                    {
                        "Sell Broker": s.get("code", ""),
                        "Sell Type": participant_label(s.get("type")),
                        "Sell Value": s.get("amount"),
                        "Sell Lot": np.nan,
                        "Sell Avg": np.nan,
                    }
                )
            else:
                row.update({"Sell Broker": "", "Sell Type": "", "Sell Value": np.nan, "Sell Lot": np.nan, "Sell Avg": np.nan})
            rows.append(row)
        return pd.DataFrame(rows)

    if dist.empty:
        return pd.DataFrame()
    buyers = dist[dist["net_value"] > 0].copy().sort_values("net_value", ascending=False).head(top_n).reset_index(drop=True)
    sellers = dist[dist["net_value"] < 0].copy().sort_values("net_value", ascending=True).head(top_n).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    max_len = max(len(buyers), len(sellers))
    for i in range(max_len):
        row: dict[str, object] = {}
        if i < len(buyers):
            b = buyers.iloc[i]
            row.update(
                {
                    "Buy Broker": b["broker_code"],
                    "Buy Type": participant_label(b["participant_type"]),
                    "Buy Value": b["buy_value"],
                    "Buy Lot": b["buy_lot"],
                    "Buy Avg": b["buy_avg_price"],
                }
            )
        else:
            row.update({"Buy Broker": "", "Buy Type": "", "Buy Value": np.nan, "Buy Lot": np.nan, "Buy Avg": np.nan})
        if i < len(sellers):
            s = sellers.iloc[i]
            row.update(
                {
                    "Sell Broker": s["broker_code"],
                    "Sell Type": participant_label(s["participant_type"]),
                    "Sell Value": s["sell_value"],
                    "Sell Lot": s["sell_lot"],
                    "Sell Avg": s["sell_avg_price"],
                }
            )
        else:
            row.update({"Sell Broker": "", "Sell Type": "", "Sell Value": np.nan, "Sell Lot": np.nan, "Sell Avg": np.nan})
        rows.append(row)
    return pd.DataFrame(rows)


# ── Conviction score & screener ──────────────────────────────────────────────

def label_component(signal: object) -> float:
    raw = str(signal or "").upper()
    if raw in {"AKUMULASI_KUAT", "STRONG_ACCUMULATION"}:
        return 100
    if raw in {"AKUMULASI", "ACCUMULATION", "NET_BUY"}:
        return 80
    if raw in {"NETRAL", "NEUTRAL"}:
        return 50
    if raw in {"DISTRIBUSI", "DISTRIBUTION", "NET_SELL"}:
        return 25
    if raw in {"DISTRIBUSI_KUAT", "STRONG_DISTRIBUTION"}:
        return 0
    return 40


def p_value_component(p_value: float | None) -> float:
    if p_value is None or pd.isna(p_value):
        return 50
    if p_value <= 0.01:
        return 100
    if p_value <= 0.05:
        return 80
    if p_value <= 0.10:
        return 55
    return 20


def foreign_component(value: float | None) -> float:
    if value is None or pd.isna(value):
        return 50
    if value > 0:
        return 100
    if value < 0:
        return 0
    return 50


def broker_win_component(scan_df: pd.DataFrame, ticker: str) -> tuple[float, str]:
    if scan_df.empty:
        return 50, "No broker validation sample"
    sub = scan_df[scan_df["ticker"] == ticker].copy() if "ticker" in scan_df.columns else scan_df.copy()
    if sub.empty:
        return 50, "No broker validation sample"
    sub = sub.sort_values(["significant", "p_value_one_sided", "mean_fwd_return"], ascending=[False, True, False])
    row = sub.iloc[0]
    win_rate = float(row.get("win_rate", 0.5))
    return max(0, min(100, win_rate * 100)), f"{row.get('broker_code', '-')} win rate {win_rate:.0%}"


def conviction_score(signal: object, foreign_5d: float | None, scan_df: pd.DataFrame, ticker: str) -> dict[str, object]:
    causality = analysis.causality_foreign_vs_price(ticker, max_lags=5)
    p_value = None if not causality else float(causality.get("min_p_value", np.nan))
    p_score = p_value_component(p_value)
    s_score = label_component(signal)
    f_score = foreign_component(foreign_5d)
    w_score, w_note = broker_win_component(scan_df, ticker)
    score = (p_score * 0.30) + (s_score * 0.30) + (f_score * 0.20) + (w_score * 0.20)
    return {
        "score": round(float(score), 1),
        "p_value": p_value,
        "causality_component": p_score,
        "signal_component": s_score,
        "foreign_component": f_score,
        "broker_component": w_score,
        "broker_note": w_note,
    }


def contradiction_alerts(signal: object, ret_5d: float | None, ret_10d: float | None, foreign_5d: float | None, smart_cum: float | None) -> list[str]:
    raw = str(signal or "").upper()
    alerts = []
    if raw in {"STRONG_DISTRIBUTION", "DISTRIBUTION", "NET_SELL", "DISTRIBUSI_KUAT", "DISTRIBUSI"} and ((ret_5d is not None and ret_5d > 0) or (ret_10d is not None and ret_10d > 0)):
        alerts.append(
            "Distribution while price is still rising — potential unfinished distribution or new buyer absorption. Monitor volume."
        )
    if raw in {"STRONG_ACCUMULATION", "ACCUMULATION", "NET_BUY", "AKUMULASI_KUAT", "AKUMULASI"} and ret_5d is not None and ret_5d < 0:
        alerts.append("Accumulation signal with negative 5D return — accumulation may be early, failed, or absorbed by larger supply.")
    if foreign_5d is not None and foreign_5d < 0 and raw in {"STRONG_ACCUMULATION", "ACCUMULATION", "NET_BUY", "AKUMULASI_KUAT", "AKUMULASI"}:
        alerts.append("Aggregate accumulation conflicts with foreign net selling — check whether the move is driven by local brokers.")
    if smart_cum is not None and smart_cum < 0 and raw in {"STRONG_ACCUMULATION", "ACCUMULATION", "NET_BUY", "AKUMULASI_KUAT", "AKUMULASI"}:
        alerts.append("Signal is accumulation but smart-money cumulative flow is negative in the selected window.")
    return alerts


def build_screener(watchlist: list[str], as_of: pd.Timestamp, scan_df: pd.DataFrame, all_prices: pd.DataFrame, all_flow: pd.DataFrame, all_activity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker in watchlist:
        flow_row = flow_row_at(all_flow, ticker, as_of)
        act_date = latest_activity_date(all_activity, ticker, as_of)
        if not flow_row or act_date is None:
            continue
        px = all_prices[all_prices["ticker"] == ticker]
        flow_sub = all_flow[(all_flow["ticker"] == ticker) & (all_flow["date"] <= as_of)].sort_values("date")
        foreign_5d = float(flow_sub.tail(5)["foreign_net_broker"].fillna(0).sum()) if not flow_sub.empty else np.nan
        buyers, _ = analysis.top_net_broker_summary(ticker, trade_date=act_date, top_n=1)
        top_buyer = "-" if buyers.empty else str(buyers.iloc[0]["broker_code"])
        ret_5d = return_to_date(px, as_of, 5)
        conv = conviction_score(flow_row.get("bandar_signal"), foreign_5d, scan_df, ticker)
        rows.append(
            {
                "Ticker": ticker,
                "Signal": fmt_signal(flow_row.get("bandar_signal")),
                "Conviction Score": conv["score"],
                "Foreign Net (5D)": foreign_5d,
                "Top Buyer": top_buyer,
                "5D Return": ret_5d,
                "Data Date": pd.Timestamp(flow_row.get("date")).date(),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Conviction Score", ascending=False).reset_index(drop=True)
  
