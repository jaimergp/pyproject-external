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
from enum import Enum
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
from ._utils import _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()


class _BuildInstallers(str, Enum):
    pip = "pip"
    uv = "uv"


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
        _BuildInstallers,
        typer.Option(
            help="Which installer tool should be used to provide the isolated 'build' venv"
        ),
    ] = _BuildInstallers.pip,
    unknown_args: typer.Context = typer.Option(()),
) -> None:
    if not os.environ.get("CI"):
        raise RuntimeError("This tool can only be used in CI environments. Set CI=1 to override.")

    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    package_name = pyproject.get("project", {}).get("name") or package.name
    if package_name.endswith(".tar.gz"):
        package_name = package_name[: -len(".tar.gz")]
    external = External.from_pyproject_data(pyproject)
    external.validate()

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)

    install_external_cmd = external.install_command(ecosystem, package_manager=package_manager)
    build_cmd = [
        sys.executable,
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
        subprocess.run(install_external_cmd, check=True)
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
                        extracted_package = next(tmp.glob(f"{package_name}*"))
                        subprocess.run([*build_cmd, extracted_package], check=True, env=env)
            else:
                subprocess.run([*build_cmd, package], check=True, env=env)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)  # avoid unnecessary typer pretty traceback
