import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return ROOT / "fixtures"


@pytest.fixture(scope="session")
def policies_dir() -> Path:
    return ROOT / "policies"


@dataclass
class FixtureCopy:
    """A writable copy of the fixture directory, for tests that need bad data."""

    path: Path

    def edit(self, name: str, change: Callable[[Any], None]) -> None:
        file = self.path / name
        data = json.loads(file.read_text(encoding="utf-8"))
        change(data)
        file.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def fixture_copy(tmp_path: Path, fixtures_dir: Path) -> FixtureCopy:
    target = tmp_path / "fixtures"
    shutil.copytree(fixtures_dir, target)
    return FixtureCopy(target)
