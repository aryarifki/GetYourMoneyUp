import numpy as np
import pandas as pd
from idx_bandarmology.features import add_forward_returns


def test_add_forward_returns_basic():
    """Test standard calculation of forward returns."""
    data = {
        "ticker": ["BBCA", "BBCA", "BBCA", "BBCA", "BBRI", "BBRI", "BBRI", "BBRI"],
        "date": [
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
            pd.Timestamp("2023-01-03"),
            pd.Timestamp("2023-01-04"),
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
            pd.Timestamp("2023-01-03"),
            pd.Timestamp("2023-01-04"),
        ],
        "close": [100.0, 110.0, 121.0, 100.0, 50.0, 45.0, 54.0, 60.0],
    }
    df = pd.DataFrame(data)

    result = add_forward_returns(df, horizons=(1, 2))

    # BBCA checks
    bbca = result[result["ticker"] == "BBCA"].reset_index(drop=True)

    # 1-day forward returns for BBCA:
    # row 0 (100 -> 110) = 0.1
    # row 1 (110 -> 121) = 0.1
    # row 2 (121 -> 100) = ~ -0.1735
    # row 3 (100 -> ?) = NaN
    np.testing.assert_allclose(bbca["fwd_return_1d"].iloc[0], 0.1)
    np.testing.assert_allclose(bbca["fwd_return_1d"].iloc[1], 0.1)
    assert pd.isna(bbca["fwd_return_1d"].iloc[3])

    # 2-day forward returns for BBCA:
    # row 0 (100 -> 121) = 0.21
    # row 1 (110 -> 100) = ~ -0.0909
    # row 2 (121 -> ?) = NaN
    np.testing.assert_allclose(bbca["fwd_return_2d"].iloc[0], 0.21)
    assert pd.isna(bbca["fwd_return_2d"].iloc[2])

    # BBRI checks to ensure no data leakage from BBCA
    bbri = result[result["ticker"] == "BBRI"].reset_index(drop=True)

    # 1-day forward returns for BBRI:
    # row 0 (50 -> 45) = -0.1
    # row 1 (45 -> 54) = 0.2
    # row 2 (54 -> 60) = ~ 0.1111
    # row 3 (60 -> ?) = NaN
    np.testing.assert_allclose(bbri["fwd_return_1d"].iloc[0], -0.1)
    np.testing.assert_allclose(bbri["fwd_return_1d"].iloc[1], 0.2)
    assert pd.isna(bbri["fwd_return_1d"].iloc[3])

    # 2-day forward returns for BBRI:
    # row 0 (50 -> 54) = 0.08
    # row 1 (45 -> 60) = 0.3333
    np.testing.assert_allclose(bbri["fwd_return_2d"].iloc[0], 0.08)
    np.testing.assert_allclose(bbri["fwd_return_2d"].iloc[1], 1/3)


def test_add_forward_returns_empty():
    """Test behavior on empty DataFrame."""
    df = pd.DataFrame(columns=["ticker", "date", "close"])
    result = add_forward_returns(df, horizons=(1, 5))

    assert "fwd_return_1d" in result.columns
    assert "fwd_return_5d" in result.columns
    assert len(result) == 0


def test_add_forward_returns_sorting():
    """Test if the dataframe is properly sorted before processing."""
    data = {
        "ticker": ["A", "A", "A"],
        "date": [
            pd.Timestamp("2023-01-03"),
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        ],
        "close": [110.0, 100.0, 105.0],
    }
    df = pd.DataFrame(data)

    result = add_forward_returns(df, horizons=(1,))

    # The output should be sorted by ticker and date
    assert result["date"].iloc[0] == pd.Timestamp("2023-01-01")
    assert result["date"].iloc[1] == pd.Timestamp("2023-01-02")
    assert result["date"].iloc[2] == pd.Timestamp("2023-01-03")

    # Therefore, 2023-01-01 close=100 -> 2023-01-02 close=105 -> return=0.05
    np.testing.assert_allclose(result["fwd_return_1d"].iloc[0], 0.05)
