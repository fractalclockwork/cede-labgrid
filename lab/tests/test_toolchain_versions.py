"""Ensure lab/docker/TOOLCHAIN_VERSIONS pins match Dockerfile defaults (single source of truth)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _parse_toolchain_versions(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _dockerfile_arg(dockerfile: Path, name: str) -> str | None:
    text = dockerfile.read_text(encoding="utf-8")
    m = re.search(rf"^ARG\s+{re.escape(name)}=(\S+)", text, re.MULTILINE)
    return m.group(1) if m else None


def test_toolchain_versions_file_exists(repo_root: Path) -> None:
    p = repo_root / "lab/docker/TOOLCHAIN_VERSIONS"
    assert p.is_file(), f"missing {p}"


def test_pico_dockerfile_arg_matches_toolchain_versions(repo_root: Path) -> None:
    tv = _parse_toolchain_versions(repo_root / "lab/docker/TOOLCHAIN_VERSIONS")
    df = repo_root / "lab/docker/pico-dev/Dockerfile"
    assert _dockerfile_arg(df, "PICO_SDK_VERSION") == tv.get("PICO_SDK_VERSION")


def test_arduino_dockerfile_arg_matches_toolchain_versions(repo_root: Path) -> None:
    tv = _parse_toolchain_versions(repo_root / "lab/docker/TOOLCHAIN_VERSIONS")
    df = repo_root / "lab/docker/arduino-dev/Dockerfile"
    assert _dockerfile_arg(df, "ARDUINO_CLI_VERSION") == tv.get("ARDUINO_CLI_VERSION")


def test_compose_defines_expected_services(repo_root: Path) -> None:
    try:
        import yaml
    except ImportError as e:
        pytest.skip(f"PyYAML: {e}")
    dc = repo_root / "lab/docker/docker-compose.yml"
    data = yaml.safe_load(dc.read_text(encoding="utf-8"))
    services = (data or {}).get("services") or {}
    for name in ("pico-dev", "arduino-dev", "orchestration-dev", "rpi-imager-dev"):
        assert name in services, f"docker-compose missing service: {name}"
