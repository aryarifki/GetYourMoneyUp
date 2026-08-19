"""IDX API client — daily OHLCV history for IDX tickers.

This module replaces yfinance and fetches historical data directly
from the IDX endpoints using session cookies to bypass blocks.
"""

from __future__ import annotations

import random
import time
import pandas as pd
import requests


def _get_idx_session() -> requests.Session:
    """Mengemulasi fungsi ensureSession() dari IDX-API BaseClient untuk menembus proteksi BEI."""
    session = requests.Session()
    # Menggunakan User-Agent umum untuk menyamar sebagai peramban biasa
    session.headers.update({
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
        'Referer': 'https://www.idx.co.id/',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    try:
        # Trik ensureSession: Dapatkan Cookie dari halaman utama terlebih dahulu
        session.get("https://www.idx.co.id/id", timeout=15.0)
        # Validasi session dengan memanggil endpoint ringan
        session.get("https://www.idx.co.id/primary/home/GetIndexList", timeout=15.0)
    except Exception as e:
        print(f"[prices] Gagal menginisialisasi sesi IDX: {e}")
        
    return session

# Simpan sesi secara global agar tidak membuat koneksi baru setiap ganti ticker
_SESSION = None

def _ensure_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _get_idx_session()
    return _SESSION


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Daily OHLCV for one ticker fetched directly from IDX.

    Returns a tidy DataFrame with columns:
    ``date, ticker, open, high, low, close, volume``
    """
    global _SESSION
    cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    sym = ticker.upper().strip()
    
    session = _ensure_session()
    # length=1000 menarik sekitar 4 tahun data hari perdagangan
    url = f"https://www.idx.co.id/primary/ListedCompany/GetTradingInfoSS?code={sym}&start=0&length=1000"
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=15.0)
            
            # Jika terkena blokir WAF (403) atau Rate Limit (429), perbarui sesi dan tunggu
            if resp.status_code in (403, 429):
                print(f"[prices] {sym} tertahan (Status {resp.status_code}), memulihkan sesi... (percobaan {attempt+1})")
                time.sleep(random.uniform(2.0, 5.0))
                # Paksa buat cookie baru
                session = _get_idx_session()
                _SESSION = session
                continue
                
            resp.raise_for_status()
            data = resp.json()
            
            rows = []
            for item in data.get("replies", []) or []:
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
                # Urutkan berdasarkan tanggal (ascending)
                return df.sort_values("date").reset_index(drop=True)
            
            # Jika data sukses ditarik tapi memang kosong, langsung kembalikan dataframe kosong
            return pd.DataFrame(columns=cols)
            
        except requests.exceptions.RequestException as exc:
            print(f"[prices] API IDX gagal untuk {sym} (percobaan {attempt+1}/{max_retries}): {type(exc).__name__}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1.0, 3.0))
        except Exception as e:
            print(f"[prices] Error memproses data untuk {sym}: {e}")
            break
            
    return pd.DataFrame(columns=cols)


def fetch_history_many(tickers: list[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Daily OHLCV for several tickers, concatenated into one tidy table."""
    frames = []
    total = len(tickers)
    
    for i, t in enumerate(tickers):
        df = fetch_history(t, period=period, interval=interval)
        if not df.empty:
            frames.append(df)
            
        # ── LOGIKA JEDA (ANTI-BLOCK/STEALTH MODE) ──
        if i < total - 1:
            # Jeda acak antara 0.3 sampai 1.2 detik setiap selesai 1 ticker
            time.sleep(random.uniform(0.3, 1.2))
            
            # Berhenti sejenak lebih lama setiap kelipatan 50 saham agar API tidak curiga
            if (i + 1) % 50 == 0:
                print(f"[prices] Progress Harga IDX: {i+1}/{total} saham ditarik. Beristirahat sejenak...")
                time.sleep(random.uniform(3.0, 6.0))
                
    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    return pd.concat(frames, ignore_index=True)
