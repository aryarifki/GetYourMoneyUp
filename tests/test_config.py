import os
from unittest.mock import patch

from idx_bandarmology.config import get_database_url


def test_get_database_url_from_database_url_env():
    """Test that DATABASE_URL from environment takes precedence."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test_user:test_pass@testhost:5432/testdb"}):
        url = get_database_url()
        assert url == "postgresql://test_user:test_pass@testhost:5432/testdb"


def test_get_database_url_fallback_defaults():
    """Test the fallback values when no env vars are set."""
    # Ensure DATABASE_URL and DB_* env vars are not set
    with patch.dict(os.environ, {}, clear=True):
        url = get_database_url()
        assert url == "postgresql://bandar:bandar123@localhost:5432/bandarmology"


def test_get_database_url_fallback_custom_env():
    """Test the fallback URL construction with custom DB_* env vars."""
    env_vars = {
        "DB_USER": "custom_user",
        "DB_PASSWORD": "custom_password",
        "DB_HOST": "custom_host",
        "DB_PORT": "5433",
        "DB_NAME": "custom_db",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        url = get_database_url()
        assert url == "postgresql://custom_user:custom_password@custom_host:5433/custom_db"


def test_get_database_url_empty_database_url():
    """Test that an empty or whitespace DATABASE_URL triggers fallback."""
    env_vars = {
        "DATABASE_URL": "   ",
        "DB_USER": "fallback_user",
        "DB_PASSWORD": "fallback_password",
        "DB_HOST": "fallback_host",
        "DB_PORT": "5434",
        "DB_NAME": "fallback_db",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        url = get_database_url()
        assert url == "postgresql://fallback_user:fallback_password@fallback_host:5434/fallback_db"
