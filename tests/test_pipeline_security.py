import pytest
from idx_bandarmology.pipeline import _already_fetched_today
from idx_bandarmology import storage

def test_already_fetched_today_invalid_table():
    with pytest.raises(ValueError, match="Invalid table name: invalid_table_name"):
        _already_fetched_today(["BBCA"], table="invalid_table_name")

from unittest.mock import patch

def test_already_fetched_today_valid_table():
    # We mock pd.read_sql and storage.engine.connect to bypass actual db execution
    # since ANY() is postgres specific and in-memory sqlite doesn't support it.
    with patch("idx_bandarmology.pipeline.pd.read_sql") as mock_read_sql, \
         patch("idx_bandarmology.pipeline.storage.engine.connect"):

        mock_read_sql.return_value = type('obj', (object,), {'empty': True})()

        # Should not raise ValueError
        try:
            _already_fetched_today(["BBCA"], table="broker_flow")
            _already_fetched_today(["BBCA"], table="prices")
            _already_fetched_today(["BBCA"], table="broker_activity")
        except ValueError:
            pytest.fail("ValueError was raised unexpectedly for valid table names.")
