import pandas as pd
import numpy as np
from idx_bandarmology.features import build_price_features

def test_build_price_features_empty_dataframe():
    """Test that build_price_features handles an empty DataFrame correctly."""
    empty_df = pd.DataFrame()
    result_df = build_price_features(empty_df)
    assert result_df.empty, "Expected an empty DataFrame to be returned."

def test_build_price_features_empty_dataframe_with_columns():
    """Test that build_price_features handles an empty DataFrame with columns correctly."""
    empty_df = pd.DataFrame(columns=["ticker", "date", "close", "volume"])
    result_df = build_price_features(empty_df)
    assert result_df.empty, "Expected an empty DataFrame to be returned."
    assert list(result_df.columns) == ["ticker", "date", "close", "volume"], "Expected the same columns to be returned."

def test_build_price_features_normal():
    """Test that build_price_features computes features correctly for normal data."""
    df = pd.DataFrame({
        "ticker": ["A", "A", "A", "A", "A", "A"],
        "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"]),
        "close": [100.0, 105.0, 102.9, 110.0, 115.5, 120.0],
        "volume": [1000, 1500, 1200, 2000, 2500, 1800]
    })

    result_df = build_price_features(df)

    assert "return_1d" in result_df.columns
    assert "volume_avg_5d" in result_df.columns
    assert "volume_ratio" in result_df.columns

    # Check return_1d calculation
    assert pd.isna(result_df.loc[0, "return_1d"])
    assert np.isclose(result_df.loc[1, "return_1d"], 0.05) # 105 / 100 - 1

    # Check volume_avg_5d
    assert result_df.loc[0, "volume_avg_5d"] == 1000.0
    assert result_df.loc[4, "volume_avg_5d"] == np.mean([1000, 1500, 1200, 2000, 2500])

    # Check volume_ratio
    assert result_df.loc[0, "volume_ratio"] == 1000.0 / 1000.0
    assert result_df.loc[4, "volume_ratio"] == 2500.0 / np.mean([1000, 1500, 1200, 2000, 2500])
