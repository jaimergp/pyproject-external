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
from .._constants import UnsupportedConstraintsBehaviour
from .._exceptions import UnsupportedSpecError
from ._utils import _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()
user_config = Config.load_user_config()


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
            "'mapped' prints a table with the dependencies mapped to the given ecosystem. "
            "'mapped-list' does the same but prints the dependencies as a flat list. "
            "'command' prints the install command for the given package manager."
        ),
    ] = _OutputChoices.RAW.value,
    package_manager: Annotated[
        str,
        typer.Option(
            help="If given, use this package manager rather than the auto-detected one. "
            "Only applies to --output 'mapped', 'mapped-list' and 'command'."
        ),
    ] = user_config.preferred_package_manager or "",
    command_separator: Annotated[
        str,
        typer.Option(
            help="With --output=command, some package managers will generate several commands. "
            "Use this option to change how they are joined in a single line.",
        ),
    ] = " && ",
    unsupported_constraints_behaviour: Annotated[
        UnsupportedConstraintsBehaviour,
        typer.Option(
            help="Whether to error, warn or ignore unsupported version constraints when mapping. "
            "Constraints will be dropped if needed."
        ),
    ] = user_config.unsupported_constraints_behaviour,
) -> None:
    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    raw_external = pyproject.get("external")
    if not raw_external:
        raise typer.BadParameter("Package's pyproject.toml does not contain an 'external' table.")

    external: External = External.from_pyproject_data(pyproject)
    if validate:
        external.validate()

    if output == _OutputChoices.RAW:
        rprint(escape(tomli_w.dumps({"external": raw_external}).rstrip()))
        return

    if output == _OutputChoices.NORMALIZED:
        try:
            to_dump = external.to_dict(with_version=True)
        except UnsupportedSpecError as exc:
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
                raise
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
                log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
            to_dump = external.to_dict(with_version=False)
        rprint(escape(tomli_w.dumps(to_dump)))
        return

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)
    if output == _OutputChoices.MAPPED_TABLE:
        try:
            mapped_dict = external.to_dict(
                mapped_for=ecosystem,
                package_manager=package_manager,
                with_version=True,
            )
        except UnsupportedSpecError as exc:
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
                raise
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
                log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
            mapped_dict = external.to_dict(
                mapped_for=ecosystem,
                package_manager=package_manager,
                with_version=False,
            )
        rprint(escape(tomli_w.dumps(mapped_dict)))
    # The following outputs might be used in shell substitutions like $(), so use print()
    # directly. rich's print will hard-wrap the line and break the output.
    elif output == _OutputChoices.COMMAND:
        try:
            commands = external.install_commands(
                ecosystem,
                package_manager=package_manager,
                with_version=True,
            )
        except UnsupportedSpecError as exc:
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
                raise
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
                log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
            commands = external.install_commands(
                ecosystem,
                package_manager=package_manager,
                with_version=False,
            )
        print(command_separator.join(map(str, commands)))
    elif output == _OutputChoices.MAPPED_LIST:
        try:
            deps = external.map_versioned_dependencies(ecosystem, package_manager=package_manager)
        except UnsupportedSpecError as exc:
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
                raise
            if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
                log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
            deps = external.map_dependencies(ecosystem, package_manager=package_manager)
        print(shlex.join(deps))
    else:
        raise typer.BadParameter(f"Unknown value for --output: {output}")
