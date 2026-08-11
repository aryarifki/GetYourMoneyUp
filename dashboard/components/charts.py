"""Chart components — matplotlib and plotly visualizations."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .formatting import fmt_rp, fmt_signal, participant_label, rgba_from_hex
from .formatting import ACC_SIGNALS, PROFILE_META


def plot_price_context(price_df: pd.DataFrame, broker_df: pd.DataFrame, ticker: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> plt.Figure:
    px = price_df[(price_df["date"] >= start_ts) & (price_df["date"] <= end_ts)].sort_values("date")
    br = broker_df[(broker_df["date"] >= start_ts) & (broker_df["date"] <= end_ts)].sort_values("date")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.8, 4.05), sharex=True, gridspec_kw={"height_ratios": [3.1, 0.95]})
    if px.empty:
        ax1.text(0.5, 0.5, "No price rows in selected broker window.", ha="center", va="center")
        ax1.set_axis_off()
        ax2.set_axis_off()
        return fig
    ax1.plot(px["date"], px["close"], color="#2563eb", linewidth=1.8, label="Close")
    ax1.axvline(start_ts, color="#b7791f", linewidth=1.0, linestyle="--", alpha=0.75, label="Broker window start")
    signal_dates = set()
    if not br.empty:
        overlay = px.merge(br[["date", "bandar_signal", "bandar_signal_score"]], on="date", how="inner")
        colors = overlay["bandar_signal_score"].map({2: "#0f9f6e", 1: "#65a30d", 0: "#94a3b8", -1: "#ea580c", -2: "#dc3545"}).fillna("#94a3b8")
        ax1.scatter(overlay["date"], overlay["close"], c=colors, s=34, zorder=4, label="Signal date")
        signal_dates = set(overlay[overlay["bandar_signal"].isin(ACC_SIGNALS)]["date"])
    volume_colors = ["#0f9f6e" if d in signal_dates else "#cbd5e1" for d in px["date"]]
    if "volume" in px.columns:
        ax2.bar(px["date"], px["volume"].fillna(0) / 1e6, color=volume_colors, width=0.8)
    ax1.set_title(f"{ticker} price, volume, and signal window")
    ax1.set_ylabel("Close")
    ax1.grid(alpha=0.18)
    ax1.legend(loc="upper left", fontsize=8)
    ax2.set_ylabel("Vol M")
    ax2.grid(axis="y", alpha=0.15)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_broker_compare(activity: pd.DataFrame, broker_codes: list[str], mode: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10.8, 3.65))
    if activity.empty or not broker_codes:
        ax.text(0.5, 0.5, "Select broker codes to display flow.", ha="center", va="center")
        ax.set_axis_off()
        return fig
    sub = activity[activity["broker_code"].isin(broker_codes)].copy()
    if sub.empty:
        ax.text(0.5, 0.5, "No rows for selected broker codes.", ha="center", va="center")
        ax.set_axis_off()
        return fig
    pivot = sub.pivot_table(index="date", columns="broker_code", values="net_value", aggfunc="sum").sort_index()
    if mode == "Cumulative":
        pivot = pivot.cumsum()
    pivot = pivot / 1e9
    for code in pivot.columns:
        ax.plot(pivot.index, pivot[code], marker="o", linewidth=2, label=code)
    ax.axhline(0, color="#64748b", linewidth=0.9)
    ax.set_ylabel("Net value, Rp B")
    ax.set_title("Broker flow comparison")
    ax.grid(alpha=0.16)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_smart_flow(daily: pd.DataFrame) -> plt.Figure:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.8, 3.45), sharex=True, gridspec_kw={"height_ratios": [2, 0.9]})
    if daily.empty:
        ax1.text(0.5, 0.5, "No smart-money flow in selected window.", ha="center", va="center")
        ax1.set_axis_off()
        ax2.set_axis_off()
        return fig
    colors = np.where(daily["smart_net"] >= 0, "#0f9f6e", "#dc3545")
    ax1.bar(daily["date"], daily["smart_net"] / 1e9, color=colors, width=0.8)
    ax1.axhline(0, color="#64748b", linewidth=0.8)
    ax1.set_ylabel("Daily net, Rp B")
    ax1.grid(axis="y", alpha=0.15)
    ax2.plot(daily["date"], daily["cumulative_net"] / 1e9, color="#2563eb", linewidth=1.8)
    ax2.axhline(0, color="#64748b", linewidth=0.8)
    ax2.set_ylabel("Cumulative")
    ax2.grid(axis="y", alpha=0.15)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_event_ribbon(event_table: pd.DataFrame, horizons: tuple[int, ...], show_individual: bool) -> plt.Figure:
    xs = [0, *horizons]
    fig, ax = plt.subplots(figsize=(10.8, 3.85))
    if event_table.empty:
        ax.text(0.5, 0.5, "No accumulation events in this window.", ha="center", va="center")
        ax.set_axis_off()
        return fig
    cols = [f"t_plus_{h}d" for h in xs]
    values = event_table[cols].apply(pd.to_numeric, errors="coerce")
    median = values.median()
    q25 = values.quantile(0.25)
    q75 = values.quantile(0.75)
    mean_plus_5 = values["t_plus_5d"].mean() if "t_plus_5d" in values.columns else values.iloc[:, -1].mean()
    color = "#0f9f6e" if mean_plus_5 >= 100 else "#dc3545"
    if show_individual:
        for row in values.itertuples(index=False):
            ax.plot(xs, list(row), color="#64748b", alpha=0.28, linewidth=1)
    ax.fill_between(xs, q25.values, q75.values, color=color, alpha=0.22, label="25-75 percentile")
    ax.plot(xs, median.values, color=color, linewidth=3, marker="o", label="Median path")
    ax.axhline(100, color="#94a3b8", linestyle="--", linewidth=0.9)
    ax.set_xticks(xs)
    ax.set_xticklabels(["Signal", *[f"+{h}d" for h in horizons]])
    ax.set_ylabel("Normalized price")
    ax.set_title("Event study ribbon, signal date = 100")
    ax.grid(alpha=0.16)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def plotly_layout(fig: go.Figure, height: int, title: str | None = None) -> go.Figure:
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=18, r=18, t=38 if title else 16, b=22),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Inter, Arial, sans-serif", color="#334155", size=12),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
    )
    fig.update_xaxes(showgrid=False, linecolor="#d9e2ec", tickfont=dict(color="#64748b"))
    fig.update_yaxes(gridcolor="#edf2f7", linecolor="#d9e2ec", tickfont=dict(color="#64748b"))
    return fig


def interactive_price_context(price_df: pd.DataFrame, broker_df: pd.DataFrame, ticker: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> go.Figure:
    px = price_df[(price_df["date"] >= start_ts) & (price_df["date"] <= end_ts)].sort_values("date")
    br = broker_df[(broker_df["date"] >= start_ts) & (broker_df["date"] <= end_ts)].sort_values("date")
    fig = go.Figure()
    if px.empty:
        return plotly_layout(fig, 390, "No price rows in selected broker window")
    overlay = px.merge(br[["date", "bandar_signal", "bandar_signal_score"]], on="date", how="left") if not br.empty else px.copy()
    overlay["Signal"] = overlay.get("bandar_signal", pd.Series(index=overlay.index)).map(fmt_signal)
    signal_color = overlay.get("bandar_signal_score", pd.Series(index=overlay.index)).map(
        {2: "#0f9f6e", 1: "#65a30d", 0: "#94a3b8", -1: "#ea580c", -2: "#dc3545"}
    ).fillna("#94a3b8")
    signal_series = overlay["bandar_signal"] if "bandar_signal" in overlay.columns else pd.Series("", index=overlay.index)
    volume_color = np.where(signal_series.isin(ACC_SIGNALS), "#0f9f6e", "#cbd5e1")

    fig.add_bar(
        x=px["date"],
        y=px["volume"].fillna(0) / 1e6 if "volume" in px.columns else np.zeros(len(px)),
        name="Volume, M",
        marker_color=volume_color,
        opacity=0.36,
        yaxis="y2",
        hovertemplate="%{x|%Y-%m-%d}<br>Volume: %{y:.2f}M<extra></extra>",
    )
    fig.add_trace(
        go.Scatter(
            x=px["date"],
            y=px["close"],
            mode="lines",
            name="Close",
            line=dict(color="#2563eb", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Close: Rp %{y:,.0f}<extra></extra>",
        )
    )
    if not br.empty:
        signal_rows = overlay[overlay["bandar_signal"].notna()].copy()
        fig.add_trace(
            go.Scatter(
                x=signal_rows["date"],
                y=signal_rows["close"],
                mode="markers",
                name="Signal",
                marker=dict(color=signal_color.loc[signal_rows.index], size=8, line=dict(width=1, color="#ffffff")),
                customdata=np.stack([signal_rows["Signal"], signal_rows["bandar_signal_score"].fillna(0)], axis=-1),
                hovertemplate="%{x|%Y-%m-%d}<br>Close: Rp %{y:,.0f}<br>Signal: %{customdata[0]}<br>Score: %{customdata[1]}<extra></extra>",
            )
        )
    fig.add_shape(
        type="line",
        x0=start_ts,
        x1=start_ts,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="#b7791f", width=1, dash="dash"),
    )
    fig.update_layout(
        yaxis=dict(title="Close"),
        yaxis2=dict(title="Volume M", overlaying="y", side="right", showgrid=False),
        barmode="overlay",
    )
    return plotly_layout(fig, 405, f"{ticker} Price, Volume, and Signal Context")


def interactive_broker_compare(activity: pd.DataFrame, broker_codes: list[str], mode: str) -> go.Figure:
    fig = go.Figure()
    if activity.empty or not broker_codes:
        return plotly_layout(fig, 350, "Select broker codes to display flow")
    sub = activity[activity["broker_code"].isin(broker_codes)].copy()
    if sub.empty:
        return plotly_layout(fig, 350, "No rows for selected broker codes")
    pivot = sub.pivot_table(index="date", columns="broker_code", values="net_value", aggfunc="sum").sort_index()
    if mode == "Cumulative":
        pivot = pivot.cumsum()
    pivot = pivot / 1e9
    line_width = 2 if len(pivot.columns) <= 5 else 1.35
    marker_size = 6 if len(pivot.columns) <= 5 else 4
    for code in pivot.columns:
        fig.add_trace(
            go.Scatter(
                x=pivot.index,
                y=pivot[code],
                mode="lines+markers",
                name=code,
                line=dict(width=line_width),
                marker=dict(size=marker_size),
                hovertemplate=f"{code}<br>%{{x|%Y-%m-%d}}<br>Net: Rp %{{y:.2f}}B<extra></extra>",
            )
        )
    fig.add_hline(y=0, line_width=1, line_color="#94a3b8")
    y_title = "Cumulative Net Value, Rp B" if mode == "Cumulative" else "Daily Net Value, Rp B"
    fig.update_yaxes(title=y_title)
    title = "Broker Flow Comparison, Cumulative in Selected Window" if mode == "Cumulative" else "Broker Flow Comparison, Daily Net by Date"
    return plotly_layout(fig, 360, title)


def interactive_smart_flow(daily: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if daily.empty:
        return plotly_layout(fig, 320, "No smart-money flow in selected window")
    colors = np.where(daily["smart_net"] >= 0, "#0f9f6e", "#dc3545")
    fig.add_bar(
        x=daily["date"],
        y=daily["smart_net"] / 1e9,
        name="Daily Net",
        marker_color=colors,
        hovertemplate="%{x|%Y-%m-%d}<br>Daily Net: Rp %{y:.2f}B<extra></extra>",
    )
    fig.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["cumulative_net"] / 1e9,
            mode="lines+markers",
            name="Cumulative Net",
            yaxis="y2",
            line=dict(color="#2563eb", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Cumulative: Rp %{y:.2f}B<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1, line_color="#94a3b8")
    fig.update_layout(
        yaxis=dict(title="Daily, Rp B"),
        yaxis2=dict(title="Cumulative, Rp B", overlaying="y", side="right", showgrid=False),
    )
    return plotly_layout(fig, 330, "Smart-Money Daily Flow")


def interactive_event_ribbon(event_table: pd.DataFrame, horizons: tuple[int, ...], show_individual: bool) -> go.Figure:
    xs = [0, *horizons]
    fig = go.Figure()
    if event_table.empty:
        return plotly_layout(fig, 360, "No accumulation events in this window")
    cols = [f"t_plus_{h}d" for h in xs]
    values = event_table[cols].apply(pd.to_numeric, errors="coerce")
    median = values.median()
    q25 = values.quantile(0.25)
    q75 = values.quantile(0.75)
    mean_plus_5 = values["t_plus_5d"].mean() if "t_plus_5d" in values.columns else values.iloc[:, -1].mean()
    color = "#0f9f6e" if mean_plus_5 >= 100 else "#dc3545"
    x_labels = ["Signal", *[f"+{h}D" for h in horizons]]
    if show_individual:
        for idx, row in event_table.iterrows():
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=[row[col] for col in cols],
                    mode="lines",
                    line=dict(color="#94a3b8", width=1),
                    opacity=0.25,
                    showlegend=False,
                    hovertemplate=f"{row.get('ticker', '')} | {pd.Timestamp(row.get('signal_date')).date()}<br>%{{x}}: %{{y:.2f}}<extra></extra>",
                )
            )
    fig.add_trace(go.Scatter(x=x_labels, y=q75.values, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=q25.values,
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(15,159,110,0.18)" if color == "#0f9f6e" else "rgba(220,53,69,0.16)",
            line=dict(width=0),
            name="25-75 percentile",
            hovertemplate="%{x}<br>25th pct: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=median.values,
            mode="lines+markers",
            name="Median Path",
            line=dict(color=color, width=3),
            hovertemplate="%{x}<br>Median: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_hline(y=100, line_width=1, line_dash="dash", line_color="#94a3b8")
    fig.update_yaxes(title="Normalized Price")
    return plotly_layout(fig, 365, "Event Study Ribbon, Signal Date = 100")


def broker_distribution_sankey(
    dist: pd.DataFrame,
    trade_date: pd.Timestamp,
    distribution_data: dict[str, object] | None = None,
    top_n: int = 8,
) -> go.Figure:
    fig = go.Figure()
    paths = exact_broker_paths(distribution_data or {}, top_n=top_n)
    exact_mode = not paths.empty
    if paths.empty:
        paths = estimated_broker_paths(dist, top_n=top_n)
    if paths.empty:
        return plotly_layout(fig, 420, "Broker Distribution")

    buyer_nodes = []
    seller_nodes = []
    node_labels = []
    node_colors = []
    node_index: dict[str, int] = {}

    for side, code_col, type_col in (("B", "buyer_code", "buyer_type"), ("S", "seller_code", "seller_type")):
        source_df = paths[[code_col, type_col]].drop_duplicates().reset_index(drop=True)
        for row in source_df.itertuples(index=False):
            code = getattr(row, code_col)
            type_label = getattr(row, type_col)
            key = f"{side}:{code}"
            node_index[key] = len(node_labels)
            node_labels.append(code)
            node_colors.append(participant_color(type_label))
            if side == "B":
                buyer_nodes.append(key)
            else:
                seller_nodes.append(key)

    sources = []
    targets = []
    values = []
    link_colors = []
    custom = []
    for row in paths.itertuples(index=False):
        s_key = f"B:{row.buyer_code}"
        t_key = f"S:{row.seller_code}"
        sources.append(node_index[s_key])
        targets.append(node_index[t_key])
        values.append(float(row.matched_value) / 1e9)
        color = participant_color(row.buyer_type)
        link_colors.append(rgba_from_hex(color, 0.35))
        custom.append([row.buyer_code, row.seller_code, fmt_rp(row.matched_value)])

    fig.add_trace(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=16,
                thickness=12,
                line=dict(color="#d9e2ec", width=0.5),
                label=node_labels,
                color=node_colors,
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=link_colors,
                customdata=custom,
                hovertemplate="Buyer %{customdata[0]}<br>Seller %{customdata[1]}<br>Estimated matched value %{customdata[2]}<extra></extra>",
            ),
        )
    )
    fig.add_annotation(x=0.02, y=1.05, xref="paper", yref="paper", text="Buyers", showarrow=False, font=dict(color="#0f9f6e", size=12))
    fig.add_annotation(x=0.98, y=1.05, xref="paper", yref="paper", text="Sellers", showarrow=False, font=dict(color="#dc3545", size=12), xanchor="right")
    api_start = (distribution_data or {}).get("start_date")
    api_end = (distribution_data or {}).get("end_date")
    if api_start and api_end:
        date_label = f"{api_start} to {api_end}" if api_start != api_end else str(api_end)
    else:
        date_label = f"{trade_date:%Y-%m-%d}"
    title = (
        f"Broker Distribution, Exact API Counterparties on {date_label}"
        if exact_mode
        else f"Broker Distribution, Estimated Matching on {date_label}"
    )
    return plotly_layout(fig, 430, title)


def participant_color(label: str) -> str:
    return {
        "FOREIGN": "#dc3545",
        "LOCAL": "#7c3aed",
        "GOV": "#0f9f6e",
    }.get(label, "#94a3b8")


def estimated_broker_paths(dist: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    if dist.empty:
        return pd.DataFrame()
    buyers = dist[dist["net_value"] > 0].copy().sort_values("net_value", ascending=False).head(top_n)
    sellers = dist[dist["net_value"] < 0].copy().sort_values("net_value", ascending=True).head(top_n)
    if buyers.empty or sellers.empty:
        return pd.DataFrame()

    buyers["remaining"] = buyers["net_value"].astype(float)
    sellers["remaining"] = sellers["net_value"].abs().astype(float)
    edges: list[dict[str, object]] = []
    seller_idx = 0
    seller_rows = sellers.reset_index(drop=True)
    buyer_rows = buyers.reset_index(drop=True)

    for buyer_i in range(len(buyer_rows)):
        buyer_left = float(buyer_rows.loc[buyer_i, "remaining"])
        while buyer_left > 1e-9 and seller_idx < len(seller_rows):
            seller_left = float(seller_rows.loc[seller_idx, "remaining"])
            if seller_left <= 1e-9:
                seller_idx += 1
                continue
            matched = min(buyer_left, seller_left)
            edges.append(
                {
                    "buyer_code": buyer_rows.loc[buyer_i, "broker_code"],
                    "buyer_type": participant_label(buyer_rows.loc[buyer_i, "participant_type"]),
                    "seller_code": seller_rows.loc[seller_idx, "broker_code"],
                    "seller_type": participant_label(seller_rows.loc[seller_idx, "participant_type"]),
                    "matched_value": matched,
                }
            )
            buyer_left -= matched
            seller_rows.loc[seller_idx, "remaining"] = seller_left - matched
            if seller_rows.loc[seller_idx, "remaining"] <= 1e-9:
                seller_idx += 1
        buyer_rows.loc[buyer_i, "remaining"] = buyer_left
    return pd.DataFrame(edges)


def exact_broker_paths(distribution_data: dict[str, object], top_n: int = 8) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    by_value = (distribution_data or {}).get("by_value") or {}
    for buyer in (by_value.get("top_broker_buy") or [])[:top_n]:
        detail = buyer.get("detail") or {}
        for counterparty in buyer.get("distribute_to") or []:
            rows.append(
                {
                    "buyer_code": detail.get("code"),
                    "buyer_type": participant_label(detail.get("type")),
                    "seller_code": counterparty.get("code"),
  
