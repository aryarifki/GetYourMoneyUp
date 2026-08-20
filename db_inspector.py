#!/usr/bin/env python3
"""Database Inspector — verify PostgreSQL contents for IDX Bandarmology."""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from idx_bandarmology import storage, config

st.set_page_config(page_title="DB Inspector", layout="wide")

# ── helpers ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_db_info() -> dict:
    """Parse DATABASE_URL safely (no password shown)."""
    url = config.DATABASE_URL
    # mask password
    display_url = url
    if "@" in url:
        try:
            proto, rest = url.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                display_url = f"{proto}://{user}:****@{hostpart}"
            else:
                display_url = f"{proto}://{creds}:****@{hostpart}"
        except Exception:
            pass
    return {"display_url": display_url, "raw_url": url}


@st.cache_data(ttl=60)
def table_counts() -> pd.DataFrame:
    """Get row counts and exact physical sizes of user tables."""
    engine = storage.engine
    q = """
    SELECT 
        schemaname, 
        relname AS table_name, 
        n_live_tup AS row_count,
        pg_size_pretty(pg_total_relation_size(relid)) AS table_size,
        pg_total_relation_size(relid) AS size_bytes
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY size_bytes DESC;
    """
    try:
        df = pd.read_sql(text(q), engine)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    return df


@st.cache_data(ttl=60)
def database_overall_size() -> dict:
    """Get the absolute true size of the entire PostgreSQL database on disk."""
    engine = storage.engine
    q = """
    SELECT 
        pg_size_pretty(pg_database_size(current_database())) AS pretty_size, 
        pg_database_size(current_database()) AS bytes_size;
    """
    try:
        df = pd.read_sql(text(q), engine)
        return {"pretty": df["pretty_size"].iloc[0], "bytes": df["bytes_size"].iloc[0]}
    except Exception:
        return {"pretty": "0 B", "bytes": 0}


def live_table_counts() -> pd.DataFrame:
    """Non-cached version of table_counts for live monitoring."""
    engine = storage.engine
    q = """
    SELECT 
        'prices' as table_name, (SELECT count(*) FROM prices) as exact_count
    UNION ALL
    SELECT 
        'broker_flow' as table_name, (SELECT count(*) FROM broker_flow) as exact_count
    UNION ALL
    SELECT 
        'broker_activity' as table_name, (SELECT count(*) FROM broker_activity) as exact_count;
    """
    try:
        df = pd.read_sql(text(q), engine)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    return df


