"""Universe manager — fetch, cache, and filter IDX listed companies.

Supports multiple universe modes:
  * "watchlist"   -> config.WATCHLIST (legacy 10 tickers)
  * "idx30"       -> IDX30 constituents
  * "lq45"        -> LQ45 constituents  
  * "idx80"       -> IDX80 constituents
  * "liquid"      -> Top liquid stocks by daily value
  * "all"         -> All listed companies (~900 tickers)
  * "custom"      -> User-defined comma-separated list

The master ticker list is fetched once from BEI and cached in PostgreSQL.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from . import config, storage

# BEI endpoints for constituents and stock summaries
_BEI_STOCK_SUMMARY = "https://www.idx.co.id/umbraco/Surface/TradingSummary/GetStockSummary"
_BEI_CONSTITUENT = "https://www.idx.co.id/umbraco/Surface/StockData/GetConstituent"

# Hard-coded index constituents (updated Aug 2026) as fallback
_IDX30 = [
    "ADRO", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "BBCA", "BBNI",
    "BBRI", "BBTN", "BMRI", "BRMS", "BRPT", "BSDE", "BUKA", "CPIN",
    "CTRA", "ESSA", "GGRM", "GOTO", "HRUM", "ICBP", "INCO", "INDF",
    "INKP", "ISAT", "ITMG", "KLBF", "MAPI", "MBMA", "MDKA", "MEDC",
    "PGAS", "PTBA", "SMGR", "TLKM", "TOWR", "UNTR", "UNVR",
]

_LQ45 = [
    "ADRO", "AMRT", "ANTM", "ARTO", "ASII", "BBCA", "BBNI", "BBRI",
    "BBTN", "BMRI", "BRPT", "BSDE", "BUKA", "CPIN", "CTRA", "ERAA",
    "ESSA", "EXCL", "GGRM", "GOTO", "HEAL", "HRUM", "ICBP", "INCO",
    "INDF", "INKP", "INTP", "ISAT", "ITMG", "JPFA", "JSMR", "KLBF",
    "MAPI", "MBMA", "MDKA", "MEDC", "MIKA", "MYOR", "PGAS", "PTBA",
    "SMGR", "TLKM", "TOWR", "UNTR", "UNVR",
]

_IDX80 = [
    "AADI", "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM",
    "ARTO", "ASII", "BBCA", "BBNI", "BBRI", "BBTN", "BFIN", "BKSL",
    "BMRI", "BRMS", "BRPT", "BSDE", "BUKA", "BUMI", "CBDK", "CMRY",
    "CPIN", "CTRA", "CUAN", "DEWA", "DSNG", "ELSA", "EMTK", "ENRG",
    "ERAA", "ESSA", "EXCL", "GGRM", "GOTO", "HEAL", "HRTA", "HRUM",
    "ICBP", "INCO", "INDF", "INDY", "INKP", "ISAT", "ITMG", "JPFA",
    "JSMR", "KIJA", "KLBF", "KPIG", "LSIP", "MAPA", "MAPI", "MBMA",
    "MDKA", "MEDC", "MIKA", "MYOR", "NCKL", "PGAS", "PGEO", "PNLF",
    "PTBA", "PTRO", "PWON", "RAJA", "RATU", "SCMA", "SMGR", "SMRA",
    "SSIA", "TAPG", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR", "WIFI",
]


def _fetch_bei_stock_summary(limit: int = 1000) -> list[dict[str, Any]]:
    """Fetch complete stock list from BEI TradingSummary endpoint."""
    try:
        resp = requests.get(
            _BEI_STOCK_SUMMARY,
            params={"start": 0, "length": limit},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("data", []) or data.get("Data", []) or []
        out = []
        for row in rows:
            code = row.get("StockCode") or row.get("code") or row.get("KodeEmiten")
            name = row.get("StockName") or row.get("name") or row.get("NamaEmiten")
            if code:
                out.append({
                    "ticker": code.upper().strip(),
                    "name": (name or "").strip(),
                    "board": (row.get("ListingBoard") or row.get("board") or "").strip(),
                    "sector": (row.get("Sector") or row.get("sector") or "").strip(),
                })
        return out
    except Exception as exc:
        print(f"[universe] BEI fetch failed: {exc}")
        return []


def _fetch_bei_constituent(index_code: str = "IHSG") -> list[str]:
    """Fetch index constituents from BEI."""
    try:
        resp = requests.get(
            _BEI_CONSTITUENT,
            params={"index": index_code},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", []) or data.get("items", []) or data.get("data", []) or []
        return [str(i.get("code") or i.get("StockCode") or i.get("ticker", "")).upper().strip() for i in items if i.get("code") or i.get("StockCode") or i.get("ticker")]
    except Exception as exc:
        print(f"[universe] BEI constituent fetch failed for {index_code}: {exc}")
        return []


def _ensure_tickers_table() -> None:
    """Create tickers master table if not exists."""
    schema = """
    CREATE TABLE IF NOT EXISTS tickers (
        ticker      VARCHAR(20) PRIMARY KEY,
        name        VARCHAR(200),
        board       VARCHAR(50),
        sector      VARCHAR(100),
        is_active   BOOLEAN DEFAULT TRUE,
        updated_at  TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_tickers_sector ON tickers(sector);
    CREATE INDEX IF NOT EXISTS idx_tickers_board ON tickers(board);
    """
    from sqlalchemy import text
    with storage.engine.begin() as conn:
        for stmt in schema.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def refresh_master_tickers(force: bool = False) -> int:
    """Fetch full ticker list from BEI and upsert into PostgreSQL.

    Returns number of tickers stored.
    """
    _ensure_tickers_table()

    # Check if we already have recent data
    if not force:
        from sqlalchemy import text
        with storage.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM tickers WHERE is_active = TRUE"))
            count = result.scalar()
            if count and count > 100:
                print(f"[universe] Using cached master tickers ({count} active). Use force=True to refresh.")
                return int(count)

    rows = _fetch_bei_stock_summary(limit=1200)
    if not rows:
        print("[universe] Warning: BEI fetch returned empty. Keeping existing tickers if any.")
        return 0

    from sqlalchemy import text
    with storage.engine.begin() as conn:
        # Mark all inactive first, then re-activate those we see
        conn.execute(text("UPDATE tickers SET is_active = FALSE"))
        for row in rows:
            conn.execute(
                text("""
                INSERT INTO tickers (ticker, name, board, sector, is_active, updated_at)
                VALUES (:ticker, :name, :board, :sector, TRUE, :updated_at)
                ON CONFLICT (ticker) DO UPDATE SET
                  name = EXCLUDED.name,
                  board = EXCLUDED.board,
                  sector = EXCLUDED.sector,
                  is_active = TRUE,
                  updated_at = EXCLUDED.updated_at
                """),
                {
                    "ticker": row["ticker"],
                    "name": row["name"],
                    "board": row["board"],
                    "sector": row["sector"],
                    "updated_at": datetime.now(timezone.utc),
                },
            )
    print(f"[universe] Refreshed {len(rows)} master tickers from BEI.")
    return len(rows)


def get_master_tickers(active_only: bool = True) -> list[str]:
    """Return all tickers from the master table."""
    _ensure_tickers_table()
    from sqlalchemy import text
    q = "SELECT ticker FROM tickers"
    if active_only:
        q += " WHERE is_active = TRUE"
    q += " ORDER BY ticker"
    with storage.engine.connect() as conn:
        df = pd.read_sql(text(q), conn)
    return df["ticker"].tolist() if not df.empty else []


def get_universe(mode: str = "watchlist", custom_list: list[str] | None = None) -> list[str]:
    """Resolve a universe mode into a concrete list of tickers.

    Parameters
    ----------
    mode : str
        One of: watchlist, idx30, lq45, idx80, all, liquid, custom.
    custom_list : list[str]
        Required when mode == "custom".

    Returns
    -------
    list[str]
        Upper-case ticker list, deduplicated and sorted.
    """
    mode = (mode or "watchlist").lower().strip()

    if mode == "watchlist":
        return sorted({t.upper() for t in config.WATCHLIST})

    if mode == "idx30":
        return sorted({t.upper() for t in _IDX30})

    if mode == "lq45":
        return sorted({t.upper() for t in _LQ45})

    if mode == "idx80":
        return sorted({t.upper() for t in _IDX80})

    if mode == "custom":
        if not custom_list:
            raise ValueError("custom_list is required when mode='custom'")
        return sorted({t.upper() for t in custom_list if t.strip()})

    if mode == "all":
        tickers = get_master_tickers(active_only=True)
        if not tickers:
            print("[universe] Master tickers empty. Refreshing from BEI...")
            refresh_master_tickers()
            tickers = get_master_tickers(active_only=True)
        if not tickers:
            print("[universe] Warning: Falling back to IDX80 because BEI fetch failed.")
            tickers = _IDX80
        return tickers

    if mode == "liquid":
        # Liquid = intersection of IDX80 + those with recent broker data
        tickers = get_master_tickers(active_only=True)
        if not tickers:
            tickers = _IDX80
        # Try to further filter to those with actual trading volume
        # For now, use IDX80 as liquid proxy + any watchlist items
        liquid = set(_IDX80) | set(config.WATCHLIST)
        return sorted({t.upper() for t in liquid})

    raise ValueError(f"Unknown universe mode: {mode}. Choose from: watchlist, idx30, lq45, idx80, all, liquid, custom")


def get_universe_info() -> dict[str, Any]:
    """Return metadata about available universes."""
    master_count = len(get_master_tickers(active_only=True))
    return {
        "watchlist": len(config.WATCHLIST),
        "idx30": len(_IDX30),
        "lq45": len(_LQ45),
        "idx80": len(_IDX80),
        "all_cached": master_count,
        "all_estimated": 900,  # rough IDX total
    }


import pandas as pd


