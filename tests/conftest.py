from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return Path(__file__).resolve().parent / "test_data"
