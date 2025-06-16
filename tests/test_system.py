import os
import sys

import pytest

from pyproject_external import detect_ecosystem_and_package_manager


@pytest.mark.skipif(
    not os.environ.get("CI") and not sys.platform.startswith("linux"),
    reason="Only for Ubuntu on CI",
)
def test_ubuntu():
    assert detect_ecosystem_and_package_manager() == ("ubuntu", "apt")


@pytest.mark.skipif(sys.platform != "darwin", reason="Only for macOS")
def test_macos():
    assert detect_ecosystem_and_package_manager() == ("homebrew", "brew")


@pytest.mark.skipif(sys.platform != "win32", reason="Only for Windows")
def test_windows():
    assert detect_ecosystem_and_package_manager() == ("vcpkg", "vcpkg")
