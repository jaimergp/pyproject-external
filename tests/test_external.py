from textwrap import dedent

try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pyproject_external import External, DepURL


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


def test_libyaml_host_as_build():
    toml = dedent(
        """
        [external]
        build-requires = ["dep:generic/libyaml"]
        """
    )
    ext = External.from_pyproject_data(tomllib.loads(toml))
    assert len(ext.build_requires) == 1
    assert ext.build_requires[0] == DepURL.from_string("dep:generic/libyaml")
    assert ext.map_dependencies(
        "fedora",
        key="build_requires",  # note mapping only has host deps for this one
        package_manager="dnf",
    ) == ["libyaml", "libyaml-devel"]
    assert set(["dnf", "install", "libyaml", "libyaml-devel"]).issubset(
        ext.install_command(
            "fedora",
            key="build_requires",
            package_manager="dnf",
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
