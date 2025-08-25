# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import shutil
import subprocess
import sys

import pytest


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
