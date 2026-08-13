# Deployment Guide — IDX Bandarmology Universe Expansion

## Overview

This update expands the dashboard coverage from 10 tickers to the entire IDX universe (~900 tickers) with:
- **Rate-limited** Stockbit API fetching (token bucket, ~8 req/min)
- **Batch processing** with progress logging and runtime tracking
- **Resume mode** — skip tickers already fetched today
- **Universe modes**: `watchlist`, `idx30`, `lq45`, `idx80`, `all`, `liquid`
- **Master ticker cache** in PostgreSQL (fetched from BEI)

---

## Files Changed / Added

| File | Action | Description |
|------|--------|-------------|
| `src/idx_bandarmology/universe.py` | **NEW** | Universe manager: BEI fetch, caching, mode resolution |
| `src/idx_bandarmology/broker_api.py` | **MODIFY** | Added token-bucket rate limiter, progress logging |
| `src/idx_bandarmology/pipeline.py` | **MODIFY** | Batch mode, runtime tracking, resume, universe_mode param |
| `src/idx_bandarmology/config.py` | **MODIFY** | Added `UNIVERSE_MODE`, `BROKER_RATE_LIMIT` env vars |
| `src/idx_bandarmology/storage.py` | **MODIFY** | Added `tickers` master table to schema |
| `src/idx_bandarmology/__init__.py` | **MODIFY** | Export `universe` module |
| `src/idx_bandarmology/init_universe.py` | **NEW** | One-time CLI script to seed master tickers |
| `.env.example` | **MODIFY** | New env vars documented |

---

## Step-by-Step Deployment

### 1. Backup Current Code

```bash
cd /opt/GetYourMoneyUp
cp -r src/idx_bandarmology src/idx_bandarmology.backup.$(date +%Y%m%d)
```

### 2. Copy New Files

```bash
# Copy all generated files to the project
cp /mnt/agents/output/universe.py src/idx_bandarmology/
cp /mnt/agents/output/broker_api.py src/idx_bandarmology/
cp /mnt/agents/output/pipeline.py src/idx_bandarmology/
cp /mnt/agents/output/config.py src/idx_bandarmology/
cp /mnt/agents/output/storage.py src/idx_bandarmology/
cp /mnt/agents/output/__init__.py src/idx_bandarmology/
cp /mnt/agents/output/init_universe.py src/idx_bandarmology/
cp /mnt/agents/output/.env.example .env.example
```

### 3. Update `.env`

Edit `.env` and add the new variables:

```bash
# Add to existing .env
UNIVERSE_MODE=idx80
BROKER_RATE_LIMIT=8.0
```

Or copy from `.env.example` and fill in your values.

### 4. Activate Virtual Environment

```bash
cd /opt/GetYourMoneyUp
source .venv/bin/activate
```

### 5. Initialize Master Tickers (One-Time)

```bash
export PYTHONPATH=/opt/GetYourMoneyUp/src
python -m idx_bandarmology.init_universe
```

Expected output:
```
============================================================
IDX Bandarmology — Universe Initialization
============================================================
[init] Database tables verified.
[init] Fetching master ticker list from BEI...
[init] Success: 920 tickers cached in PostgreSQL.

[init] Available universes:
       watchlist: 10 tickers
       idx30: 39 tickers
       lq45: 45 tickers
       idx80: 80 tickers
       all_cached: 920 tickers
       all_estimated: 900 tickers
...
```

### 6. Test Pipeline with Small Universe

```bash
# Test with watchlist first (fast, ~10 tickers)
python -c "from idx_bandarmology import pipeline; print(pipeline.run(universe_mode='watchlist'))"
```

Then test with a larger universe:
```bash
# Test with IDX30 (~39 tickers, ~5 minutes)
python -c "from idx_bandarmology import pipeline; print(pipeline.run(universe_mode='idx30'))"
```

### 7. Test with Full Universe (Optional)

```bash
# IDX80 (~80 tickers, ~11 minutes)
python -c "from idx_bandarmology import pipeline; print(pipeline.run(universe_mode='idx80'))"

# ALL (~900 tickers, ~2 hours)
python -c "from idx_bandarmology import pipeline; print(pipeline.run(universe_mode='all'))"
```

> **Warning**: `all` mode will take ~2 hours for broker data. Run during off-market hours or use `idx80` for daily use.

### 8. Verify Database

```bash
sudo -u postgres psql -d bandarmology -c "SELECT COUNT(*) FROM tickers WHERE is_active = TRUE;"
sudo -u postgres psql -d bandarmology -c "SELECT COUNT(DISTINCT ticker) FROM broker_flow WHERE date = CURRENT_DATE;"
```

---

## Runtime Estimates

| Universe | Tickers | Prices (yfinance) | Broker Data (Stockbit) | Total |
|----------|---------|-------------------|------------------------|-------|
| watchlist | 10 | ~10s | ~80s | ~2 min |
| idx30 | 39 | ~15s | ~5 min | ~6 min |
| lq45 | 45 | ~15s | ~6 min | ~7 min |
| idx80 | 80 | ~20s | ~11 min | ~12 min |
| all | ~900 | ~60s | ~2 hours | ~2 hours |

*Broker estimates assume 8 req/min rate limit. yfinance is parallel and fast.*

---

## Resume Mode

If the pipeline is interrupted, re-running it with `resume=True` (default) will skip tickers already stored for today:

```python
from idx_bandarmology import pipeline
pipeline.run(universe_mode='idx80')  # skips already-fetched tickers
```

To force re-fetch everything:
```python
pipeline.run(universe_mode='idx80', resume=False)
```

---

## Daily Cron Job Setup

Add to crontab for daily 6 PM run (after market close):

```bash
sudo crontab -e
```

```cron
# IDX Bandarmology — daily pipeline at 18:00 WIB (11:00 UTC)
0 11 * * * cd /opt/GetYourMoneyUp && PYTHONPATH=/opt/GetYourMoneyUp/src /opt/GetYourMoneyUp/.venv/bin/python -c "from idx_bandarmology import pipeline; pipeline.run(universe_mode='idx80')" >> /opt/GetYourMoneyUp/logs/pipeline_$(date +\%Y\%m\%d).log 2>&1
```

Create log directory:
```bash
mkdir -p /opt/GetYourMoneyUp/logs
```

---

## Troubleshooting

### BEI fetch returns 0 tickers
The BEI endpoint may be down or changed. The hard-coded fallback lists (IDX30, LQ45, IDX80) will still work.

### Rate limit errors (429 Too Many Requests)
Lower the rate in `.env`:
```
BROKER_RATE_LIMIT=6.0
```

### Pipeline too slow for "all" mode
Use `idx80` for daily runs and `all` only for weekend backfills.

### Memory issues with large universes
The pipeline processes tickers sequentially for broker data, so memory usage is flat regardless of universe size.

---

## API Reference (Quick)

```python
from idx_bandarmology import universe, pipeline, broker_api

# List available universes
universe.get_universe_info()
# {'watchlist': 10, 'idx30': 39, 'lq45': 45, 'idx80': 80, 'all_cached': 920, 'all_estimated': 900}

# Get ticker list
universe.get_universe('idx80')

# Refresh master tickers from BEI
universe.refresh_master_tickers(force=True)

# Run pipeline with timing
result = pipeline.run(universe_mode='idx80')
print(f"Completed in {result['elapsed_seconds']}s")

# Adjust rate limit dynamically
broker_api.set_rate_limit(6.0)  # 6 req/min
```
.
