import time
import os
os.environ["BROKER_API_TOKEN"] = "dummy"

# Mock requests.get
import requests
class MockResponse:
    def raise_for_status(self): pass
    def json(self): return {"data": {}}
requests.get = lambda *args, **kwargs: MockResponse()

from idx_bandarmology import pipeline
from idx_bandarmology import broker_api

broker_api.set_rate_limit(60000) # Fast rate limit for test

# Make mock for prices
from idx_bandarmology import prices
import pandas as pd
prices.fetch_history_many = lambda *args, **kwargs: pd.DataFrame()

# We might also need mock for storage if it hits db
from idx_bandarmology import storage
storage.upsert_prices = lambda *args, **kwargs: 0
storage.upsert_broker_flow = lambda *args, **kwargs: 0
storage.upsert_broker_activity = lambda *args, **kwargs: 0
storage.init_db = lambda: None
storage.log_run = lambda *args, **kwargs: None

import unittest.mock
with unittest.mock.patch('idx_bandarmology.pipeline._already_fetched_today', return_value=[]):
    with unittest.mock.patch('idx_bandarmology.broker_api.fetch_historical_broker_data', return_value=(pd.DataFrame(), pd.DataFrame())):
        t0 = time.time()
        pipeline.run(tickers=["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"], fetch_broker_data=True, broker_batch_size=3)
        t1 = time.time()
        print(f"Elapsed: {t1 - t0}")
