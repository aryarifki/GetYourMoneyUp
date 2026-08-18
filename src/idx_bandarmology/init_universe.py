#!/usr/bin/env python3
"""Initialize the master ticker universe from BEI."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from idx_bandarmology import universe, storage


def main() -> None:
    print("=" * 60)
    print("IDX Bandarmology - Universe Initialization")
    print("=" * 60)

    storage.init_db()
    print("[init] Database tables verified.")

    print("[init] Fetching master ticker list from BEI...")
    count = universe.refresh_master_tickers(force=True)

    if count > 0:
        print(f"[init] Success: {count} tickers cached in PostgreSQL.")
    else:
        print("[init] Warning: BEI fetch returned 0 tickers. Using fallback hard-coded lists.")

    info = universe.get_universe_info()
    print("\n[init] Available universes:")
    for name, size in info.items():
        print(f"       {name}: ~{size} tickers")

    print("\n[init] Quick test - resolving idx30 universe...")
    idx30 = universe.get_universe("idx30")
    print(f"       -> {len(idx30)} tickers: {', '.join(idx30[:5])}...")

    print("\n[init] Done. You can now run the pipeline with:")
    print("       python -c \"from idx_bandarmology import pipeline; pipeline.run(universe_mode='idx80')\"")
    print("=" * 60)


if __name__ == "__main__":
    main()
