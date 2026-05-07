"""Tests for Docker target workflow (Makefile aliases and printed plan)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_workflow_targets_delegate_to_build_targets(repo_root: Path) -> None:
    mf = (repo_root / "lab/docker/Makefile").read_text(encoding="utf-8")
    assert "workflow-docker-all: build-images-all-arch" in mf
    assert "workflow-docker-host: build-images-host" in mf
    assert "workflow-emulated-arm64: build-images-arm64" in mf
    assert "workflow-emulated-amd64: build-images-amd64" in mf
    assert "workflow-emulated-targets: build-images-cross" in mf
    assert "test-emulated-target:" in mf
    assert "emulation-envs-standup-test:" in mf and "EMULATION_ORCH_PYTEST" in mf
    assert "docker-compose.platform-arm64.yml" in mf


def test_root_makefile_wires_docker_workflow(repo_root: Path) -> None:
    root_mf = (repo_root / "Makefile").read_text(encoding="utf-8")
    assert "docker-workflow:" in root_mf
    assert 'workflow-docker-all' in root_mf
    assert "docker-test-arch:" in root_mf and "docker-workflow" in root_mf
    assert "test-emulated-docker:" in root_mf and "test-emulated-target" in root_mf
    assert "emulation-environments-test:" in root_mf and "emulation-envs-standup-test" in root_mf


def test_github_manual_workflow_lists_docker_workflow(repo_root: Path) -> None:
    wf = repo_root / ".github/workflows/docker-target-workflow.yml"
    assert wf.is_file()
    text = wf.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text
    assert "make docker-workflow" in text


def test_workflow_docker_print_matches_host_line(repo_root: Path) -> None:
    if shutil.which("make") is None:
        pytest.skip("GNU make not installed")
    common = [
        "make",
        "--no-print-directory",
        "-C",
        str(repo_root / "lab/docker"),
    ]
    host = subprocess.run(
        common + ["print-host-platform"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert host.returncode == 0, host.stderr
    plat = host.stdout.strip()

    printed = subprocess.run(
        common + ["workflow-docker-print"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert printed.returncode == 0, printed.stderr
    out = printed.stdout
    # Makefile uses U+2014 em dash in Step 1 label
    step1 = f"Step 1 \u2014 host (native):     {plat}"
    assert step1 in out, out
    assert "Step 2" in out and "Step 3" in out
