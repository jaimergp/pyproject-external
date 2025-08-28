# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import sys

from packaging.markers import Marker

from pyproject_external import DepURL


def test_parse():
    dep = DepURL.from_string("dep:pypi/requests@>=2.0")
    assert isinstance(dep, DepURL)
    # Current packageurl-python (0.16.0) does not
    # complain about operators in versions :)
    assert dep.type == "pypi"
    assert dep.name == "requests"
    assert dep.version == ">=2.0"
    assert dep.environment_marker is None


def test_parse_with_environment_marker():
    dep = DepURL.from_string(
        "dep:pypi/requests@>=2.0; python_version == "
        f"'{sys.version_info.major}.{sys.version_info.minor}'"
    )
    assert dep.environment_marker == Marker(
        f"python_version == '{sys.version_info.major}.{sys.version_info.minor}'"
    )
    assert dep.evaluate_environment_marker()
    assert dep.to_string() == "dep:pypi/requests@>=2.0"
    assert dep.to_string(drop_environment_marker=False) == (
        "dep:pypi/requests@>=2.0; "
        f'python_version == "{sys.version_info.major}.{sys.version_info.minor}"'
    )

    dep = DepURL.from_string(
        "dep:pypi/requests@>=2.0; python_version == "
        f"'{sys.version_info.major + 1}.{sys.version_info.minor}'"
    )
    assert not dep.evaluate_environment_marker()


def test_export():
    dep = DepURL.from_string("dep:pypi/requests@>=2.0")
    assert dep.to_string() == "dep:pypi/requests@>=2.0"
    assert dep.to_core_metadata_string() == "pkg:pypi/requests (vers:pypi/>=2.0)"
    assert dep.to_purl_string() == "pkg:pypi/requests?vers=vers:pypi/%3E%3D2.0"
