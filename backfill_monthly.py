#!/usr/bin/env python3
"""Backfill broker data per bulan dengan progress tracking per universe & resume.

Usage:
    python3 backfill_monthly.py --universe idx80 --months all
    python3 backfill_monthly.py --universe all --months 2026-01,2026-02
    python3 backfill_monthly.py --status
    python3 backfill_monthly.py --reset-progress
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# ── path setup ─────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from idx_bandarmology import pipeline, storage, universe as universe_mod
from idx_bandarmology.broker_api import set_rate_limit

# ── konfigurasi ────────────────────────────────────────────────────────────
_PROGRESS_FILE = _ROOT / "data" / "backfill_progress.json"
_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

_PAUSE_BETWEEN_MONTHS = 15

# ── helper progress ────────────────────────────────────────────────────────

def load_progress() -> dict:
    if _PROGRESS_FILE.exists():
        try:
            data = json.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
            # Auto-Migrasi dari format lama (list) ke format baru (dict per universe)
            if "completed" in data and isinstance(data["completed"], list):
                print("🔄 Melakukan migrasi format log progress lama (default ke idx80)...")
                return {
                    "started_at": data.get("started_at"),
                    "last_run": data.get("last_run"),
                    "universes": {
                        "idx80": {
                            "completed": data["completed"],
                            "failed": data.get("failed", {})
                        }
                    }
                }
            return data
        except json.JSONDecodeError:
            pass
    return {"started_at": None, "last_run": None, "universes": {}}

def save_progress(p: dict) -> None:
    p["last_run"] = datetime.now().isoformat()
    _PROGRESS_FILE.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")

def get_universe_progress(progress: dict, universe: str) -> dict:
    if "universes" not in progress:
        progress["universes"] = {}
    if universe not in progress["universes"]:
        progress["universes"][universe] = {"completed": [], "failed": {}}
    return progress["universes"][universe]

# ── helper tanggal & estimasi ──────────────────────────────────────────────

def get_month_ranges(end_date: date | None = None, months_back: int = 12) -> list[tuple[date, date, str]]:
    if end_date is None:
        end_date = date.today()

    ranges = []
    for i in range(months_back):
        year = end_date.year
        month = end_date.month - i
        while month <= 0:
            month += 12
            year -= 1

        start = date(year, month, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        end = next_month - timedelta(days=1)

        if end > date.today():
            end = date.today()

        label = f"{year}-{month:02d}"
        ranges.append((start, end, label))

    return ranges

def parse_month_args(arg: str, ranges: list[tuple[date, date, str]]) -> list[tuple[date, date, str]]:
    if arg == "all":
        return ranges
    if arg == "last6":
        return ranges[:6]
    if arg == "last3":
        return ranges[:3]

    selected = [s.strip() for s in arg.split(",")]
    filtered = [r for r in ranges if r[2] in selected]
    if not filtered:
        print(f"❌ Bulan '{arg}' tidak ditemukan.")
        sys.exit(1)
    return filtered

def estimate_time(n_tickers: int, n_days: int) -> str:
    total_seconds = n_tickers * n_days * 8
    hours = total_seconds / 3600
    return f"~{hours:.1f} jam ({total_seconds/60:.0f} menit)"

# ── eksekusi utama ─────────────────────────────────────────────────────────

def run_backfill_month(
    month_label: str,
    start: date,
    end: date,
    universe_mode: str,
    rate_limit: float,
    refresh_prices: bool,
    progress: dict,
) -> bool:
    print(f"\n{'='*60}")
    print(f"📅 Memproses: {month_label}  ({start}  →  {end})")
    print(f"{'='*60}")

    uni_prog = get_universe_progress(progress, universe_mode)
    
    if month_label in uni_prog["completed"]:
        print(f"   ✅ Sudah selesai untuk universe '{universe_mode}'. Skip.")
        return True

    if start > end:
        print(f"   ⚠️  Range tidak valid. Skip.")
        return True

    # AMBIL DAFTAR SAHAM
    syms = universe_mod.get_universe(universe_mode)
    
    # LOGIKA SKIP SUBSET (Jika mode 'all' dan 'idx80' sudah pernah ditarik di bulan ini)
    if universe_mode == "all":
        idx80_prog = progress.get("universes", {}).get("idx80", {}).get("completed", [])
        if month_label in idx80_prog:
            print("   💡 Info: idx80 sudah ada untuk bulan ini. Menghapus idx80 dari daftar request...")
            syms_idx80 = universe_mod.get_universe("idx80")
            syms = [s for s in syms if s not in syms_idx80]

    n_days = (end - start).days + 1
    trading_days = sum(1 for i in range(n_days) if (start + timedelta(days=i)).weekday() < 5)
    est = estimate_time(len(syms), trading_days)
    print(f"   🎯 Target: {len(syms)} tickers | Hari kerja: ~{trading_days} | Estimasi: {est}")

    try:
        t0 = time.monotonic()
        set_rate_limit(rate_limit)

        # CATATAN: Jika pipeline Anda MENDUKUNG parameter `tickers=...`, 
        # gunakan argumen tersebut agar filtering berjalan. 
        # Jika hanya mendukung string universe_mode, ini tetap akan men-download ulang idx80.
        result = pipeline.backfill_broker_history(
            universe_mode=universe_mode, 
            # tickers=syms,  <-- (Buka komen ini jika pipeline Anda mendukung custom list)
            start_date=start,
            end_date=end,
            refresh_prices=refresh_prices,
            price_period="1y",
        )

        elapsed = time.monotonic() - t0
        print(f"   ✅ Selesai dalam {elapsed/60:.1f} menit")
        print(f"      📊 Broker rows: {result['n_broker']:,} | Activity rows: {result.get('n_activity', 0):,}")

        uni_prog["completed"].append(month_label)
        if month_label in uni_prog["failed"]:
            del uni_prog["failed"][month_label]
        save_progress(progress)
        return True

    except Exception as exc:
        print(f"   ❌ GAGAL: {exc}")
        uni_prog["failed"][month_label] = str(exc)
        save_progress(progress)
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill broker data per bulan")
    parser.add_argument("--universe", default="idx80", help="Universe yang akan di-backfill")
    parser.add_argument("--months", default="all", help='Bulan: "all", "last3", dsb.')
    parser.add_argument("--rate-limit", type=float, default=8.0)
    parser.add_argument("--no-refresh-prices", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset-progress", action="store_true")

    args = parser.parse_args()
    storage.init_db()
    progress = load_progress()

    if args.reset_progress:
        if _PROGRESS_FILE.exists():
            _PROGRESS_FILE.unlink()
            print("🗑️  Progress di-reset.")
        return

    if args.status:
        print(f"📋 Backfill Progress")
        print(f"   Dimulai: {progress.get('started_at') or 'Belum pernah'}")
        
        for uni, data in progress.get("universes", {}).items():
            print(f"\n   🔹 Universe: {uni.upper()}")
            print(f"      ✅ Selesai: {len(data['completed'])} bulan")
            for m in data["completed"]:
                print(f"         - {m}")
        return

    if not progress["started_at"]:
        progress["started_at"] = datetime.now().isoformat()
        save_progress(progress)

    ranges = get_month_ranges(months_back=12)
    selected = parse_month_args(args.months, ranges)
    uni_prog = get_universe_progress(progress, args.universe)

    print(f"\n📅 Total bulan dipilih: {len(selected)}")
    for start, end, label in selected:
        status = "✅" if label in uni_prog["completed"] else "⏳"
        print(f"   {status} {label}  ({start} ~ {end})")

    remaining = [r for r in selected if r[2] not in uni_prog["completed"]]
    if not remaining:
        print("\n🎉 Semua bulan sudah selesai!")
        return

    print(f"\n⏳ Bulan yang akan dikerjakan: {len(remaining)}")
    confirm = input("Lanjutkan? [Y/n]: ").strip().lower()
    if confirm and confirm not in ("y", "yes", "ya"):
        print("Dibatalkan.")
        return

    for start, end, label in remaining:
        ok = run_backfill_month(label, start, end, args.universe, args.rate_limit, not args.no_refresh_prices, progress)
        if label != remaining[-1][2] and ok:
            time.sleep(_PAUSE_BETWEEN_MONTHS)

if __name__ == "__main__":
    main()

