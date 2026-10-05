"""Builds lib/core as a shared lib and loads it with ctypes."""
import ctypes
import os
import shutil
import subprocess

import pytest

from core_lib import CORE, Core

@pytest.fixture(scope="session")
def core(tmp_path_factory):
    cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    out = tmp_path_factory.mktemp("core") / "libcore.so"
    srcs = [str(CORE / "frame.c"), str(CORE / "logic.c")]
    subprocess.run(
        [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O1", "-shared", "-fPIC", "-o", str(out), *srcs],
        check=True,
    )
    return Core(ctypes.CDLL(str(out)))
