# 📈 IDX Bandarmology — Smart Money Tracker (PostgreSQL Edition)

> **Acknowledgment:** This repository is an enhanced, production-ready fork of the original [idx-bandarmology](https://github.com/IgnatiusHarry/idx-bandarmology) project by IgnatiusHarry.

An end-to-end data pipeline and interactive dashboard for tracking "Smart Money" (broker accumulation and foreign flow) in the Indonesian Stock Exchange (IDX/BEI). 

This project explores a fundamental trading hypothesis: **Do large-broker accumulation signals and foreign flow actually align with stronger IDX stock returns, or are they mostly trader folklore?**

---

## ✨ What's New in this Version? (Fork Upgrades)
This repository brings several architectural improvements over the original project to make it scalable and deployment-ready:

*   🐘 **PostgreSQL Migration (`storage.py`)**: Replaced the original SQLite database with a robust **PostgreSQL + SQLAlchemy** engine. It utilizes `psycopg2` `execute_values` for high-performance bulk upserts, making it scalable for the entire IDX universe (~900 tickers).
*   🔍 **DB Inspector Dashboard (`db_inspector.py`)**: A standalone Streamlit application built to monitor database health, track row counts per table, and detect missing historical date gaps.
*   ⚡ **Lazy Fetching (`app.py`)**: The main dashboard now features dynamic live-fetching. If you query a ticker that hasn't been updated in the database today, the dashboard will automatically hit the Broker API in the background and update the database on the fly.
*   📅 **Smart Monthly Backfiller (`backfill_monthly.py`)**: A specialized script for historical data extraction with JSON-based progress tracking. It safely handles API rate limits and allows you to pause/resume backfilling across massive universes without data loss.
*   🌐 **Public Deployment Ready (`cloudflared_config.yml`)**: Pre-configured for secure public internet exposure using Cloudflare Tunnels.

## 🏗️ Architecture & Workflow

**Data Engineering → Data Analysis → Data Science**

1.  **Ingestion**: Fetches daily OHLCV from `yfinance` and broker flow/distribution data from an authenticated private endpoint.
2.  **Storage**: Cleans and lands data into a relational **PostgreSQL** data warehouse.
3.  **Feature Engineering**: Calculates forward/backward returns, rolling volumes, and encodes categorical bandar signals.
4.  **Modeling**: Runs OLS regression (with HAC/Newey-West robust errors) and Machine Learning classifiers (Logistic Regression & Random Forest) to test the predictive power of the signals.
5.  **Visualization**: Serves insights through a highly interactive Streamlit dashboard.

## 🛠️ Tech Stack
*   **Data Processing**: Python, pandas, NumPy
*   **Storage**: PostgreSQL, SQLAlchemy, psycopg2-binary
*   **Machine Learning & Stats**: scikit-learn, statsmodels
*   **Visualization**: Streamlit, Plotly, matplotlib, seaborn
*   **Data Sources**: yfinance, Authenticated Broker API

## 📂 Repository Structure

```text
idx-bandarmology/
├── .env.example
├── requirements.txt
├── cloudflared_config.yml       # Cloudflare tunnel setup
├── backfill_monthly.py          # Automated historical data fetcher
├── db_inspector.py              # Streamlit DB monitoring app
├── init_universe.py             # BEI master ticker initializer
├── dashboard/
│   └── app.py                   # Main Smart Money Dashboard
├── src/idx_bandarmology/
│   ├── config.py              # Env & DB configurations
│   ├── broker_api.py          # Rate-limited API client
│   ├── prices.py              # yfinance integration
│   ├── storage.py             # PostgreSQL SQLAlchemy models
│   ├── pipeline.py            # ETL Orchestrator
│   ├── universe.py            # Ticker categorization (IDX30, LQ45, etc.)
│   ├── features.py            # Target & feature engineering
│   ├── analysis.py            # Statistical & correlation analysis
│   └── modeling.py            # ML & OLS hypothesis testing
└── data/                      # Local JSON progress and CSV fallbacks
```

## 🚀 Setup & Installation

**1. Clone the repository and install dependencies:**
```bash
git clone <your-repo-url>
cd idx-bandarmology
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Setup PostgreSQL Database:**
Create a new PostgreSQL database (e.g., `bandarmology`).

**3. Configure Environment Variables:**
```bash
cp .env.example .env
```
Edit the `.env` file with your database credentials and API token:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/bandarmology
BROKER_API_TOKEN=your_authenticated_bearer_token_here
UNIVERSE_MODE=idx80
```
*(Note: The `BROKER_API_TOKEN` requires an active session token from the broker data provider. Keep this token private.)*

## 💻 Usage Guide

### 1. Initialize the Universe
Fetch the latest master list of active tickers directly from BEI:
```bash
python init_universe.py
```

### 2. Backfill Historical Data
Populate your database with historical broker flow data. This script tracks progress in `data/backfill_progress.json` so you can safely pause and resume.
```bash
python backfill_monthly.py --universe idx80 --months last6
```

### 3. Run the Main Dashboard
Launch the interactive Streamlit dashboard to analyze stocks, view broker distributions (Sankey diagrams), and run the cross-watchlist screener:
```bash
streamlit run dashboard/app.py
```

### 4. Run the DB Inspector
Monitor your PostgreSQL database health, check for date gaps, and verify table sizes:
```bash
streamlit run db_inspector.py
```

## ⚠️ Disclaimer
This project is built for educational purposes and data science research. **It is not financial or investment advice.** 
The behavioral buckets ("Smart Money", "Retail", etc.) are heuristic classifications based on historical broker patterns, not official identities. Any corporate-affiliation notes discovered using this tool are observational hypotheses and do not imply insider trading or wrongdoing. 

---
*Original project by [IgnatiusHarry](https://github.com/IgnatiusHarry/idx-bandarmology) | Forked and upgraded by Cugarete*
