# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import shutil
import subprocess
import sys
from textwrap import dedent

import pytest

from pyproject_external._cli.prepare import prepare
from pyproject_external._cli.show import _OutputChoices, show


@pytest.mark.skipif(not shutil.which("conda"), reason="conda not available")
def test_run_command_show(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[external]\nhost_requires = ["dep:generic/llvm@<20"]'
    )
    subprocess.run(
        f'set -x; eval "$({sys.executable} -m pyproject_external show --output=command '
        f'{tmp_path} --package-manager=conda)"',
        shell=True,
        check=True,
    )


def test_show_integration(tmp_path):
    (tmp_path / "cryptography.toml").write_text(
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
            "dep:generic/libffi@3.5.2",
            ]
            """
        ).lstrip()
    )
    prepare(
        "cryptography",
        external_metadata_dir=tmp_path,
        out_dir=tmp_path,
    )
    for output in _OutputChoices:
        show(next(tmp_path.glob("*.tar.gz")), output=output, package_manager="conda")
