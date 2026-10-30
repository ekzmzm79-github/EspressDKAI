import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SAMPLE_DATA = Path(__file__).resolve().parent / "fixtures" / "sample" / "data"


@pytest.fixture
def sample_data() -> Path:
    return SAMPLE_DATA
