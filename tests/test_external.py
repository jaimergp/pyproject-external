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
