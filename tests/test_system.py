import sys

import distro
import pytest

from pyproject_external import detect_ecosystem_and_package_manager


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
