# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import shutil
import subprocess
import sys
from itertools import chain

import pytest

from pyproject_external import Mapping


@pytest.fixture
def mapping_instance():
    # Create a minimal Mapping instance for testing the method
    # The actual data doesn't matter much for _add_version_to_spec
    return Mapping({"mappings": [], "package_managers": []})


@pytest.mark.parametrize(
    "dep_url,expected",
    (
        ("dep:generic/llvm@20", "llvm==20"),
        ("dep:generic/llvm@>20", "llvm>20"),
        ("dep:generic/llvm@<22,>=21", "llvm<22,>=21"),
    ),
)
def test_build_command(dep_url, expected):
    mapping: Mapping = Mapping.from_default("conda-forge")
    mgr = mapping.get_package_manager("conda")
    for specs in mapping.iter_specs_by_id(dep_url):
        assert expected in chain(*[mgr.render_spec(spec) for spec in specs])


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
