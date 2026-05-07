"""Sanity checks for lab/docker/Makefile platform targets (no Docker daemon required)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


def test_print_host_platform_emits_linux_triple(repo_root: Path) -> None:
    if shutil.which("make") is None:
        pytest.skip("GNU make not installed (e.g. minimal orchestration-dev image)")
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
    line = proc.stdout.strip()
    assert re.match(r"^linux/(amd64|arm64|[a-z0-9_/-]+)$", line), line


def test_makefile_documents_platform_matrix(repo_root: Path) -> None:
    mf = (repo_root / "lab/docker/Makefile").read_text(encoding="utf-8")
    assert "build-images-host" in mf
    assert "build-images-all-arch" in mf
    assert "workflow-docker-all" in mf and "workflow-emulated-arm64" in mf
    assert "linux/arm64" in mf and "CROSS_PLATFORMS" in mf
    assert (repo_root / "lab/docker/docker-compose.platform-amd64.yml").is_file()
    assert (repo_root / "lab/docker/docker-compose.platform-arm64.yml").is_file()
