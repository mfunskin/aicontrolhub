from __future__ import annotations

import pytest

from aicontrolhub.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "governance.sqlite3")
