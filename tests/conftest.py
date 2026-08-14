import pytest

@pytest.fixture
def mock_storage(mocker):
    return mocker.patch("idx_bandarmology.storage")
