# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

from functools import cache

import pytest
from packageurl import PackageURL

from pyproject_external import Ecosystems, Mapping, Registry


@cache
def default_registry():
    return Registry.from_default()


@cache
def default_ecosystems():
    return Ecosystems.from_default()


def test_registry():
    default_registry().validate()


def test_ecosystems():
    default_ecosystems().validate()


@pytest.mark.parametrize("mapping", sorted(default_ecosystems().iter_names()))
def test_mappings(mapping):
    Mapping.from_default(mapping).validate()


@pytest.mark.parametrize(
    "dep_url",
    list(dict.fromkeys([entry["id"] for entry in default_registry().iter_all()])),
)
def test_registry_dep_urls_are_parsable(dep_url):
    if dep_url.startswith("dep:"):
        pytest.skip("dep URLs use a different schema and aren't parsable (yet?)")
    PackageURL.from_string(dep_url)


def test_resolve_virtual_gcc():
    mapping = Mapping.from_default("fedora")
    registry = default_registry()
    arrow = next(
        iter(mapping.iter_by_id("dep:virtual/compiler/c", resolve_with_registry=registry))
    )
    assert arrow["specs"]["build"] == ["gcc"]


def test_resolve_alias_arrow():
    mapping = Mapping.from_default("fedora")
    registry = default_registry()
    arrow = next(
        iter(mapping.iter_by_id("dep:github/apache/arrow", resolve_with_registry=registry))
    )
    assert arrow["specs"]["run"] == ["libarrow", "libarrow-dataset-libs"]


def test_ecosystem_get_mapping():
    assert default_ecosystems().get_mapping("fedora")
    assert default_ecosystems().get_mapping("does-not-exist", None) is None
    with pytest.raises(ValueError):
        default_ecosystems().get_mapping("does-not-exist")
