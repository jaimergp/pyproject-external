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


class _ValidationDefault(_Validated):
    default_schema = "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/main/schemas/central-registry.schema.json"

    def __init__(self, data):
        self.data = data


def test_schema_validation_default_url():
    with pytest.raises(ValidationErrors):
        _ValidationDefault({}).validate()
    _ValidationDefault({"definitions": []}).validate()


def test_schema_validation_default_path(tmp_path):
    r = requests.get(
        "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/"
        "main/schemas/central-registry.schema.json"
    )
    r.raise_for_status()
    (tmp_path / "schema.json").write_text(r.text)

    class _ValidationDefaultPath(_Validated):
        default_schema = tmp_path / "schema.json"

        def __init__(self, data):
            self.data = data

    with pytest.raises(ValidationErrors):
        _ValidationDefaultPath({}).validate()
    _ValidationDefaultPath({"definitions": []}).validate()


def test_schema_validation_with_schema_url():
    with pytest.raises(ValidationErrors):
        _ValidationDefault(
            {
                "$schema": "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/"
                "main/schemas/central-registry.schema.json"
            }
        ).validate()
    _ValidationDefault(
        {
            "$schema": "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/"
            "main/schemas/central-registry.schema.json",
            "definitions": [],
        }
    ).validate()


def test_schema_validation_with_schema_path(tmp_path):
    r = requests.get(
        "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/"
        "main/schemas/central-registry.schema.json"
    )
    r.raise_for_status()
    (tmp_path / "schema.json").write_text(r.text)
    with pytest.raises(ValidationErrors):
        _ValidationDefault({"$schema": str(tmp_path / "schema.json")}).validate()
    _ValidationDefault({"$schema": str(tmp_path / "schema.json"), "definitions": []}).validate()


@pytest.mark.parametrize("mapping", sorted(default_ecosystems().iter_names()))
def test_mappings(mapping):
    Mapping.from_default(mapping).validate()


@pytest.mark.parametrize(
    "dep_url",
    sorted(default_registry().iter_unique_ids()),
)
def test_registry_dep_urls_are_parsable(dep_url):
    DepURL.from_string(dep_url)


@pytest.mark.parametrize(
    "dep_url",
    [
        "pkg:generic/bad-scheme",
        "absolutely-not-a-dep-urldep:virtual",
        "dep:virtual/not-valid",
        "dep:virtual/not-valid/name",
    ],
)
def test_registry_dep_urls_fail_validation(dep_url):
    with pytest.raises(ValueError):
        DepURL.from_string(dep_url)


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


def test_commands():
    mapping = Mapping.from_default("conda-forge")
    assert [
        "conda",
        "install",
        "--yes",
        "--channel=conda-forge",
        "--strict-channel-priority",
        "make",
    ] in [
        command.render()
        for commands in mapping.iter_commands("install", "dep:generic/make", "conda")
        for command in commands
    ]
    assert [
        "conda",
        "list",
        "-f",
        "make",
    ] in [
        command.render()
        for commands in mapping.iter_commands("query", "dep:generic/make", "conda")
        for command in commands
    ]
