from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "hardware: needs attached Pico/Uno/Pi")
    config.addinivalue_line("markers", "uno: Uno hello_lab / digest facet")
    config.addinivalue_line("markers", "pico: Pico hello_lab / digest facet")
    config.addinivalue_line("markers", "gateway: Raspberry Pi gateway native hello_gateway / digest facet")
    config.addinivalue_line("markers", "pi_gateway: must run on Raspberry Pi")
    config.addinivalue_line(
        "markers",
        "dev_host_intel: Dev-Host on x86_64 — native Docker stack is linux/amd64 (compose platform-amd64)",
    )
    config.addinivalue_line(
        "markers",
        "emulated_linux_arm64: linux/arm64 OCI targets on Intel (QEMU/binfmt); Pi-gateway–class parity in containers",
    )


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def lab_config_path(repo_root: Path) -> Path:
    env = os.environ.get("CEDE_LAB_CONFIG")
    if env:
        return Path(env)
    override = repo_root / "lab" / "config" / "lab.yaml"
    if override.exists():
        return override
    return repo_root / "lab" / "config" / "lab.example.yaml"
