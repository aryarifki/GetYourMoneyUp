import os
from unittest import mock
import pytest

from idx_bandarmology.config import get_universe_mode

def test_get_universe_mode_valid():
    with mock.patch.dict(os.environ, {"UNIVERSE_MODE": "lq45"}):
        assert get_universe_mode() == "lq45"

    with mock.patch.dict(os.environ, {"UNIVERSE_MODE": "kompas100"}):
        assert get_universe_mode() == "kompas100"

    with mock.patch.dict(os.environ, {"UNIVERSE_MODE": "all"}):
        assert get_universe_mode() == "all"

def test_get_universe_mode_strip_lower():
    with mock.patch.dict(os.environ, {"UNIVERSE_MODE": "  lQ45  "}):
        assert get_universe_mode() == "lq45"

def test_get_universe_mode_invalid_defaults_to_watchlist():
    with mock.patch.dict(os.environ, {"UNIVERSE_MODE": "invalid_mode"}):
        assert get_universe_mode() == "watchlist"

def test_get_universe_mode_default():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert get_universe_mode() == "watchlist"
