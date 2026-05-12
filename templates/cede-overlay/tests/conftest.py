"""CEDE hardware test fixtures for {{APP_NAME}}.

These tests require:
  - labgrid coordinator + exporter running
  - cede_labgrid Python package installed (pip install -e <cede-labgrid-repo>)
  - Firmware built (make build or make docker-build)
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "labgrid: LabGrid-managed hardware test")
