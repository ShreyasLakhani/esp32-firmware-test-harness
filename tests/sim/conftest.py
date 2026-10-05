import os

import pytest

from harness import BUILD, ROOT, Node

ARTIFACTS = ROOT / "artifacts"


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/sim" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.sim)


def _token():
    # CI sets REQUIRE_SIM=1 so a missing token or build fails instead of skipping
    stop = pytest.fail if os.environ.get("REQUIRE_SIM") == "1" else pytest.skip
    token = os.environ.get("WOKWI_CLI_TOKEN")
    if not token:
        stop("WOKWI_CLI_TOKEN not set")
    if not (BUILD / "firmware.bin").exists():
        stop("firmware not built. run: pio run")
    return token


@pytest.fixture(scope="module")
def sim():
    n = Node(_token())
    yield n
    n.close()


@pytest.fixture(scope="module")
def sim_no_sensor():
    n = Node(_token(), diagram=ROOT / "diagrams" / "no-sensor" / "diagram.json")
    yield n
    n.close()


@pytest.fixture
def node(sim):
    """Fresh boot for each test."""
    sim.start()
    return sim


@pytest.fixture
def artifacts():
    ARTIFACTS.mkdir(exist_ok=True)
    return ARTIFACTS
