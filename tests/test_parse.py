# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

from pyproject_external import DepURL


def test_parse():
    # TODO: scheme should be dep:
    pkg = DepURL.from_string("pkg:pypi/requests@>=2.0")
    # Current packageurl-python (0.16.0) does not
    # complain about operators in versions :)
    assert pkg.type == "pypi"
    assert pkg.name == "requests"
    assert pkg.version == ">=2.0"
