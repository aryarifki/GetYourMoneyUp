#!/usr/bin/env python3
"""Initialize the master ticker universe from BEI.

Run this once after deploying the new code:
    cd /opt/GetYourMoneyUp
    source .venv/bin/activate
    python -m idx_bandarmology.init_universe

Or from anywhere with PYTHONPATH set:
    PYTHONPATH=/opt/GetYourMoneyUp/src python -m idx_bandarmology.init_universe
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path if running directly
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from idx_bandarmology import universe, storage


def main() -> None:
    print("=" * 60)
    print("IDX Bandarmology — Universe Initialization")
    print("=" * 60)

    # Ensure DB tables exist
    storage.init_db()
    print("[init] Database tables verified.")

    # Refresh master tickers from BEI
    print("[init] Fetching master ticker list from BEI...")
    count = universe.refresh_master_tickers(force=True)

    if count > 0:
        print(f"[init] Success: {count} tickers cached in PostgreSQL.")
    else:
        print("[init] Warning: BEI fetch returned 0 tickers. Using fallback hard-coded lists.")

    # Show universe info
    info = universe.get_universe_info()
    print("
[init] Available universes:")
    for name, size in info.items():
        print(f"       {name}: ~{size} tickers")

    # Quick test
    print("
[init] Quick test — resolving 'idx30' universe...")
    idx30 = universe.get_universe("idx30")
    print(f"       -> {len(idx30)} tickers: {', '.join(idx30[:5])}...")

    print("
[init] Done. You can now run the pipeline with:")
    print("       python -c "from idx_bandarmology import pipeline; pipeline.run(universe_mode='idx80')"")
    print("=" * 60)


if __name__ == "__main__":
    main()
