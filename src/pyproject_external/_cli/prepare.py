# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Prepare a package for building with [external] metadata
by downloading and patching its most recent sdist.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

import typer

from .._sdist import (
    append_external_metadata,
    apply_patches,
    create_new_sdist,
    download_sdist,
    untar_sdist,
)

log = logging.getLogger(__name__)
app = typer.Typer()


@app.command(help=__doc__)
def prepare(
    package_name: Annotated[
        str,
        typer.Argument(help="PyPI package name to download and patch."),
    ],
    external_metadata_dir: Annotated[
        str,
        typer.Option(
            help="Search this directory to find a '<package_name>.toml' "
            "file that contains an '[external]' table.",
        ),
    ] = "external_metadata",
    patches_dir: Annotated[
        str,
        typer.Option(
            help="Search this directory to find a '<package_name>.py' "
            "script that will run additional patches on the sdist contents.",
        ),
    ] = "patches",
    out_dir: Annotated[
        str,
        typer.Option(help="Directory where the patched sdist will be written to."),
    ] = "sdist",
) -> None:
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        fname_sdist = download_sdist(package_name, tmp)
        fname_pyproject_toml = untar_sdist(fname_sdist, tmp)
        append_external_metadata(
            fname_pyproject_toml,
            package_name,
            patches_dir=external_metadata_dir,
        )
        apply_patches(package_name, fname_pyproject_toml.parent, patches_dir=patches_dir)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        create_new_sdist(fname_sdist, tmp, out_dir or os.getcwd())
