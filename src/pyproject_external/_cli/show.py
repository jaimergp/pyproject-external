# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
"""
Query PEP 725 [external] metadata from pyproject.toml or source distributions.
"""

import logging
import shlex
from enum import Enum
from pathlib import Path
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w
import typer
from rich import print as rprint
from rich.markup import escape

# Only import from __init__ to make sure the only uses the public interface
from .. import (
    Config,
    External,
    detect_ecosystem_and_package_manager,
    find_ecosystem_for_package_manager,
)
from ._utils import _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()


class _OutputChoices(Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    MAPPED_TABLE = "mapped"
    MAPPED_LIST = "mapped-list"
    COMMAND = "command"


@app.command(help=__doc__)
def show(
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
    ] = _OutputChoices.RAW.value,
    package_manager: Annotated[
        str,
        typer.Option(help="If given, use this package manager rather than the auto-detected one."),
    ] = Config.load_user_config().preferred_package_manager or "",
) -> None:
    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    raw_external = pyproject.get("external")
    if not raw_external:
        raise typer.BadParameter("Package's pyproject.toml does not contain an 'external' table.")

    external = External.from_pyproject_data(pyproject)
    if validate:
        external.validate()

    if output == _OutputChoices.RAW:
        rprint(escape(tomli_w.dumps({"external": raw_external}).rstrip()))
        return

    if output == _OutputChoices.NORMALIZED:
        rprint(escape(tomli_w.dumps(external.to_dict())))
        return

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)
    if output == _OutputChoices.MAPPED_TABLE:
        mapped_dict = external.to_dict(mapped_for=ecosystem, package_manager=package_manager)
        rprint(escape(tomli_w.dumps(mapped_dict)))
    # The following outputs might be used in shell substitutions like $(), so use print()
    # directly. rich's print will hard-wrap the line and break the output.
    elif output == _OutputChoices.COMMAND:
        print(shlex.join(external.install_command(ecosystem, package_manager=package_manager)))
    elif output == _OutputChoices.MAPPED_LIST:
        print(shlex.join(external.map_dependencies(ecosystem, package_manager=package_manager)))
    else:
        raise typer.BadParameter(f"Unknown value for --output: {output}")
