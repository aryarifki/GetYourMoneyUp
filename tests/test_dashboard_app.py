import sys
import importlib.util
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np

# Mock heavy/problematic imports for testing
mock_st = MagicMock()
mock_st.stop.side_effect = SystemExit("Stop Streamlit")
sys.modules['streamlit'] = mock_st
sys.modules['streamlit_searchbox'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['plotly.graph_objects'] = MagicMock()

# Mock internal dependencies to avoid db queries during top-level app execution
mock_universe = MagicMock()
mock_universe.get_master_tickers.side_effect = Exception("No tickers")
sys.modules['idx_bandarmology.universe'] = mock_universe
sys.modules['idx_bandarmology'] = MagicMock()
sys.modules['idx_bandarmology.analysis'] = MagicMock()
sys.modules['idx_bandarmology.broker_api'] = MagicMock()
sys.modules['idx_bandarmology.config'] = MagicMock()
sys.modules['idx_bandarmology.pipeline'] = MagicMock()
sys.modules['idx_bandarmology.storage'] = MagicMock()

# Load the module manually
spec = importlib.util.spec_from_file_location("dashboard.app", "dashboard/app.py")
app = importlib.util.module_from_spec(spec)
sys.modules["dashboard.app"] = app
try:
    spec.loader.exec_module(app)
except SystemExit:
    pass


def test_fmt_pct_happy_path():
    """Test standard float and string float values."""
    assert app.fmt_pct(0.1234) == "+12.34%"
    assert app.fmt_pct(-0.1234) == "-12.34%"
    assert app.fmt_pct(0) == "+0.00%"
    assert app.fmt_pct(1) == "+100.00%"
    assert app.fmt_pct("0.05") == "+5.00%"
    assert app.fmt_pct("-0.05") == "-5.00%"

def test_fmt_pct_edge_cases():
    """Test None, pd.NA, and np.nan values."""
    assert app.fmt_pct(None) == "-"
    assert app.fmt_pct(pd.NA) == "-"
    assert app.fmt_pct(np.nan) == "-"

def test_fmt_pct_error_conditions():
    """Test values that should raise an error when cast to float."""
    with pytest.raises(ValueError):
        app.fmt_pct("invalid")
    with pytest.raises(TypeError):
        app.fmt_pct({"key": "value"})
