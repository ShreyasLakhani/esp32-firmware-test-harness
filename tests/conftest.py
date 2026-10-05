import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "test_id(id): test case ID from docs/test-plan.md")


@pytest.fixture(autouse=True)
def _record_test_id(request, record_property):
    # puts the test plan ID into the JUnit XML as a property
    marker = request.node.get_closest_marker("test_id")
    if marker:
        record_property("test_id", marker.args[0])