@st.cache_data(ttl=60)
def table_date_ranges() -> pd.DataFrame:
    engine = storage.engine
    queries = {
        "prices": "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT ticker) as tickers FROM prices",
        "broker_flow": "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT ticker) as tickers FROM broker_flow",
        "broker_activity": "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT ticker) as tickers FROM broker_activity",
        "runs": "SELECT MIN(run_at)::date as min_date, MAX(run_at)::date as max_date, COUNT(*) as total_runs FROM runs",
        "tickers": "SELECT COUNT(*) as total_tickers, COUNT(*) FILTER (WHERE is_active = TRUE) as active_tickers FROM tickers",
    }
    rows = []
    for table, q in queries.items():
        try:
            df = pd.read_sql(text(q), engine)
            row = df.iloc[0].to_dict()
            row["table"] = table
            rows.append(row)
        except Exception as e:
            rows.append({"table": table, "error": str(e)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def get_ticker_list(table: str) -> pd.DataFrame:
    engine = storage.engine
    if table == "tickers":
        q = "SELECT ticker, name, board, sector, is_active, updated_at FROM tickers ORDER BY ticker"
    else:
        q = f"SELECT DISTINCT ticker FROM {table} ORDER BY ticker"
    try:
        return pd.read_sql(text(q), engine)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


@st.cache_data(ttl=60)
def get_date_gaps(table: str, ticker: str | None = None) -> pd.DataFrame:
    engine = storage.engine
    if ticker:
        q = f"""
        WITH dates AS (
            SELECT generate_series(
                (SELECT MIN(date) FROM {table} WHERE ticker = :t),
                (SELECT MAX(date) FROM {table} WHERE ticker = :t),
                '1 day'::interval
            )::date AS date
        )
        SELECT d.date
        FROM dates d
        LEFT JOIN {table} t ON d.date = t.date AND t.ticker = :t
        WHERE t.date IS NULL AND EXTRACT(ISODOW FROM d.date) < 6
        ORDER BY d.date DESC
        LIMIT 100
        """
        df = pd.read_sql(text(q), engine, params={"t": ticker})
    else:
        q = f"""
        WITH daily AS (
            SELECT date, COUNT(DISTINCT ticker) as n_tickers
            FROM {table}
            GROUP BY date
            ORDER BY date DESC
            LIMIT 90
        )
        SELECT * FROM daily
        """
        df = pd.read_sql(text(q), engine)
    return df


@st.cache_data(ttl=60)
def sample_rows(table: str, limit: int = 20) -> pd.DataFrame:
    engine = storage.engine
    try:
        return pd.read_sql(text(f"SELECT * FROM {table} ORDER BY date DESC LIMIT {limit}"), engine)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


@st.cache_data(ttl=60)
def backfill_progress() -> dict:
    pfile = _ROOT / "data" / "backfill_progress.json"
    if not pfile.exists():
        return {}
    import json
    return json.loads(pfile.read_text(encoding="utf-8"))


def format_bytes(size: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


# ── UI ────────────────────────────────────────────────────────────────────

st.title("🗄️ Database Inspector")
st.caption("Verify PostgreSQL contents for IDX Bandarmology")

db_info = get_db_info()
with st.sidebar:
    st.header("Connection")
    st.code(db_info["display_url"], language="text")
    st.caption("Password masked for security")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ── Top metrics ───────────────────────────────────────────────────────────
counts = table_counts()
db_size_info = database_overall_size()

if "error" not in counts.columns:
    total_rows = int(counts["row_count"].sum()) if not counts.empty else 0
    total_tables = len(counts)
    total_bytes = int(counts["size_bytes"].sum()) if not counts.empty else 0
    table_data_size = format_bytes(total_bytes)
else:
    total_rows, total_tables, table_data_size = 0, 0, "0 B"

ranges = table_date_ranges()

# Merombak layout menjadi 6 kolom agar informasinya padat & jelas
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Tables", total_tables)
with c2:
    st.metric("Total Rows", f"{total_rows:,}")
with c3:
    st.metric("Data Size (Tables)", table_data_size, help="Ukuran bersih khusus data tabel Anda.")
with c4:
    st.metric("Total DB Size", db_size_info["pretty"], help="Ukuran fisik absolut PostgreSQL di disk (termasuk cache, index, dan log internal).")
with c5:
    tickers_row = ranges[ranges["table"] == "tickers"]
    active = int(tickers_row["active_tickers"].iloc[0]) if not tickers_row.empty else 0
    st.metric("Active Tickers", active)
with c6:
    runs_row = ranges[ranges["table"] == "runs"]
    total_runs = int(runs_row["total_runs"].iloc[0]) if not runs_row.empty else 0
    st.metric("Pipeline Runs", total_runs)

# ── Tabs ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", "📋 Tables", "📅 Date Gaps", "🔍 Samples", "🔄 Backfill Status", "📦 Live Batch Monitor"
])

with tab1:
    st.subheader("Date Ranges per Table")
    if not ranges.empty:
        st.dataframe(ranges, use_container_width=True, hide_index=True)

    st.subheader("Row Counts & Storage Size")
    if not counts.empty:
        # Hide the raw size_bytes column for cleaner UI
        display_counts = counts.drop(columns=["size_bytes"])
        st.dataframe(display_counts, use_container_width=True, hide_index=True)

    # Visual: rows per table
    if not counts.empty:
        fig = px.bar(counts, x="table_name", y="row_count", text="row_count",
                     title="Row Count by Table", color="table_name")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Ticker Coverage")
    tbl = st.selectbox("Table", ["prices", "broker_flow", "broker_activity", "tickers"], key="ticker_tbl")
    tdf = get_ticker_list(tbl)
    st.write(f"Total: {len(tdf)} records")
    st.dataframe(tdf, use_container_width=True, height=500)

with tab3:
    st.subheader("Detect Missing Dates")
    tbl_gap = st.selectbox("Table", ["prices", "broker_flow", "broker_activity"], key="gap_tbl")
    tickers = get_ticker_list(tbl_gap)["ticker"].tolist() if tbl_gap != "broker_activity" else []
    
    use_ticker = st.checkbox("Filter by specific ticker", value=False)
    sel_ticker = None
    if use_ticker and tickers:
        sel_ticker = st.selectbox("Ticker", tickers, key="gap_ticker")
    
    gaps = get_date_gaps(tbl_gap, sel_ticker)
    if gaps.empty:
        st.success("No gaps detected in the selected range (or all dates present).")
    else:
        st.warning(f"Found {len(gaps)} missing dates (weekends excluded)")
        st.dataframe(gaps, use_container_width=True)

    # Daily counts chart
    st.subheader("Daily Row Counts (Last 90 days)")
    daily = get_date_gaps(tbl_gap, None)  # reused helper for daily stats
    if not daily.empty and "n_tickers" in daily.columns:
        fig = px.bar(daily, x="date", y="n_tickers", title=f"{tbl_gap} — distinct tickers per day")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Latest Rows")
    tbl_samp = st.selectbox("Table", ["prices", "broker_flow", "broker_activity", "runs"], key="sample_tbl")
    lim = st.slider("Limit", 5, 100, 20)
    sdf = sample_rows(tbl_samp, lim)
    st.dataframe(sdf, use_container_width=True)

with tab5:
    st.subheader("Backfill Progress (Local File)")
    prog = backfill_progress()
    if not prog:
        st.info("No backfill_progress.json found. Run backfill_monthly.py first.")
    else:
        st.json(prog)
        completed = prog.get("completed", [])
        failed = prog.get("failed", {})
        st.write(f"✅ Completed: {len(completed)} months")
        st.write(f"❌ Failed: {len(failed)} months")
        if failed:
            st.error("Failed months:")
            for m, e in failed.items():
                st.write(f"- {m}: {e}")

with tab6:
    st.subheader("📦 Live Batch Monitor")
    st.caption("Monitor exact row counts in real-time. Useful for tracking micro-batching progress during an active pipeline run.")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        auto_refresh = st.toggle("Enable Auto-Refresh", value=False)
        refresh_rate = st.slider("Refresh interval (seconds)", min_value=2, max_value=15, value=5, disabled=not auto_refresh)
    
    placeholder = st.empty()
    
    if auto_refresh:
        # Loop for live updates
        while True:
            live_df = live_table_counts()
            with placeholder.container():
                if "error" in live_df.columns:
                    st.error(f"Error reading DB: {live_df['error'].iloc[0]}")
                else:
                    mc1, mc2, mc3 = st.columns(3)
                    
                    price_val = live_df[live_df['table_name'] == 'prices']['exact_count'].values
                    flow_val = live_df[live_df['table_name'] == 'broker_flow']['exact_count'].values
                    act_val = live_df[live_df['table_name'] == 'broker_activity']['exact_count'].values
                    
                    p_cnt = int(price_val[0]) if len(price_val) else 0
                    f_cnt = int(flow_val[0]) if len(flow_val) else 0
                    a_cnt = int(act_val[0]) if len(act_val) else 0
                    
                    mc1.metric("Prices Rows", f"{p_cnt:,}")
                    mc2.metric("Broker Flow Rows", f"{f_cnt:,}")
                    mc3.metric("Broker Activity Rows", f"{a_cnt:,}")
                    
                    st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")
            
            time.sleep(refresh_rate)
    else:
        # Static render with manual refresh button
        if st.button("Click to Refresh Live Counts", type="primary"):
            live_df = live_table_counts()
            with placeholder.container():
                if "error" in live_df.columns:
                    st.error(f"Error reading DB: {live_df['error'].iloc[0]}")
                else:
                    mc1, mc2, mc3 = st.columns(3)
                    
                    price_val = live_df[live_df['table_name'] == 'prices']['exact_count'].values
                    flow_val = live_df[live_df['table_name'] == 'broker_flow']['exact_count'].values
                    act_val = live_df[live_df['table_name'] == 'broker_activity']['exact_count'].values
                    
                    p_cnt = int(price_val[0]) if len(price_val) else 0
                    f_cnt = int(flow_val[0]) if len(flow_val) else 0
                    a_cnt = int(act_val[0]) if len(act_val) else 0
                    
                    mc1.metric("Prices Rows", f"{p_cnt:,}")
                    mc2.metric("Broker Flow Rows", f"{f_cnt:,}")
                    mc3.metric("Broker Activity Rows", f"{a_cnt:,}")
                    
                    st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")
        else:
            with placeholder.container():
                st.info("Click the button above or enable Auto-Refresh to start monitoring.")

st.caption("DB Inspector — IDX Bandarmology")
