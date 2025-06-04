# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
import logging
import shlex
import tarfile
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import distro
import tomli_w
import typer
from rich import print as rprint
from rich.console import Console
from rich.logging import RichHandler

from . import External, Mapping, Ecosystems


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=Console(stderr=True))],
)
log = logging.getLogger(__name__)


@cache
def _known_ecosystems() -> Ecosystems:
    return Ecosystems.from_default()


@cache
def _remote_mapping(ecosystem_or_url: str) -> Mapping:
    if ecosystem_or_url.startswith(("http://", "https://")):
        return Mapping.from_url(ecosystem_or_url)
    return Mapping.from_default(ecosystem_or_url)


def _detect_ecosystem(package_manager: str) -> str:
    for ecosystem, mapping in _known_ecosystems().iter_items():
        mapping = _remote_mapping(mapping["mapping"])
        try:
            mapping.get_package_manager(package_manager)
        except ValueError:
            continue
        else:
            return ecosystem
    raise ValueError(f"No ecosystem detected for package manager '{package_manager}'")


def _detect_ecosystem_and_package_manager() -> tuple[str, str]:
    for name in (distro.id(), distro.like()):
        if name == "darwin":
            return "homebrew", "brew"
        mapping = _known_ecosystems().get_mapping(name, default=None)
        if mapping:
            return name, mapping.package_managers[0]["name"]

    log.warning("No support for distro %s yet!", distro.id())
    # FIXME
    return "fedora", "dnf"


def _read_pyproject_from_sdist(path: Path) -> str:
    with tarfile.open(path) as tar:
        for info in tar.getmembers():
            name = info.name
            if "/" in name and name.split("/")[-1] == "pyproject.toml":
                return tar.extractfile(info).read().decode()
    raise ValueError("Could not read pyproject.toml file from sdist")


class _OutputChoices(Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    MAPPED_TABLE = "mapped"
    MAPPED_LIST = "mapped-list"
    COMMAND = "command"


def main(
    package: Annotated[
        str,
        typer.Argument(
            help="Package to analyze. It can be a path to a pyproject.toml-containing directory,"
            " or a source distribution."
        ),
    ],
    validate: Annotated[
        bool,
        typer.Option(help="Validate external dependencies against central registry."),
    ] = False,
    output: Annotated[
        _OutputChoices,
        typer.Option(
            help="Choose output format. 'raw' prints the TOML table as is. "
            "'normalized' processes the 'dep:' URLs before printing them. "
            "'mapped' prints the dependencies mapped to the given ecosystem. "
            "'command' prints the install command for the given package manager."
        ),
    ] = _OutputChoices.RAW,
    package_manager: Annotated[
        str,
        typer.Option(help="If given, use this package manager rather than auto-detect one."),
    ] = "",
) -> None:
    package = Path(package)
    if package.is_file():
        if not package.name.lower().endswith(".tar.gz"):
            raise typer.BadParameter(f"Given package '{package}' is a file, but not a sdist.")
        pyproject_text = _read_pyproject_from_sdist(package)
    elif package.is_dir():
        pyproject_text = (package / "pyproject.toml").read_text()

    pyproject = tomllib.loads(pyproject_text)
    raw_external = pyproject.get("external")
    if not raw_external:
        raise typer.BadParameter("Package's pyproject.toml does not contain an 'external' table.")

    if output == _OutputChoices.RAW:
        rprint(r"\[external]")
        rprint(tomli_w.dumps(raw_external).rstrip())
        return

    external = External.from_pyproject_data(pyproject)
    if validate:
        external.validate()

    if output == _OutputChoices.NORMALIZED:
        rprint(rf"\{tomli_w.dumps(external.to_dict())}")
        return

    if package_manager:
        ecosystem = _detect_ecosystem(package_manager)
    else:
        ecosystem, package_manager = _detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)
    if output == _OutputChoices.MAPPED_TABLE:
        mapped_dict = external.to_dict(mapped_for=ecosystem, package_manager=package_manager)
        rprint(rf"\{tomli_w.dumps(mapped_dict)}")
    # The following outputs might be used in shell substitutions like $(), so use print()
    # directly. rich's print will hard-wrap the line and break the output.
    elif output == _OutputChoices.COMMAND:
        print(shlex.join(external.install_command(ecosystem, package_manager=package_manager)))
    elif output == _OutputChoices.MAPPED_LIST:
        print(shlex.join(external.map_dependencies(ecosystem, package_manager=package_manager)))
    else:
        raise typer.BadParameter(f"Unknown value for --output: {output}")


def entry_point() -> None:
    typer.run(main)


if __name__ == "__main__":
    import sys

    sys.exit(entry_point())
