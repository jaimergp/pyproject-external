import os
from textwrap import dedent

try:
    import tomllib
except ImportError:
    import tomli as tomllib
import pytest

from pyproject_external import DepURL, External


def test_external():
    toml = dedent(
        """
        [external]
        build-requires = ["dep:virtual/compiler/c"]
        """
    )
    ext: External = External.from_pyproject_data(tomllib.loads(toml))
    assert len(ext.build_requires) == 1
    assert ext.build_requires[0] == DepURL.from_string("dep:virtual/compiler/c")
    assert ext.map_dependencies(
        "conda-forge",
        categories=("build_requires",),
        package_manager="conda",
    ) == ["c-compiler", "python"]
    install_commands = ext.install_commands(
        "conda-forge",
        categories=("build_requires",),
        package_manager="conda",
    )
    assert ["c-compiler", "python"] == install_commands[0].arguments


def test_external_optional():
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/make",
            "dep:generic/ninja",
            "dep:generic/arrow",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert len(ext.optional_build_requires) == 1
    assert len(ext.optional_build_requires["extra"]) == 3
    assert ext.optional_build_requires["extra"] == [
        DepURL.from_string("dep:generic/make"),
        DepURL.from_string("dep:generic/ninja"),
        DepURL.from_string("dep:generic/arrow"),
    ]
    assert ext.map_dependencies(
        "conda-forge",
        categories=("optional_build_requires",),
        package_manager="conda",
    ) == ["make", "ninja", "libarrow-all"]
    assert ["make", "ninja", "libarrow-all"] == ext.install_commands(
        "conda-forge",
        package_manager="conda",
    )[0].arguments


def test_external_dependency_groups():
    toml = dedent(
        """
        [external.dependency-groups]
        test = [
            "dep:generic/arrow",
            {include-group = "test-compiled"},
        ]
        test-compiled = [
            "dep:generic/make",
            "dep:generic/ninja",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert len(ext.dependency_groups) == 2
    assert len(ext.dependency_groups["test"]) == 3
    assert ext.dependency_groups["test"] == [
        DepURL.from_string("dep:generic/arrow"),
        DepURL.from_string("dep:generic/make"),
        DepURL.from_string("dep:generic/ninja"),
    ]
    assert ext.map_dependencies(
        "conda-forge",
        categories=("dependency_groups",),
        package_manager="conda",
    ) == ["libarrow-all", "make", "ninja"]
    assert [
        "libarrow-all",
        "make",
        "ninja",
    ] == ext.install_commands(
        "conda-forge",
        package_manager="conda",
    )[0].arguments


def test_crude_error_message():
    toml = dedent(
        """
        [external]
        build-requires = [
            "dep:generic/does-not-exist",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    with pytest.raises(ValueError, match="does not have any") as exc:
        ext.map_dependencies("fedora", package_manager="dnf")
    assert "Is this dependency in the right category?" not in str(exc.value)


def test_informative_error_message():
    toml = dedent(
        """
        [external]
        build-requires = [
            "dep:generic/libyaml",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    with pytest.raises(ValueError, match="Is this dependency in the right category?"):
        ext.map_dependencies("fedora", package_manager="dnf")


def test_crude_error_message_optional(caplog):
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/does-not-exist",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    ext.map_dependencies("fedora", package_manager="dnf")
    assert "does not have any" in caplog.text
    assert "Is this dependency in the right category?" not in caplog.text


def test_informative_error_message_optional(caplog):
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/libyaml",
        ]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    ext.map_dependencies("fedora", package_manager="dnf")
    assert "Is this dependency in the right category?" in caplog.text


def test_external_with_environment_markers_pass():
    toml = dedent(
        f"""
        [external]
        build-requires = ['dep:virtual/compiler/c; os_name == "{os.name}"']
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert ext.to_dict() == {
        "external": {
            "build_requires": [
                f'dep:virtual/compiler/c; os_name == "{os.name}"',
            ],
        },
    }
    assert len(ext.build_requires) == 1
    assert ext.build_requires[0] == DepURL.from_string(
        f'dep:virtual/compiler/c; os_name == "{os.name}"'
    )
    assert ext.map_dependencies(
        "conda-forge",
        categories=("build_requires",),
        package_manager="conda",
    ) == ["c-compiler", "python"]


def test_external_with_environment_markers_fail():
    toml = dedent(
        f"""
        [external]
        build-requires = ['dep:virtual/compiler/c; os_name != "{os.name}"']
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert (
        ext.map_dependencies(
            "conda-forge",
            categories=("build_requires",),
            package_manager="conda",
        )
        == []
    )


def test_external_map_dependencies():
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/arrow",
        ]
        """
    )
    ext: External = External.from_pyproject_data(tomllib.loads(toml))
    assert ext.map_dependencies("conda-forge", package_manager="conda") == ["libarrow-all"]


def test_external_map_versioned_dependencies():
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/arrow@2",
        ]
        """
    )
    ext: External = External.from_pyproject_data(tomllib.loads(toml))
    assert ext.map_versioned_dependencies("conda-forge", package_manager="conda") == [
        "libarrow-all==2"
    ]


def test_external_install_commands():
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/arrow",
            "dep:generic/make",
        ]
        """
    )
    ext: External = External.from_pyproject_data(tomllib.loads(toml))
    commands = ext.install_commands("conda-forge", package_manager="conda")
    assert len(commands) == 1
    assert commands[0].arguments == ["libarrow-all", "make"]


def test_external_query_commands():
    toml = dedent(
        """
        [external.optional-build-requires]
        extra = [
            "dep:generic/arrow",
            "dep:generic/make",
        ]
        """
    )
    ext: External = External.from_pyproject_data(tomllib.loads(toml))
    commands = ext.query_commands("conda-forge", package_manager="conda")
    assert len(commands) == 2
    assert commands[0].arguments == ["libarrow-all"]
    assert commands[1].arguments == ["make"]
