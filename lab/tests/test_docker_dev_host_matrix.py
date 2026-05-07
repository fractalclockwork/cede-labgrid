"""Docker Dev-Host tiers: Intel native subcontainers vs emulated ARM.

**Dev-Host (Tier 0)** runs Docker on the developer machine. On **Intel / x86_64**, the
default toolchain images are **linux/amd64** (see ``docker-compose.platform-amd64.yml``).

**Emulated / remote-style ARM** here means **linux/arm64** images built or run through
Docker’s multi-arch path (QEMU **binfmt** on amd64 hosts). This matches **Raspberry Pi
64-bit gateway** userspace for CI parity—not the physical Pi on the LAN (that stays
``hardware`` / ``pi_gateway``).

Makefile entry points: ``build-images-host``, ``workflow-emulated-arm64``, ``test-emulated-target``.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

TOOLCHAIN_SERVICES = frozenset(
    ("pico-dev", "arduino-dev", "orchestration-dev", "rpi-imager-dev")
)


def _platform_services(repo_root: Path, suffix: str) -> dict:
    path = repo_root / "lab" / "docker" / f"docker-compose.platform-{suffix}.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return (data or {}).get("services") or {}


@pytest.mark.dev_host_intel
def test_intel_dev_host_native_stack_is_linux_amd64(repo_root: Path) -> None:
    """Subcontainers for an Intel Dev-Host: every toolchain service pins linux/amd64."""
    svcs = _platform_services(repo_root, "amd64")
    assert set(svcs.keys()) == TOOLCHAIN_SERVICES
    for name in TOOLCHAIN_SERVICES:
        assert svcs[name].get("platform") == "linux/amd64", name


@pytest.mark.emulated_linux_arm64
def test_emulated_arm64_target_stack_is_linux_arm64(repo_root: Path) -> None:
    """Emulated / Pi-class aarch64 userspace: every toolchain service pins linux/arm64."""
    svcs = _platform_services(repo_root, "arm64")
    assert set(svcs.keys()) == TOOLCHAIN_SERVICES
    for name in TOOLCHAIN_SERVICES:
        assert svcs[name].get("platform") == "linux/arm64", name


def test_platform_overrides_cover_same_services_as_base_compose(repo_root: Path) -> None:
    base = yaml.safe_load(
        (repo_root / "lab/docker/docker-compose.yml").read_text(encoding="utf-8")
    )
    base_services = set((base or {}).get("services") or {})
    assert base_services == TOOLCHAIN_SERVICES

    for suffix in ("amd64", "arm64"):
        ov = yaml.safe_load(
            (
                repo_root / f"lab/docker/docker-compose.platform-{suffix}.yml"
            ).read_text(encoding="utf-8")
        )
        plat_svcs = set((ov or {}).get("services") or {})
        assert plat_svcs == TOOLCHAIN_SERVICES, suffix


@pytest.mark.dev_host_intel
def test_make_print_host_platform_linux_amd64_on_x86_64(repo_root: Path) -> None:
    """On Intel silicon, Makefile HOST_PLATFORM must be linux/amd64 (native Dev-Host tier)."""
    if platform.machine() != "x86_64":
        pytest.skip("requires x86_64 Dev-Host")
    if shutil.which("make") is None:
        pytest.skip("GNU make not installed")
    proc = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-C",
            str(repo_root / "lab/docker"),
            "print-host-platform",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "linux/amd64"


@pytest.mark.emulated_linux_arm64
def test_makefile_wires_emulated_arm64_and_integration_target(repo_root: Path) -> None:
    """Makefile links workflow-emulated-arm64 / test-emulated-target to arm64 compose merge."""
    mf = (repo_root / "lab/docker/Makefile").read_text(encoding="utf-8")
    assert "workflow-emulated-arm64: build-images-arm64" in mf
    assert "test-emulated-target:" in mf
    assert "COMPOSE_ARM64" in mf and "build orchestration-dev" in mf
