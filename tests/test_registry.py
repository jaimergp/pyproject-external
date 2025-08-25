# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

import sys
from functools import cache

import pytest
import requests

from pyproject_external import DepURL, Ecosystems, Mapping, Registry
from pyproject_external._registry import (
    Command,
    CommandInstructions,
    MappedSpec,
    PackageManager,
    ValidationErrors,
    _Validated,
)


@cache
def default_registry() -> Registry:
    return Registry.from_default()


@cache
def default_ecosystems() -> Ecosystems:
    return Ecosystems.from_default()


@cache
def small_conda_forge_mapping() -> Mapping:
    return Mapping(
        {
            "name": "conda-forge",
            "mappings": [
                {
                    "id": "dep:generic/arrow",
                    "description": "C++ libraries for Apache Arrow",
                    "specs": "libarrow-all",
                    "urls": {"feedstock": "https://github.com/conda-forge/arrow-cpp-feedstock"},
                },
                {
                    "id": "dep:generic/multi-arrow",
                    "description": "C++ libraries for Apache Arrow, with two specs",
                    "specs": ["libarrow-all", "libarrow"],
                    "urls": {"feedstock": "https://github.com/conda-forge/arrow-cpp-feedstock"},
                },
                {
                    "id": "dep:generic/make",
                    "description": "GNU Make",
                    "specs": "make",
                    "urls": {"feedstock": "https://github.com/conda-forge/make-feedstock"},
                },
            ],
            "package_managers": [
                {
                    "name": "conda",
                    "commands": {
                        "install": {
                            "command": [
                                "conda",
                                "install",
                                "{}",
                            ],
                            "multiple_specifiers": "always",
                        },
                        "query": {"command": ["conda", "list", "-f", "{}"]},
                    },
                    "specifier_syntax": {
                        "exact_version": ["{name}=={version}"],
                        "name_only": ["{name}"],
                        "version_ranges": {
                            "and": ",",
                            "equal": "={version}",
                            "greater_than": ">{version}",
                            "greater_than_equal": ">={version}",
                            "less_than": "<{version}",
                            "less_than_equal": "<={version}",
                            "not_equal": "!={version}",
                            "syntax": ["{name}{ranges}"],
                        },
                    },
                },
                {
                    "name": "name-only-conda",
                    "commands": {
                        "install": {
                            "command": [
                                "conda",
                                "install",
                                "{}",
                            ],
                            "multiple_specifiers": "name-only",
                        },
                        "query": {"command": ["conda", "list", "-f", "{}"]},
                    },
                    "specifier_syntax": {
                        "exact_version": ["{name}", "--version", "{version}"],
                        "name_only": ["{name}"],
                        "version_ranges": {
                            "and": ",",
                            "equal": "={version}",
                            "greater_than": ">{version}",
                            "greater_than_equal": ">={version}",
                            "less_than": "<{version}",
                            "less_than_equal": "<={version}",
                            "not_equal": "!={version}",
                            "syntax": ["{name}{ranges}"],
                        },
                    },
                },
                {
                    "name": "single-spec-conda",
                    "commands": {
                        "install": {
                            "command": [
                                "conda",
                                "install",
                                "{}",
                            ],
                            "multiple_specifiers": "never",
                        },
                        "query": {"command": ["conda", "list", "-f", "{}"]},
                    },
                    "specifier_syntax": {
                        "exact_version": ["{name}", "--version", "{version}"],
                        "name_only": ["{name}"],
                        "version_ranges": {
                            "and": ",",
                            "equal": "={version}",
                            "greater_than": ">{version}",
                            "greater_than_equal": ">={version}",
                            "less_than": "<{version}",
                            "less_than_equal": "<={version}",
                            "not_equal": "!={version}",
                            "syntax": ["{name}{ranges}"],
                        },
                    },
                },
            ],
        }
    )


def test_registry():
    default_registry().validate()


def test_ecosystems():
    default_ecosystems().validate()


class _ValidationDefault(_Validated):
    default_schema = "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/main/schemas/central-registry.schema.json"

    def __init__(self, data):
        self.data = data


def test_schema_validation_default_url():
    with pytest.raises(ValidationErrors, match="Validation error"):
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

    with pytest.raises(ValidationErrors, match="Validation error"):
        _ValidationDefaultPath({}).validate()
    _ValidationDefaultPath({"definitions": []}).validate()


