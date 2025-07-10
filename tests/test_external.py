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
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert len(ext.build_requires) == 1
    assert ext.build_requires[0] == DepURL.from_string("dep:virtual/compiler/c")
    assert ext.map_dependencies(
        "conda-forge",
        key="build_requires",
        package_manager="conda",
    ) == ["c-compiler", "python"]
    assert set(["conda", "install", "c-compiler", "python"]).issubset(
        ext.install_command(
            "conda-forge",
            key="build_requires",
            package_manager="conda",
        )
    )


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
        key="optional_build_requires",
        package_manager="conda",
    ) == ["make", "ninja", "libarrow-all"]
    assert set(["conda", "install", "make", "ninja", "libarrow-all"]).issubset(
        ext.install_command(
            "conda-forge",
            package_manager="conda",
        )
    )


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
        key="dependency_groups",
        package_manager="conda",
    ) == ["libarrow-all", "make", "ninja"]
    assert set(["conda", "install", "make", "ninja", "libarrow-all"]).issubset(
        ext.install_command(
            "conda-forge",
            package_manager="conda",
        )
    )


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
