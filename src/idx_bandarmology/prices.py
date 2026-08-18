"""IDX API client — daily OHLCV history for IDX tickers.

This module replaces yfinance and fetches historical data directly
from the IDX endpoints using session cookies to bypass blocks.
"""

from __future__ import annotations

import pandas as pd
import requests


def _get_idx_session() -> requests.Session:
    """Mengemulasi fungsi ensureSession() dari IDX-API BaseClient untuk menembus proteksi BEI."""
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
        'Referer': 'https://www.idx.co.id/',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    })
    
    try:
        # Trik ensureSession: Dapatkan Cookie dari halaman utama
        session.get("https://www.idx.co.id/id", timeout=15.0)
        # Validasi session
        session.get("https://www.idx.co.id/primary/home/GetIndexList", timeout=15.0)
    except Exception as e:
        print(f"[prices] Gagal menginisialisasi sesi IDX: {e}")
        
    return session


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Daily OHLCV for one ticker fetched directly from IDX.

    Returns a tidy DataFrame with columns:
    ``date, ticker, open, high, low, close, volume``
    (empty DataFrame with these columns if fetch fails).
    
    Note: `period` and `interval` parameters are kept for compatibility 
    with the pipeline orchestrator, but the API fetches up to 1000 days natively.
    """
    cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    sym = ticker.upper().strip()
    
    session = _get_idx_session()
    # length=1000 menarik sekitar 4 tahun data hari perdagangan (sangat cukup untuk analisis 1y)
    url = f"https://www.idx.co.id/primary/ListedCompany/GetTradingInfoSS?code={sym}&start=0&length=1000"
    
    try:
        resp = session.get(url, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        
        rows = []
        for item in data.get("replies", []):
            rows.append({
                "date": pd.to_datetime(item.get("Date")).date(),
                "ticker": sym,
                "open": float(item.get("OpenPrice", 0)),
                "high": float(item.get("High", 0)),
                "low": float(item.get("Low", 0)),
                "close": float(item.get("Close", 0)),
                "volume": int(item.get("Volume", 0)),
            })
            
        if rows:
            df = pd.DataFrame(rows)[cols]
            # Urutkan berdasarkan tanggal (ascending) agar sistem fitur (forward/backward) berfungsi benar
            return df.sort_values("date").reset_index(drop=True)
            
    except Exception as exc:
        print(f"[prices] API IDX gagal untuk {sym}: {type(exc).__name__}")
        
    return pd.DataFrame(columns=cols)


def fetch_history_many(tickers: list[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Daily OHLCV for several tickers, concatenated into one tidy table."""
    frames = [fetch_history(t, period=period, interval=interval) for t in tickers]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    return pd.concat(frames, ignore_index=True)
