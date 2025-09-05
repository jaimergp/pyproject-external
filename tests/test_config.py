# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

import re
from textwrap import dedent

import pytest

from pyproject_external._config import Config
from pyproject_external._constants import APP_CONFIG_FILENAME


def test_config_empty():
    Config.load_user_config()


def test_config_populated(monkeypatch, tmp_path):
    monkeypatch.setenv("PYPROJECT_EXTERNAL_CONFIG_DIR", str(tmp_path))
    (tmp_path / APP_CONFIG_FILENAME).write_text(
        dedent(
            """
            preferred_package_manager = "conda"
            """
        )
    )
    config = Config.load_user_config()
    assert config.preferred_package_manager == "conda"


def test_config_error(monkeypatch, tmp_path):
    monkeypatch.setenv("PYPROJECT_EXTERNAL_CONFIG_DIR", str(tmp_path))
    (tmp_path / APP_CONFIG_FILENAME).write_text(
        dedent(
            """
            unsupported_constraints_behaviour = "unknown"
            """
        )
    )
    with pytest.raises(ValueError, match=re.escape(str(tmp_path))):
        Config.load_user_config()