def test_schema_validation_with_schema_url():
    with pytest.raises(ValidationErrors, match="Validation error"):
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
    with pytest.raises(ValidationErrors, match="Validation error"):
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
    "dep_url,error",
    [
        ("pkg:generic/bad-scheme", 'purl is missing the required "dep" scheme'),
        ("absolutely-not-a-dep-urldep:virtual", 'purl is missing the required "dep" scheme'),
        ("dep:virtual/not-valid", "'dep:virtual/\\*' only accepts 'compiler' or 'interface'"),
        ("dep:virtual/not-valid/name", "'dep:virtual/\\*' only accepts 'compiler' or 'interface'"),
    ],
)
def test_registry_dep_urls_fail_validation(dep_url, error):
    with pytest.raises(ValueError, match=error):
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
    with pytest.raises(ValueError, match="cannot be found"):
        default_ecosystems().get_mapping("does-not-exist")


def test_registry_iter_unique_ids():
    reg = default_registry()
    assert sorted(reg.iter_unique_ids()) == sorted(dict.fromkeys(reg.iter_unique_ids()))


def test_registry_iter_by_id():
    reg = default_registry()
    for item in reg.iter_by_id("dep:generic/arrow"):
        assert item["id"] == "dep:generic/arrow"


def test_registry_iter_canonical():
    reg = default_registry()
    for item in reg.iter_canonical():
        assert (
            item["id"].startswith("dep:virtual/")
            or not item.get("provides")
            or all(prov.startswith("dep:virtual/") for prov in item.get("provides"))
        )


def test_registry_iter_aliases():
    reg = default_registry()
    for item in reg.iter_aliases():
        assert item["provides"]


def test_registry_iter_generic():
    reg = default_registry()
    for item in reg.iter_generic():
        assert item["id"].startswith("dep:generic/")


def test_registry_iter_virtual():
    reg = default_registry()
    for item in reg.iter_virtual():
        assert item["id"].startswith("dep:virtual/")


def test_mapping_iter_by_id():
    mapping = small_conda_forge_mapping()
    entry = next(mapping.iter_by_id("dep:generic/arrow"))
    assert isinstance(entry, dict)
    assert entry["id"] == "dep:generic/arrow"


def test_mapping_iter_specs_by_id():
    mapping = small_conda_forge_mapping()
    specs = next(mapping.iter_specs_by_id("dep:generic/arrow"))
    assert isinstance(specs, list)
    assert len(specs) == 1
    assert specs[0].name == "libarrow-all"
    assert specs[0].version == ""

    specs = next(mapping.iter_specs_by_id("dep:generic/arrow@>=2"))
    assert isinstance(specs, list)
    assert len(specs) == 1
    assert specs[0].name == "libarrow-all"
    assert specs[0].version == ">=2"


@pytest.mark.parametrize(
    "dep_url,expected",
    (
        ("dep:generic/arrow", "libarrow-all"),
        ("dep:generic/arrow@20", "libarrow-all==20"),
        ("dep:generic/arrow@>20", "libarrow-all>20"),
        ("dep:generic/arrow@<22,>=21", "libarrow-all<22,>=21"),
    ),
)
@pytest.mark.parametrize("command_type", ["install", "query"])
def test_mapping_iter_commands(dep_url, expected, command_type):
    mapping = small_conda_forge_mapping()
    commands = next(mapping.iter_commands(command_type, dep_url, "conda"))
    assert isinstance(commands, list)
    assert len(commands) == 1
    if command_type == "install":
        assert commands[0].template == ["conda", "install", "{}"]
    elif command_type == "query":
        assert commands[0].template == ["conda", "list", "-f", "{}"]
    assert commands[0].arguments == [expected]


@pytest.mark.parametrize("depurl", ["dep:generic/multi-arrow", "dep:generic/multi-arrow@2"])
def test_mapping_iter_commands_name_only(depurl):
    mapping = small_conda_forge_mapping()
    commands = next(mapping.iter_commands("install", depurl, "name-only-conda"))
    assert isinstance(commands, list)
    if "@" in depurl:  # versioned, several commands
        assert len(commands) == 2
        assert commands[0].template == commands[1].template == ["conda", "install", "{}"]
        assert commands[0].arguments == ["libarrow-all", "--version", "2"]
        assert commands[1].arguments == ["libarrow", "--version", "2"]
    else:
        assert len(commands) == 1
        assert commands[0].template == ["conda", "install", "{}"]
        assert commands[0].arguments == ["libarrow-all", "libarrow"]


@pytest.mark.parametrize("depurl", ["dep:generic/multi-arrow", "dep:generic/multi-arrow@2"])
def test_mapping_iter_commands_single_spec(depurl):
    mapping = small_conda_forge_mapping()
    commands = next(mapping.iter_commands("install", depurl, "single-spec-conda"))
    assert isinstance(commands, list)
    assert len(commands) == 2
    assert commands[0].template == commands[1].template == ["conda", "install", "{}"]
    if "@" in depurl:  # versioned, several arguments
        assert commands[0].arguments == ["libarrow-all", "--version", "2"]
        assert commands[1].arguments == ["libarrow", "--version", "2"]
    else:
        assert commands[0].arguments == ["libarrow-all"]
        assert commands[1].arguments == ["libarrow"]


