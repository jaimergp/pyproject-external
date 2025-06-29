import os
import shutil
import sys

import distro
import pytest

from pyproject_external import activated_conda_env, detect_ecosystem_and_package_manager


@pytest.mark.skipif(
    distro.id() != "ubuntu",
    reason="Only for Ubuntu",
)
def test_ubuntu(monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX")
    assert detect_ecosystem_and_package_manager() == ("ubuntu", "apt")


@pytest.mark.skipif(sys.platform != "darwin", reason="Only for macOS")
def test_macos(monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX")
    assert detect_ecosystem_and_package_manager() == ("homebrew", "brew")


@pytest.mark.skipif(sys.platform != "win32", reason="Only for Windows")
def test_windows(monkeypatch):
    monkeypatch.delenv("CONDA_PREFIX")
    assert detect_ecosystem_and_package_manager() == ("vcpkg", "vcpkg")


@pytest.mark.skipif(not shutil.which("pixi"), reason="Needs Pixi")
def test_pixi(monkeypatch):
    if not os.environ.get("CONDA_PREFIX"):
        monkeypatch.setenv("CONDA_PREFIX", sys.prefix)
    if not os.environ.get("PIXI_EXE"):
        monkeypatch.setenv("PIXI_EXE", shutil.which("pixi"))
    assert detect_ecosystem_and_package_manager() == ("conda-forge", "pixi")


@pytest.mark.parametrize("tool", ("conda", "mamba", "micromamba", "pixi"))
def test_activated_conda_env(tool):
    if not shutil.which(tool):
        pytest.skip()
    with activated_conda_env(tool, sys.prefix) as env:
        assert any(p.startswith(sys.prefix) for p in env["PATH"].split(os.pathsep))
        assert sorted(env) != sorted(os.environ)
