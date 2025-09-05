# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Build a wheel for the given sdist or project.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tarfile
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import typer

from .. import (
    Config,
    External,
    activated_conda_env,
    detect_ecosystem_and_package_manager,
    find_ecosystem_for_package_manager,
)
from .._constants import PythonInstallers, UnsupportedConstraintsBehaviour
from .._exceptions import UnsupportedSpecError
from ._utils import NotOnCIError, _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()
user_config = Config.load_user_config()


@app.command(
    help=__doc__,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def build(
    package: Annotated[
        str,
        typer.Argument(
            help="Package to build wheel for."
            "It can be a path to a pyproject.toml-containing directory, "
            "or a source distribution."
        ),
    ],
    package_manager: Annotated[
        str,
        typer.Option(
            help="If given, use this package manager to install the external dependencies "
            "rather than the auto-detected one."
        ),
    ] = Config.load_user_config().preferred_package_manager or "",
    outdir: Annotated[
        str | None,
        typer.Option(help="Output directory for the wheel. Defaults to working directory"),
    ] = None,
    build_installer: Annotated[
        PythonInstallers,
        typer.Option(
            help="Which installer tool should be used to provide the isolated 'build' venv"
        ),
    ] = PythonInstallers.PIP,
    python: Annotated[
        str,
        typer.Option(help="Python executable to use"),
    ] = sys.executable,
    unsupported_constraints_behaviour: Annotated[
        UnsupportedConstraintsBehaviour,
        typer.Option(
            help="Whether to error, warn or ignore unsupported version constraints. "
            "Constraints will be dropped if needed."
        ),
    ] = user_config.unsupported_constraints_behaviour,
    unknown_args: typer.Context = typer.Option(()),
) -> None:
    if not os.environ.get("CI"):
        raise NotOnCIError()

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
        install_external_cmds = external.install_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=True,
        )
    except UnsupportedSpecError as exc:
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
            raise
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
            log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
        install_external_cmds = external.install_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=False,
        )
    build_cmd = [
        python,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        outdir or os.getcwd(),
        "--installer",
        build_installer,
        *unknown_args.args,
    ]
    try:
        # 1. Install external dependencies
        for external_cmd in install_external_cmds:
            subprocess.run(external_cmd.render(), check=True)
        # 2. Build wheel
        with (
            activated_conda_env(package_manager=package_manager)
            if ecosystem == "conda-forge"
            else nullcontext(os.environ) as env
        ):
            if package.is_file():
                with TemporaryDirectory() as tmp:
                    with tarfile.open(package) as tar:
                        tar.extractall(tmp, filter="data")
                        tmp = Path(tmp)
                        if (tmp / "pyproject.toml").is_file():
                            extracted_package = tmp
                        else:
                            extracted_package = next(tmp.glob("*"))
                        subprocess.run([*build_cmd, extracted_package], check=True, env=env)
            else:
                subprocess.run([*build_cmd, package], check=True, env=env)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)  # avoid unnecessary typer pretty traceback
