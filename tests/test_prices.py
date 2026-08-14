import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from idx_bandarmology.prices import _yf_ticker, fetch_history, fetch_history_many

def test_yf_ticker():
    assert _yf_ticker("bbca") == "BBCA.JK"
    assert _yf_ticker("BBCA") == "BBCA.JK"
    assert _yf_ticker("BBCA.JK") == "BBCA.JK"
    assert _yf_ticker(" bbca ") == "BBCA.JK"

@patch("idx_bandarmology.prices.yf.download")
def test_fetch_history_success(mock_download):
    # Mock return data similar to yfinance structure
    mock_df = pd.DataFrame({
        "Date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
        "Open": [100.0, 101.0],
        "High": [105.0, 106.0],
        "Low": [95.0, 96.0],
        "Close": [102.0, 103.0],
        "Volume": [1000, 1500]
    }).set_index("Date")
    mock_download.return_value = mock_df

    df = fetch_history("BBCA")

    assert mock_download.called
    assert list(df.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]
    assert df["ticker"].tolist() == ["BBCA", "BBCA"]
    assert df["date"].tolist() == [pd.Timestamp("2023-01-01").date(), pd.Timestamp("2023-01-02").date()]
    assert df["open"].tolist() == [100.0, 101.0]

@patch("idx_bandarmology.prices.yf.download")
def test_fetch_history_multiindex(mock_download):
    # yfinance sometimes returns a MultiIndex column DataFrame (e.g. Price, Ticker)
    columns = pd.MultiIndex.from_tuples([
        ("Open", "BBCA.JK"), ("High", "BBCA.JK"), ("Low", "BBCA.JK"),
        ("Close", "BBCA.JK"), ("Volume", "BBCA.JK")
    ])
    mock_df = pd.DataFrame({
        ("Open", "BBCA.JK"): [100.0],
        ("High", "BBCA.JK"): [105.0],
        ("Low", "BBCA.JK"): [95.0],
        ("Close", "BBCA.JK"): [102.0],
        ("Volume", "BBCA.JK"): [1000]
    }, index=pd.Index(pd.to_datetime(["2023-01-01"]), name="Date"))
    mock_df.columns = columns
    mock_download.return_value = mock_df

    df = fetch_history("BBCA")

    assert list(df.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]
    assert df["open"].iloc[0] == 100.0

@patch("idx_bandarmology.prices.yf.download")
def test_fetch_history_empty_or_none(mock_download):
    # Test None
    mock_download.return_value = None
    df_none = fetch_history("BBCA")
    assert df_none.empty
    assert list(df_none.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]

    # Test Empty
    mock_download.return_value = pd.DataFrame()
    df_empty = fetch_history("BBCA")
    assert df_empty.empty
    assert list(df_empty.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]

@patch("idx_bandarmology.prices.yf.download")
def test_fetch_history_exception(mock_download):
    # Raise exception during download
    mock_download.side_effect = Exception("API Error")

    df = fetch_history("BBCA")
    assert df.empty
    assert list(df.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]

@patch("idx_bandarmology.prices.fetch_history")
def test_fetch_history_many(mock_fetch_history):
    # Mock fetch_history to return sample dataframes
    df_bbca = pd.DataFrame({
        "date": [pd.Timestamp("2023-01-01").date()],
        "ticker": ["BBCA"],
        "open": [100.0], "high": [105.0], "low": [95.0], "close": [102.0], "volume": [1000]
    })
    df_bmri = pd.DataFrame({
        "date": [pd.Timestamp("2023-01-01").date()],
        "ticker": ["BMRI"],
        "open": [200.0], "high": [205.0], "low": [195.0], "close": [202.0], "volume": [2000]
    })
    df_empty = pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])

    # Return df_bbca, then empty, then df_bmri
    mock_fetch_history.side_effect = [df_bbca, df_empty, df_bmri]

    df_combined = fetch_history_many(["BBCA", "GOTO", "BMRI"])

    assert len(df_combined) == 2
    assert df_combined["ticker"].tolist() == ["BBCA", "BMRI"]

    # Test all empty returns empty df
    mock_fetch_history.side_effect = [df_empty, df_empty]
    df_all_empty = fetch_history_many(["GOTO", "BUMI"])
    assert df_all_empty.empty
    assert list(df_all_empty.columns) == ["date", "ticker", "open", "high", "low", "close", "volume"]