def test_mapping_commands():
    mapping = small_conda_forge_mapping()
    assert [
        "conda",
        "install",
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


def test_command_validation():
    with pytest.raises(ValueError, match="template"):
        Command(["pkg", "install"], ["name"])
    with pytest.raises(ValueError, match="template"):
        Command(["pkg", "install", "{}", "{}"], ["name"])
    with pytest.raises(ValueError, match="template"):
        Command(["pkg", "install", "{}{}"], ["name"])
    # This one is ok
    Command(["pkg", "install", "{}"], ["name"])


def test_command_merge():
    command1 = Command(["pkg", "install", "{}"], ["name1"])
    command2 = Command(["pkg", "install", "{}"], ["name2"])
    merged = Command.merge(command1, command2)
    assert merged.template == ["pkg", "install", "{}"]
    assert merged.arguments == ["name1", "name2"]


def test_command_merge_wrong():
    command1 = Command(["pkg", "install", "{}"], ["name1"])
    command2 = Command(["pkg", "update", "{}"], ["name2"])
    with pytest.raises(ValueError):
        Command.merge(command1, command2)


def test_command_instructions():
    instr = CommandInstructions(
        command_template=["pkg", "install", "{}"],
        requires_elevation=False,
        multiple_specifiers="always",
    )
    assert instr.render_template() == ["pkg", "install", "{}"]


def test_command_instructions_elevation():
    instr = CommandInstructions(
        command_template=["pkg", "install", "{}"],
        requires_elevation=True,
        multiple_specifiers="always",
    )
    if sys.platform.startswith("win"):
        assert instr.render_template() == ["runas", "pkg", "install", "{}"]
    else:
        assert instr.render_template() == ["sudo", "pkg", "install", "{}"]


def test_command_instructions_wrong():
    with pytest.raises(ValueError, match="command_template"):
        CommandInstructions(
            command_template=["pkg", "install"],
            requires_elevation=False,
            multiple_specifiers="always",
        )
    with pytest.raises(ValueError, match="multiple_specifiers"):
        CommandInstructions(
            command_template=["pkg", "install", "{}"],
            requires_elevation=False,
            multiple_specifiers="sometimes",
        )


_package_manager_pep440 = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "always",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": ["{name}==={version}"],
            "name_only": ["{name}"],
            "version_ranges": {
                "and": ",",
                "equal": "={version}",
                "greater_than": ">{version}",
                "greater_than_equal": ">={version}",
                "less_than": "<{version}",
                "less_than_equal": "<={version}",
                "not_equal": "!={version}",
                "syntax": ["{name}{ranges}"],
            },
        },
    },
)
_package_manager_pep440_single_spec = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "never",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": ["{name}==={version}"],
            "name_only": ["{name}"],
            "version_ranges": {
                "and": ",",
                "equal": "={version}",
                "greater_than": ">{version}",
                "greater_than_equal": ">={version}",
                "less_than": "<{version}",
                "less_than_equal": "<={version}",
                "not_equal": "!={version}",
                "syntax": ["--spec", "{name}", "--version", "{ranges}"],
            },
        },
    },
)
_package_manager_pep440_name_only = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "name-only",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": ["{name}==={version}"],
            "name_only": ["{name}"],
            "version_ranges": {
                "and": ",",
                "equal": "={version}",
                "greater_than": ">{version}",
                "greater_than_equal": ">={version}",
                "less_than": "<{version}",
                "less_than_equal": "<={version}",
                "not_equal": "!={version}",
                "syntax": ["--spec", "{name}", "--version", "{ranges}"],
            },
        },
    },
)
_package_manager_name_only = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "name-only",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": None,
            "name_only": ["--spec", "{name}"],
            "version_ranges": None,
        },
    },
)
_package_manager_exact_version_only = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "always",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": ["--spec", "{name}", "--version", "{version}"],
            "name_only": ["--spec", "{name}"],
            "version_ranges": None,
        },
    },
)
_package_manager_names_only = PackageManager.from_mapping_entry(
    {
        "name": "pkg",
        "commands": {
            "install": {
                "command": [
                    "pkg",
                    "install",
                    "{}",
                ],
                "multiple_specifiers": "always",
            },
            "query": {"command": ["pkg", "list", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": None,
            "name_only": ["--spec", "{name}"],
            "version_ranges": None,
        },
    },
)
_package_manager_gentoo = PackageManager.from_mapping_entry(
    {
        "name": "portage",
        "commands": {
            "install": {
                "command": ["emerge", "{}"],
                "multiple_specifiers": "always",
                "requires_elevation": True,
            },
            "query": {"command": ["portageq", "has_version", "/", "{}"]},
        },
        "specifier_syntax": {
            "exact_version": ["={name}-{version}"],
            "name_only": ["{name}"],
            "version_ranges": {
                "and": None,
                "equal": "={name}-{version}*",
                "greater_than": ">{name}-{version}",
                "greater_than_equal": ">={name}-{version}",
                "less_than": "<{name}-{version}",
                "less_than_equal": "<={name}-{version}",
                "not_equal": None,
                "syntax": ["{ranges}"],
            },
        },
    }
)


@pytest.mark.parametrize(
    "mgr,name,version,expected",
    (
        (_package_manager_pep440, "libarrow-all", "", ["libarrow-all"]),
        (_package_manager_pep440, "libarrow-all", "20", ["libarrow-all===20"]),
        (_package_manager_pep440, "libarrow-all", ">20", ["libarrow-all>20"]),
        (_package_manager_pep440, "libarrow-all", "<22,>=21", ["libarrow-all<22,>=21"]),
        (_package_manager_name_only, "libarrow-all", "", ["--spec", "libarrow-all"]),
        (_package_manager_name_only, "libarrow-all", "20", ValueError),
        (_package_manager_name_only, "libarrow-all", ">20", ValueError),
        (_package_manager_name_only, "libarrow-all", "<22,>=21", ValueError),
        (_package_manager_exact_version_only, "libarrow-all", "", ["--spec", "libarrow-all"]),
        (
            _package_manager_exact_version_only,
            "libarrow-all",
            "20",
            ["--spec", "libarrow-all", "--version", "20"],
        ),
        (_package_manager_exact_version_only, "libarrow-all", ">20", ValueError),
        (_package_manager_exact_version_only, "libarrow-all", "<22,>=21", ValueError),
        (
            _package_manager_gentoo,
            "libarrow-all",
            "<22,>=21",
            ["<libarrow-all-22", ">=libarrow-all-21"],
        ),
        (_package_manager_gentoo, "libarrow-all", "!=21", ValueError),
    ),
)
def test_package_manager_render_spec(mgr, name, version, expected):
    if expected is ValueError:
        with pytest.raises(expected):
            mgr.render_spec(MappedSpec(name, version))
    else:
        assert mgr.render_spec(MappedSpec(name, version)) == expected


@pytest.mark.parametrize(
    "mgr,specs,expected",
    (
        (
            _package_manager_pep440_single_spec,
            [MappedSpec("libarrow-all", "")],
            [["pkg", "install", "libarrow-all"]],
        ),
        (
            _package_manager_pep440,
            [
                MappedSpec("libarrow-all", ""),
                MappedSpec("libarrow-all", ""),
            ],
            [["pkg", "install", "libarrow-all"]],  # deduplicated
        ),
        (
            _package_manager_pep440_single_spec,
            [
                MappedSpec("libarrow-all", ""),
                MappedSpec("libarrow-all", ""),
            ],
            [["pkg", "install", "libarrow-all"]],  # deduplicated
        ),
        (
            _package_manager_pep440,
            [MappedSpec("libarrow-all", "20"), MappedSpec("make", "")],
            [["pkg", "install", "libarrow-all===20", "make"]],
        ),
        (
            _package_manager_exact_version_only,
            [MappedSpec("libarrow-all", "20"), MappedSpec("make", "")],
            [["pkg", "install", "--spec", "libarrow-all", "--version", "20", "--spec", "make"]],
        ),
        (
            _package_manager_exact_version_only,
            [MappedSpec("libarrow-all", ">20"), MappedSpec("make", "")],
            ValueError,
        ),
        (
            _package_manager_pep440_single_spec,
            [
                MappedSpec("libarrow-all", ">20"),
                MappedSpec("make", ""),
                MappedSpec("cat", ""),
            ],
            [
                ["pkg", "install", "--spec", "libarrow-all", "--version", ">20"],
                ["pkg", "install", "make"],
                ["pkg", "install", "cat"],
            ],
        ),
        (
            _package_manager_pep440_name_only,
            [
                MappedSpec("libarrow-all", "<22,>=21"),
                MappedSpec("make", ""),
                MappedSpec("cat", ""),
            ],
            [
                ["pkg", "install", "make", "cat"],
                ["pkg", "install", "--spec", "libarrow-all", "--version", "<22,>=21"],
            ],
        ),
        (
            _package_manager_names_only,
            [
                MappedSpec("libarrow-all", "<22,>=21"),
                MappedSpec("make", ""),
                MappedSpec("cat", ""),
            ],
            ValueError,
        ),
    ),
)
def test_package_manager_render_commands(mgr, specs, expected):
    if expected is ValueError:
        with pytest.raises(expected):
            mgr.render_commands("install", specs)
    else:
        assert [command.render() for command in mgr.render_commands("install", specs)] == expected
