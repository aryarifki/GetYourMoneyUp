import sys
from unittest.mock import patch
import pytest
import pandas as pd
import numpy as np

# We mock all external data fetching and API calls that happen at module level
# when importing dashboard/app.py.
with patch('idx_bandarmology.storage.read_prices') as mock_prices, \
     patch('idx_bandarmology.storage.read_broker_flow') as mock_flow, \
     patch('idx_bandarmology.storage.read_broker_activity') as mock_act, \
     patch('idx_bandarmology.storage.read_runs') as mock_runs, \
     patch('idx_bandarmology.universe.get_universe') as mock_uni, \
     patch('idx_bandarmology.universe.get_master_tickers') as mock_mast, \
     patch('idx_bandarmology.analysis.broker_alpha_scan') as mock_alpha, \
     patch('idx_bandarmology.analysis.event_study_table') as mock_event, \
     patch('idx_bandarmology.analysis.price_performance_table') as mock_perf, \
     patch('idx_bandarmology.analysis.causality_foreign_vs_price') as mock_cause, \
     patch('idx_bandarmology.analysis.top_net_broker_summary') as mock_top:

    # Minimal viable mock return values to let the Streamlit app script execute completely
    mock_prices.return_value = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'ticker': ['ANTM'], 'close': [1000], 'volume': [1000]})
    mock_flow.return_value = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'ticker': ['ANTM'], 'bandar_signal': ['AKUMULASI'], 'bandar_signal_score': [1], 'foreign_net_broker': [0], 'local_net_broker': [0], 'total_value': [0]})
    mock_act.return_value = pd.DataFrame({'date': pd.to_datetime(['2023-01-01']), 'ticker': ['ANTM'], 'broker_code': ['XX'], 'net_value': [0], 'participant_type': ['LOCAL'], 'buy_value': [0], 'sell_value': [0], 'frequency': [1], 'buy_lot': [0], 'sell_lot': [0], 'buy_avg_price': [0], 'sell_avg_price': [0]})
    mock_runs.return_value = pd.DataFrame({'run_at': ['2023-01-01']})
    mock_uni.return_value = ['ANTM']
    mock_mast.return_value = ['ANTM']
    mock_alpha.return_value = pd.DataFrame({'ticker': [], 'broker_code': [], 'significant': []})
    mock_event.return_value = pd.DataFrame()
    mock_perf.return_value = pd.DataFrame()
    mock_cause.return_value = {'is_significant': False, 'min_p_value': 0.5, 'best_lag': 1}
    mock_top.return_value = (pd.DataFrame(), pd.DataFrame())

    sys.path.insert(0, '.')
    # import app module to get fmt_signal function
    from dashboard.app import fmt_signal

def test_fmt_signal():
    # mapped keys
    assert fmt_signal("AKUMULASI_KUAT") == "Strong Accumulation"
    assert fmt_signal("AKUMULASI") == "Accumulation"
    assert fmt_signal("NETRAL") == "Neutral"
    assert fmt_signal("DISTRIBUSI") == "Distribution"
    assert fmt_signal("DISTRIBUSI_KUAT") == "Strong Distribution"

    # english versions
    assert fmt_signal("STRONG_ACCUMULATION") == "Strong Accumulation"
    assert fmt_signal("NET_BUY") == "Net Buy"

    # unmapped string formatting
    assert fmt_signal("UNKNOWN_STATUS") == "Unknown Status"
    assert fmt_signal("LOWER_case") == "Lower Case"

    # None and NaN
    assert fmt_signal(None) == "-"
    assert fmt_signal(np.nan) == "-"
    assert fmt_signal(pd.NA) == "-"
