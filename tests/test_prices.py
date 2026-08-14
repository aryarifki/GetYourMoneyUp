import pandas as pd
from unittest.mock import patch
from idx_bandarmology.prices import fetch_history

def test_fetch_history_exception():
    """Test that fetch_history returns an empty dataframe with correct columns if yf.download raises an Exception."""
    with patch("idx_bandarmology.prices.yf.download") as mock_download:
        mock_download.side_effect = Exception("Mocked yfinance error")

        result = fetch_history("BBCA")

        # Verify it returns an empty DataFrame
        assert isinstance(result, pd.DataFrame)
        assert result.empty

        # Verify the columns are correct
        expected_columns = ["date", "ticker", "open", "high", "low", "close", "volume"]
        assert list(result.columns) == expected_columns
