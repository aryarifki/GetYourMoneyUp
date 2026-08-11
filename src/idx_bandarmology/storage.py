"""PostgreSQL storage — the landing zone for the pipeline.

Replaces SQLite with psycopg2. All public function signatures stay identical
so analysis.py, pipeline.py, and the dashboard need zero changes.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from . import config

# ── schema ───────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    date    DATE NOT NULL,
    ticker  VARCHAR(20) NOT NULL,
    open    NUMERIC,
    high    NUMERIC,
    low     NUMERIC,
    close   NUMERIC,
    volume  BIGINT,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS broker_flow (
    date                DATE NOT NULL,
    ticker              VARCHAR(20) NOT NULL,
    bandar_signal       VARCHAR(50),
    bandar_signal_score NUMERIC,
    foreign_net_broker  NUMERIC,
    local_net_broker    NUMERIC,
    gov_net_broker      NUMERIC,
    foreign_net_flow    NUMERIC,
    domestic_net_flow   NUMERIC,
    total_value         NUMERIC,
    foreign_signal      VARCHAR(50),
    conclusion_broker   TEXT,
    conclusion_flow     TEXT,
    fetched_at          TIMESTAMP,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS broker_activity (
    date             DATE NOT NULL,
    ticker           VARCHAR(20) NOT NULL,
    broker_code      VARCHAR(20) NOT NULL,
    participant_type VARCHAR(20),
    buy_value        NUMERIC,
    sell_value       NUMERIC,
    net_value        NUMERIC,
    buy_lot          NUMERIC,
    sell_lot         NUMERIC,
    frequency        NUMERIC,
    buy_avg_price    NUMERIC,
    sell_avg_price   NUMERIC,
    fetched_at       TIMESTAMP,
    PRIMARY KEY (date, ticker, broker_code)
);

CREATE TABLE IF NOT EXISTS runs (
    run_at   TIMESTAMP NOT NULL,
    tickers  TEXT,
    n_prices INTEGER,
    n_broker INTEGER,
    notes    TEXT
);

-- indexes for fast dashboard reads
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);
CREATE INDEX IF NOT EXISTS idx_broker_flow_ticker_date ON broker_flow(ticker, date);
CREATE INDEX IF NOT EXISTS idx_broker_activity_ticker_date ON broker_activity(ticker, date);
CREATE INDEX IF NOT EXISTS idx_broker_activity_broker ON broker_activity(broker_code);
"""


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist yet."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
        conn.commit()


def _clean_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """Replace NaN/inf with None so PostgreSQL accepts them."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype.kind in "fc":  # float or complex
            df[col] = df[col].replace([float("inf"), float("-inf")], None)
            df[col] = df[col].where(df[col].notna(), None)
    return df


def upsert_prices(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = _clean_numeric_df(df)
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    rows = [tuple(row) for row in df[cols].values]

    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO prices (date, ticker, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (date, ticker) DO UPDATE SET
                  open = EXCLUDED.open,
                  high = EXCLUDED.high,
                  low = EXCLUDED.low,
                  close = EXCLUDED.close,
                  volume = EXCLUDED.volume
                """,
                rows,
                template=None,
                page_size=1000,
            )
        conn.commit()
    return len(df)


def upsert_broker_flow(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = _clean_numeric_df(df)
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    cols = [
        "date", "ticker", "bandar_signal", "bandar_signal_score",
        "foreign_net_broker", "local_net_broker", "gov_net_broker",
        "foreign_net_flow", "domestic_net_flow", "total_value",
        "foreign_signal", "conclusion_broker", "conclusion_flow", "fetched_at",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    rows = [tuple(row) for row in df[cols].values]

    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO broker_flow (
                    date, ticker, bandar_signal, bandar_signal_score,
                    foreign_net_broker, local_net_broker, gov_net_broker,
                    foreign_net_flow, domestic_net_flow, total_value,
                    foreign_signal, conclusion_broker, conclusion_flow, fetched_at
                )
                VALUES %s
                ON CONFLICT (date, ticker) DO UPDATE SET
                  bandar_signal = EXCLUDED.bandar_signal,
                  bandar_signal_score = EXCLUDED.bandar_signal_score,
                  foreign_net_broker = EXCLUDED.foreign_net_broker,
                  local_net_broker = EXCLUDED.local_net_broker,
                  gov_net_broker = EXCLUDED.gov_net_broker,
                  foreign_net_flow = EXCLUDED.foreign_net_flow,
                  domestic_net_flow = EXCLUDED.domestic_net_flow,
                  total_value = EXCLUDED.total_value,
                  foreign_signal = EXCLUDED.foreign_signal,
                  conclusion_broker = EXCLUDED.conclusion_broker,
                  conclusion_flow = EXCLUDED.conclusion_flow,
                  fetched_at = EXCLUDED.fetched_at
                """,
                rows,
                page_size=1000,
            )
        conn.commit()
    return len(df)


def upsert_broker_activity(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = _clean_numeric_df(df)
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    cols = [
        "date", "ticker", "broker_code", "participant_type",
        "buy_value", "sell_value", "net_value",
        "buy_lot", "sell_lot", "frequency",
        "buy_avg_price", "sell_avg_price", "fetched_at",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    rows = [tuple(row) for row in df[cols].values]

    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO broker_activity (
                    date, ticker, broker_code, participant_type,
                    buy_value, sell_value, net_value,
                    buy_lot, sell_lot, frequency,
                    buy_avg_price, sell_avg_price, fetched_at
                )
                VALUES %s
                ON CONFLICT (date, ticker, broker_code) DO UPDATE SET
                  participant_type = EXCLUDED.participant_type,
                  buy_value = EXCLUDED.buy_value,
                  sell_value = EXCLUDED.sell_value,
                  net_value = EXCLUDED.net_value,
                  buy_lot = EXCLUDED.buy_lot,
                  sell_lot = EXCLUDED.sell_lot,
                  frequency = EXCLUDED.frequency,
                  buy_avg_price = EXCLUDED.buy_avg_price,
                  sell_avg_price = EXCLUDED.sell_avg_price,
                  fetched_at = EXCLUDED.fetched_at
                """,
                rows,
                page_size=1000,
            )
        conn.commit()
    return len(df)


def log_run(tickers: list[str], n_prices: int, n_broker: int, notes: str = "") -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO runs (run_at, tickers, n_prices, n_broker, notes) VALUES (%s, %s, %s, %s, %s)",
                (datetime.now(timezone.utc), ",".join(tickers), n_prices, n_broker, notes),
            )
        conn.commit()


def read_prices(tickers: list[str] | None = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM prices"
    params = None
    if tickers:
        q += " WHERE ticker = ANY(%s)"
        params = ([t.upper() for t in tickers],)
    with get_conn() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def read_broker_flow(tickers: list[str] | None = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM broker_flow"
    params = None
    if tickers:
        q += " WHERE ticker = ANY(%s)"
        params = ([t.upper() for t in tickers],)
    with get_conn() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def read_broker_activity(tickers: list[str] | None = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM broker_activity"
    params = None
    if tickers:
        q += " WHERE ticker = ANY(%s)"
        params = ([t.upper() for t in tickers],)
    with get_conn() as conn:
        df = pd.read_sql(q, conn, params=params, parse_dates=["date"])
    return df.sort_values(["ticker", "date", "net_value"], ascending=[True, True, False]).reset_index(drop=True)


def read_runs() -> pd.DataFrame:
    init_db()
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM runs ORDER BY run_at DESC", conn, parse_dates=["run_at"])
 
