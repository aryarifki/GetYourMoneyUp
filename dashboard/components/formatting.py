"""Formatting utilities — signal names, currency, percentages, labels."""

from __future__ import annotations

import numpy as np
import pandas as pd


PROFILE_META = {
    "smart_foreign": ("Foreign Smart Money", "Directional foreign institutions"),
    "local_institutional": ("Local Institutions", "Local institution-like accounts"),
    "market_maker": ("Market Makers", "Active on both sides; net position matters"),
    "bandar_gorengan": ("Speculative Operators", "Speculative operator profile"),
    "retail": ("Retail-Dominant", "Retail-heavy platforms"),
    "lainnya": ("Other Brokers", "Outside defined behavioral profiles"),
}

SMART_PROFILES = {"smart_foreign", "local_institutional"}
ACC_SIGNALS = {"STRONG_ACCUMULATION", "ACCUMULATION", "NET_BUY", "AKUMULASI_KUAT", "AKUMULASI"}
DIST_SIGNALS = {"STRONG_DISTRIBUTION", "DISTRIBUTION", "NET_SELL", "DISTRIBUSI_KUAT", "DISTRIBUSI"}


def fmt_signal(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    mapping = {
        "AKUMULASI_KUAT": "Strong Accumulation",
        "AKUMULASI": "Accumulation",
        "DISTRIBUSI_KUAT": "Strong Distribution",
        "DISTRIBUSI": "Distribution",
        "NETRAL": "Neutral",
        "STRONG_ACCUMULATION": "Strong Accumulation",
        "ACCUMULATION": "Accumulation",
        "NET_BUY": "Net Buy",
        "STRONG_DISTRIBUTION": "Strong Distribution",
        "DISTRIBUTION": "Distribution",
        "NET_SELL": "Net Sell",
        "NEUTRAL": "Neutral",
    }
    text = str(value)
    return mapping.get(text, text.replace("_", " ").title())


def fmt_rp(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    n = float(value)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1e12:
        return f"{sign}Rp {n / 1e12:.2f} T"
    if n >= 1e9:
        return f"{sign}Rp {n / 1e9:.2f} B"
    if n >= 1e6:
        return f"{sign}Rp {n / 1e6:.2f} M"
    return f"{sign}Rp {n:,.0f}"


def fmt_pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.2%}"


def participant_label(value: object) -> str:
    return {"Asing": "FOREIGN", "Lokal": "LOCAL", "Pemerintah": "GOV"}.get(str(value), str(value or "-"))


def english_text(value: object) -> object:
    if value is None or pd.isna(value):
        return value
    mapping = {
        "Asing": "Foreign",
        "Lokal": "Local",
        "Pemerintah": "Government",
        "AKUMULASI_KUAT": "Strong Accumulation",
        "AKUMULASI": "Accumulation",
        "DISTRIBUSI_KUAT": "Strong Distribution",
        "DISTRIBUSI": "Distribution",
        "NETRAL": "Neutral",
    }
    return mapping.get(str(value), value)


def signed_color(value: float) -> str:
    return "#0f9f6e" if value >= 0 else "#dc3545"


def score_tone(score: float) -> tuple[str, str]:
    if score < 40:
        return "negative", "#f43f5e"
    if score <= 70:
        return "warning", "#f59e0b"
    return "positive", "#10b981"


def broker_subtype(row: pd.Series) -> str:
    if participant_label(row.get("Type") or row.get("participant_type")) != "FOREIGN":
        return "-"
    net = abs(float(row.get("Net", row.get("net_value", 0)) or 0))
    freq = max(float(row.get("Freq", row.get("frequency", 0)) or 0), 1)
    avg_value = net / freq
    if avg_value >= 500_000_000 or (net >= 5_000_000_000 and freq <= 500):
        return "Institutional"
    if freq >= 2_000 or avg_value <= 100_000_000:
        return "Speculative"
    return "Mixed"


def rgba_from_hex(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return f"rgba(148,163,184,{alpha})"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
  
