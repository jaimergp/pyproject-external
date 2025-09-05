# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from pyproject_external._cli.build import app as build
from pyproject_external._cli.install import app as install
from pyproject_external._cli.prepare import prepare
from pyproject_external._cli.show import _OutputChoices, show
from pyproject_external._constants import UnsupportedConstraintsBehaviour
from pyproject_external._exceptions import UnsupportedSpecError


@pytest.mark.skipif(not shutil.which("micromamba"), reason="micromamba not available")
def test_run_command_show(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[external]\nhost_requires = ["dep:generic/llvm@<20"]'
    )
    subprocess.run(
        f'set -x; eval "$({sys.executable} -m pyproject_external show --output=command '
        f'{tmp_path} --package-manager=micromamba)"',
        shell=True,
        check=True,
    )


def _prepare_cryptography(tmpdir, version="") -> Path:
    (tmpdir / "cryptography.toml").write_text(
        dedent(
            """
            [external]
            build-requires = [
            "dep:virtual/compiler/c",
            "dep:virtual/compiler/rust",
            "dep:generic/pkg-config",
            ]
            host-requires = [
            "dep:generic/openssl@>=3",
            "dep:generic/libffi@3.4.6",
            ]
            """
        ).lstrip()
    )
    prepare(
        "cryptography",
        version=version,
        external_metadata_dir=tmpdir,
        out_dir=tmpdir,
    )
    return next(tmpdir.glob("*.tar.gz"))


@pytest.fixture(scope="session")
def prepared_cryptography(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("pyproject-external-prepare")
    return _prepare_cryptography(tmp, "45.0.7")


def test_prepare(tmp_path) -> Path:
    assert _prepare_cryptography(tmp_path, "")


def test_show(prepared_cryptography):
    for output in _OutputChoices:
        show(prepared_cryptography, output=output, package_manager="micromamba")


def test_show_unsupported_constraints_error(prepared_cryptography):
    with pytest.raises(UnsupportedSpecError):
        show(
            prepared_cryptography,
            output=_OutputChoices.MAPPED_LIST,
            package_manager="pacman",
            unsupported_constraints_behaviour=UnsupportedConstraintsBehaviour.ERROR,
        )


def test_show_unsupported_constraints_warning(prepared_cryptography, caplog):
    caplog.set_level(logging.WARNING)
    show(
        prepared_cryptography,
        output=_OutputChoices.MAPPED_LIST,
        package_manager="pacman",
        unsupported_constraints_behaviour=UnsupportedConstraintsBehaviour.WARN,
    )
    assert "UnsupportedSpecError" in caplog.text


def test_show_unsupported_constraints_ignore(prepared_cryptography):
    show(
        prepared_cryptography,
        output=_OutputChoices.MAPPED_LIST,
        package_manager="pacman",
        unsupported_constraints_behaviour=UnsupportedConstraintsBehaviour.IGNORE,
    )


@pytest.fixture
def conda_python_env(tmp_path, monkeypatch):
    subprocess.run(
        [
            "micromamba",
            "create",
            "--yes",
            "--prefix",
            str(tmp_path / "env"),
            "--override-channels",
            "--channel=conda-forge",
            "python",
            "pip",
            "python-build",
        ],
        check=True,
    )
    monkeypatch.setenv("CONDA_PREFIX", str(tmp_path / "env"))
    yield tmp_path / "env"


@pytest.mark.skipif(not shutil.which("micromamba"), reason="micromamba not available")
@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="SSL errors on Windows, needs debugging"
)
def test_install(prepared_cryptography, conda_python_env, monkeypatch):
    python = (
        conda_python_env / "python.exe"
        if sys.platform.startswith("win")
        else conda_python_env / "bin" / "python"
    )
    monkeypatch.setenv("CI", "1")
    if sys.platform.startswith("win"):
        monkeypatch.setenv("OPENSSL_DIR", str(conda_python_env))
    with pytest.raises(SystemExit, check=lambda exc: exc.code == 0):
        install(
            [
                str(prepared_cryptography),
                "--package-manager",
                "micromamba",
                "--python",
                str(python),
            ]
        )


@pytest.mark.skipif(not shutil.which("micromamba"), reason="micromamba not available")
@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="SSL errors on Windows, needs debugging"
)
def test_build(prepared_cryptography, conda_python_env, tmp_path, monkeypatch):
    python = (
        conda_python_env / "python.exe"
        if sys.platform.startswith("win")
        else conda_python_env / "bin" / "python"
    )
    monkeypatch.setenv("CI", "1")
    if sys.platform.startswith("win"):
        monkeypatch.setenv("OPENSSL_DIR", str(conda_python_env))
    with pytest.raises(SystemExit, check=lambda exc: exc.code == 0):
        build(
            [
                str(prepared_cryptography),
                "--package-manager",
                "micromamba",
                "--python",
                str(python),
                "--outdir",
                str(tmp_path),
            ]
        )
