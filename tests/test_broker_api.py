import pytest
from src.idx_bandarmology import broker_api

def test_set_rate_limit():
    """Test that set_rate_limit properly updates the _RL_RATE module variable."""
    initial_rate = broker_api._RL_RATE
    try:
        # Set to 12 requests per minute (which is 12/60 = 0.2 tokens per second)
        broker_api.set_rate_limit(12.0)
        assert broker_api._RL_RATE == 12.0 / 60.0

        # Test another value
        broker_api.set_rate_limit(30.0)
        assert broker_api._RL_RATE == 30.0 / 60.0
    finally:
        # Restore the initial rate
        broker_api._RL_RATE = initial_rate
