# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs

"""
Utilities to patch sdist tarballs to include `[external]` metadata.
"""

import sys
import tarfile
import urllib.request
import warnings
from pathlib import Path
from subprocess import run

from pypi_json import PyPIJSON


def download_sdist(package_name: str, sdist_dir: str | Path) -> str:
    with PyPIJSON() as client:
        metadata = client.get_metadata(package_name)

    url = None
    for item in metadata.get_wheel_tag_mapping():
        if isinstance(item, list):  # sdist
            assert len(item) == 1 and str(item[0]).endswith("tar.gz")
            url = str(item[0])

    if url is None:
        raise RuntimeError(f"No sdist for package {package_name} found.")

    fname_sdist = url.split("/")[-1]
    urllib.request.urlretrieve(url, sdist_dir / fname_sdist)
    return fname_sdist


_toml_setuptools = """[build-system]
requires = ["setuptools", "versioninfo"]
build-backend = "setuptools.build_meta"
"""


def untar_sdist(fname_sdist: str, sdist_dir: str | Path) -> Path:
    tar = tarfile.open(sdist_dir / fname_sdist)

    for info in tar.getmembers():
        name = info.name
        if "/" in name and name.split("/")[1] == "pyproject.toml":
            break

    tar.extractall(path=sdist_dir)

    pyproject_toml = sdist_dir / info.name.split("/")[0] / "pyproject.toml"
    if not (pyproject_toml).exists():
        warnings.warn(f"{fname_sdist} does not contain a pyproject.toml file", UserWarning)
        with open(pyproject_toml, "w") as f:
            f.write(_toml_setuptools)

    return pyproject_toml


def append_external_metadata(
    fname_sdist: str,
    package_name: str,
    patches_dir: str | Path = "external_metadata",
) -> None:
    pyproject_toml = Path(fname_sdist)
    pyproject_toml_contents = pyproject_toml.read_text()
    external_metadata = Path(patches_dir, f"{package_name}.toml").read_text()
    if external_metadata not in pyproject_toml_contents:
        pyproject_toml.write_text(pyproject_toml_contents + "\n" + external_metadata)


def apply_patches(
    package_name: str,
    unpacked_dir: str | Path,
    patches_dir: str | Path = "patches",
) -> None:
    if (script := Path(patches_dir, f"{package_name}.py")).is_file():
        run([sys.executable, script, unpacked_dir], check=True)


def create_new_sdist(
    sdist_name: str, sdist_dir: str | Path, amended_dir: str | Path = "."
) -> None:
    dirname = sdist_name.split(".tar.gz")[0]
    with tarfile.open(Path(amended_dir, sdist_name.lower().replace("_", "-")), "w:gz") as tar:
        tar.add(sdist_dir / dirname, arcname=dirname)
