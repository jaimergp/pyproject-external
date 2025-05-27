# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

from pyproject_external import DepURL


def test_parse():
    dep = DepURL.from_string("dep:pypi/requests@>=2.0")
    assert isinstance(dep, DepURL)
    # Current packageurl-python (0.16.0) does not
    # complain about operators in versions :)
    assert dep.type == "pypi"
    assert dep.name == "requests"
    assert dep.version == ">=2.0"


def test_export():
    dep = DepURL.from_string("dep:pypi/requests@>=2.0")
    assert dep.to_string() == "dep:pypi/requests@>=2.0"
    assert dep.to_core_metadata_string() == "pkg:pypi/requests (vers:pypi/>=2.0)"
    assert dep.to_purl_string() == "pkg:pypi/requests?vers=vers:pypi/%3E%3D2.0"
