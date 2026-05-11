"""LabGrid pytest plugin configuration for CEDE hardware tests.

This conftest is loaded automatically by pytest when --lg-env is passed.
It registers CEDE custom markers and re-exports the standard labgrid
fixtures (env, target, strategy) so tests can use them directly.

Usage:
    pytest --lg-env env/remote.yaml lab/tests/test_pico_labgrid.py
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "labgrid: LabGrid-managed hardware test (needs coordinator + exporter)",
    )
