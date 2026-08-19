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
    # Header siluman tingkat tinggi (Spoofing Google Chrome Modern di Windows)
    session.headers.update({
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Host': 'www.idx.co.id',
        'Origin': 'https://www.idx.co.id',
        'Referer': 'https://www.idx.co.id/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    })
    
    try:
        # Memancing cookie dengan mengunjungi halaman beranda layaknya manusia
        session.get("https://www.idx.co.id/id", timeout=15.0)
        time.sleep(0.5)
        # Validasi session
        session.get("https://www.idx.co.id/primary/home/GetIndexList", timeout=15.0)
    except Exception as e:
        pass # Abaikan jika gagal memancing, lanjut gunakan header yang ada
        
    return session

# Simpan sesi secara global agar tidak membuat koneksi baru setiap ganti ticker
_SESSION = None

def _ensure_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _get_idx_session()
    return _SESSION


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> tuple[pd.DataFrame, int]:
    """Daily OHLCV for one ticker fetched directly from IDX."""
    global _SESSION
    cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    sym = ticker.upper().strip()
    
    session = _ensure_session()
    url = f"https://www.idx.co.id/primary/ListedCompany/GetTradingInfoSS?code={sym}&start=0&length=1000"
    
    last_status = 200
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=15.0)
            last_status = resp.status_code
            
            # Jika terkena blokir WAF (403) atau Rate Limit (429)
            if last_status in (403, 429):
                print(f"[prices] {sym} tertahan (Status {last_status}), memulihkan sesi... (percobaan {attempt+1})")
                time.sleep(random.uniform(2.0, 5.0))
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
                return df.sort_values("date").reset_index(drop=True), 200
                
            # Jika data sukses ditarik tapi memang kosong
            return pd.DataFrame(columns=cols), 200
            
        except requests.exceptions.RequestException as exc:
            print(f"[prices] API IDX gagal untuk {sym} (percobaan {attempt+1}/{max_retries}): {type(exc).__name__}")
            last_status = 500
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1.0, 3.0))
        except Exception as e:
            print(f"[prices] Error memproses data untuk {sym}: {e}")
            last_status = 500
            break
            
    return pd.DataFrame(columns=cols), last_status


def fetch_history_many(tickers: list[str], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Daily OHLCV for several tickers, concatenated into one tidy table."""
    frames = []
    total = len(tickers)
    consecutive_403 = 0
    
    for i, t in enumerate(tickers):
        # ── SIRKUIT BREAKER ──
        if consecutive_403 >= 3:
            print("\n[prices] 🚨 SIRKUIT BREAKER AKTIF: IP Anda diblokir permanen oleh Firewall IDX (Status 403).")
            print("[prices] ⏭️ Menghentikan penarikan harga saham agar proses backfill broker Stockbit tetap bisa berjalan...\n")
            break
            
        df, status = fetch_history(t, period=period, interval=interval)
        
        if status == 403:
            consecutive_403 += 1
        else:
            consecutive_403 = 0 # Reset jika berhasil
            
        if not df.empty:
            frames.append(df)
            
        # ── LOGIKA JEDA (ANTI-BLOCK/STEALTH MODE) ──
        if i < total - 1 and status != 403:
            time.sleep(random.uniform(0.3, 1.2))
            if (i + 1) % 50 == 0:
                print(f"[prices] Progress Harga IDX: {i+1}/{total} saham ditarik. Beristirahat sejenak...")
                time.sleep(random.uniform(3.0, 6.0))
                
    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    return pd.concat(frames, ignore_index=True)
