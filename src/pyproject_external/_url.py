# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Parse dep: dependencies
"""

from packageurl import PackageURL


class DepURL(PackageURL):
    # TODO: Needs https://github.com/package-url/packageurl-python/pull/184
    SCHEME = "dep"
