# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Query whether the external dependencies of a package are already satisfied.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import typer

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


@app.command(
    help=__doc__,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def query(
    package: Annotated[
        str,
        typer.Argument(
            help="Package whose external dependencies need to be queried. "
            "It can be a path to a pyproject.toml-containing directory, "
            "or a source distribution."
        ),
    ],
    package_manager: Annotated[
        str,
        typer.Option(
            help="If given, use this package manager to query the external dependencies "
            "rather than the auto-detected one."
        ),
    ] = user_config.preferred_package_manager or "",
    unsupported_constraints_behaviour: Annotated[
        UnsupportedConstraintsBehaviour,
        typer.Option(
            help="Whether to error, warn or ignore unsupported version constraints when mapping. "
            "Constraints will be dropped if needed."
        ),
    ] = user_config.unsupported_constraints_behaviour,
    unknown_args: typer.Context = typer.Option(None),
) -> None:
    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    external: External = External.from_pyproject_data(pyproject)
    external.validate(raises=False)

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)

    try:
        query_commands = external.query_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=True,
        )
    except UnsupportedSpecError as exc:
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
            raise
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
            log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
        query_commands = external.query_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=False,
        )

    errors = 0
    for query_command in query_commands:
        try:
            log.debug("Query command: %s", query_command)
            p = subprocess.run(query_command.render(), capture_output=True, text=True)
            log.debug("Stdout: %s", p.stdout)
            log.debug("Stderr: %s", p.stderr)
            p.check_returncode()
        except subprocess.CalledProcessError as exc:
            log.debug("Query exception.", exc_info=exc)
            log.error("Could not find %s as %s!", query_command.sources, query_command.arguments)
            errors += 1
        else:
            log.info("Found %s as %s", query_command.sources, query_command.arguments)
    if errors:
        sys.exit(1)
