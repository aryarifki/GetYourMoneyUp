import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from idx_bandarmology import pipeline

@pytest.fixture
def mock_storage(mocker):
    storage = mocker.patch("idx_bandarmology.pipeline.storage")
    storage.upsert_prices.return_value = 10
    storage.upsert_broker_flow.return_value = 5
    storage.upsert_broker_activity.return_value = 20
    return storage

@pytest.fixture
def mock_prices(mocker):
    prices = mocker.patch("idx_bandarmology.pipeline.prices")
    prices.fetch_history_many.return_value = pd.DataFrame()
    return prices

@pytest.fixture
def mock_broker_api(mocker):
    api = mocker.patch("idx_bandarmology.pipeline.broker_api")
    api.is_available.return_value = True
    api.fetch_watchlist.return_value = {
        "BBCA": {
            "available": True,
            "broker": {"date": "2024-01-01", "signal": "Accumulation", "signalScore": 90},
            "foreignDomestic": {"date": "2024-01-01", "netForeign": 100}
        }
    }
    api.fetch_historical_broker_data.return_value = (pd.DataFrame(), pd.DataFrame())
    return api

@pytest.fixture
def mock_universe(mocker):
    univ = mocker.patch("idx_bandarmology.pipeline.universe")
    univ.get_universe.return_value = ["BBCA", "BMRI"]
    return univ

def test_run_custom_tickers(mock_storage, mock_prices, mock_broker_api, mocker):
    mocker.patch("idx_bandarmology.pipeline._already_fetched_today", return_value=[])

    result = pipeline.run(tickers=["bbca", "bbri"], price_period="1mo")

    assert result["tickers"] == ["BBCA", "BBRI"]
    assert result["mode"] == "custom"
    assert result["n_prices"] == 10
    assert result["n_broker"] == 5
    assert result["n_activity"] == 20
    assert result["broker_skipped"] == 0
    assert result["broker_fetched"] == 2

    mock_prices.fetch_history_many.assert_called_once_with(["BBCA", "BBRI"], period="1mo")
    mock_broker_api.fetch_watchlist.assert_called_once()
    mock_storage.upsert_prices.assert_called_once()
    mock_storage.upsert_broker_flow.assert_called_once()
    mock_storage.upsert_broker_activity.assert_called_once()
    mock_storage.log_run.assert_called_once()

def test_run_universe_mode(mock_storage, mock_prices, mock_broker_api, mock_universe, mocker):
    mocker.patch("idx_bandarmology.pipeline._already_fetched_today", return_value=[])

    result = pipeline.run(universe_mode="lq45", price_period="1mo")

    assert result["tickers"] == ["BBCA", "BMRI"]
    assert result["mode"] == "lq45"
    mock_universe.get_universe.assert_called_once_with("lq45")

def test_run_resume_skips_tickers(mock_storage, mock_prices, mock_broker_api, mocker):
    mocker.patch("idx_bandarmology.pipeline._already_fetched_today", return_value=["BBCA"])

    result = pipeline.run(tickers=["BBCA", "BBRI"], resume=True)

    assert result["broker_skipped"] == 1
    assert result["broker_fetched"] == 1
    # Should only fetch for BBRI
    called_args = mock_broker_api.fetch_watchlist.call_args[0][0]
    assert called_args == ["BBRI"]

def test_run_skip_broker_data(mock_storage, mock_prices, mock_broker_api, mocker):
    result = pipeline.run(tickers=["BBCA"], fetch_broker_data=False)

    assert result["n_broker"] == 0
    assert result["n_activity"] == 0
    mock_broker_api.fetch_watchlist.assert_not_called()

def test_run_broker_api_unavailable(mock_storage, mock_prices, mock_broker_api, mocker):
    mock_broker_api.is_available.return_value = False

    result = pipeline.run(tickers=["BBCA"])

    assert result["n_broker"] == 0
    assert result["n_activity"] == 0
    mock_broker_api.fetch_watchlist.assert_not_called()

def test_backfill_broker_history(mock_storage, mock_prices, mock_broker_api):
    result = pipeline.backfill_broker_history(
        tickers=["BBCA"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        refresh_prices=True
    )

    assert result["tickers"] == ["BBCA"]
    assert result["start_date"] == "2024-01-01"
    assert result["end_date"] == "2024-01-31"
    assert result["n_prices"] == 10
    assert result["n_broker"] == 5
    assert result["n_activity"] == 20

    mock_prices.fetch_history_many.assert_called_once()
    mock_broker_api.fetch_historical_broker_data.assert_called_once_with(["BBCA"], "2024-01-01", "2024-01-31")

def test_backfill_requires_dates(mock_storage, mock_prices, mock_broker_api):
    with pytest.raises(ValueError, match="start_date and end_date are required"):
        pipeline.backfill_broker_history(tickers=["BBCA"])

def test_backfill_requires_broker_api(mock_storage, mock_prices, mock_broker_api):
    mock_broker_api.is_available.return_value = False
    with pytest.raises(RuntimeError, match="BROKER_API_TOKEN/STOCKBIT_TOKEN is not configured"):
        pipeline.backfill_broker_history(
            tickers=["BBCA"],
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
