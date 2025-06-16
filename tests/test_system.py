import os
import sys

import pytest

from pyproject_external import detect_ecosystem_and_package_manager

pytestmark = pytest.mark.skipif(not os.environ.get("CI"), reason="On CI only.")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Only for Ubuntu")
def test_ubuntu():
    assert detect_ecosystem_and_package_manager() == ("ubuntu", "apt-get")


@pytest.mark.skipif(sys.platform != "darwin", reason="Only for macOS")
def test_macos():
    assert detect_ecosystem_and_package_manager() == ("homebrew", "brew")


@pytest.mark.skipif(sys.platform != "win32", reason="Only for Windows")
def test_windows():
    assert detect_ecosystem_and_package_manager() == ("win32", "vcpkg")
