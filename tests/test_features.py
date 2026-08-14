import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from idx_bandarmology.features import build_price_features


def test_build_price_features_empty():
    """Test with an empty DataFrame."""
    empty_df = pd.DataFrame(columns=["ticker", "date", "close", "volume"])
    result = build_price_features(empty_df)
    assert_frame_equal(result, empty_df)


def test_build_price_features_normal():
    """Test return and rolling volume calculation with normal data."""
    data = pd.DataFrame({
        "ticker": ["A", "A", "A", "B", "B"],
        "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-01", "2023-01-02"]),
        "close": [100.0, 105.0, 102.9, 50.0, 55.0],
        "volume": [1000, 2000, 3000, 500, 100]
    })

    result = build_price_features(data)

    # For ticker A:
    # returns: NaN, 105/100-1 = 0.05, 102.9/105-1 = -0.02
    # vol avg: 1000, 1500, 2000
    # vol ratio: 1.0, 2000/1500 = 1.333, 3000/2000 = 1.5

    # For ticker B:
    # returns: NaN, 55/50-1 = 0.1
    # vol avg: 500, 300
    # vol ratio: 1.0, 100/300 = 0.333

    assert result.loc[result["ticker"] == "A", "return_1d"].isna().iloc[0]
    np.testing.assert_allclose(result.loc[result["ticker"] == "A", "return_1d"].iloc[1:], [0.05, -0.02], rtol=1e-5)
    np.testing.assert_allclose(result.loc[result["ticker"] == "A", "volume_avg_5d"], [1000, 1500, 2000])
    np.testing.assert_allclose(result.loc[result["ticker"] == "A", "volume_ratio"], [1.0, 2000/1500, 3000/2000])

    assert result.loc[result["ticker"] == "B", "return_1d"].isna().iloc[0]
    np.testing.assert_allclose(result.loc[result["ticker"] == "B", "return_1d"].iloc[1:], [0.1], rtol=1e-5)
    np.testing.assert_allclose(result.loc[result["ticker"] == "B", "volume_avg_5d"], [500, 300])
    np.testing.assert_allclose(result.loc[result["ticker"] == "B", "volume_ratio"], [1.0, 100/300])


def test_build_price_features_out_of_order():
    """Test that sorting is enforced before calculations."""
    data = pd.DataFrame({
        "ticker": ["A", "A", "B", "A"],
        "date": pd.to_datetime(["2023-01-02", "2023-01-01", "2023-01-01", "2023-01-03"]),
        "close": [105.0, 100.0, 50.0, 102.9],
        "volume": [2000, 1000, 500, 3000]
    })

    result = build_price_features(data)

    # DataFrame should be sorted by ticker then date
    # Index should be preserved from the original DataFrame but reordered
    a_returns = result.loc[result["ticker"] == "A"].sort_values("date")["return_1d"].values

    assert np.isnan(a_returns[0])
    np.testing.assert_allclose(a_returns[1:], [0.05, -0.02], rtol=1e-5)


def test_build_price_features_zero_volume_division():
    """Test that zero volume avg results in NaN ratio instead of inf."""
    data = pd.DataFrame({
        "ticker": ["A", "A"],
        "date": pd.to_datetime(["2023-01-01", "2023-01-02"]),
        "close": [100.0, 105.0],
        "volume": [0, 0]
    })

    result = build_price_features(data)

    # Volume avg should be 0
    np.testing.assert_allclose(result["volume_avg_5d"], [0, 0])

    # Volume ratio should be NaN because volume_avg_5d is 0
    assert result["volume_ratio"].isna().all()
