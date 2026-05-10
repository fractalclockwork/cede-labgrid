"""Tests for FIRMWARE_DIGEST / CEDE_REPO_DIGEST Makefile logic and lab_i2c_matrix_validate._firmware_digest."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_lab_i2c_matrix(repo_root: Path, *, modname: str = "_cede_lab_i2c_matrix_validate_test") -> ModuleType:
    path = repo_root / "lab" / "pi" / "scripts" / "lab_i2c_matrix_validate.py"
    spec = importlib.util.spec_from_file_location(modname, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_make_print_firmware_digest_digest_override(repo_root: Path) -> None:
    proc = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-C",
            str(repo_root),
            "print-firmware-digest",
            "DIGEST=feedface1234",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "feedface1234"


def test_make_print_firmware_digest_equals_git_when_digest_unset(repo_root: Path) -> None:
    git = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if git.returncode != 0:
        pytest.skip("not a git checkout")
    want = (git.stdout or "").strip()
    assert len(want) >= 4
    proc = subprocess.run(
        ["make", "--no-print-directory", "-C", str(repo_root), "print-firmware-digest"],
        check=True,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "DIGEST"},
    )
    assert proc.stdout.strip() == want


def test_make_print_firmware_digest_whitespace_digest_falls_back_to_git(repo_root: Path) -> None:
    git = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if git.returncode != 0:
        pytest.skip("not a git checkout")
    want = (git.stdout or "").strip()
    proc = subprocess.run(
        ["make", "--no-print-directory", "-C", str(repo_root), "print-firmware-digest", "DIGEST=   "],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == want


def test_make_print_cede_repo_digest_matches_git(repo_root: Path) -> None:
    git = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if git.returncode != 0:
        pytest.skip("not a git checkout")
    want = (git.stdout or "").strip()
    proc = subprocess.run(
        ["make", "--no-print-directory", "-C", str(repo_root), "print-cede-repo-digest"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == want


def test_firmware_digest_env_overrides_git(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEDE_EXPECT_DIGEST", "envdigest99")
    modname = "_cede_fw_digest_env"
    mod = _load_lab_i2c_matrix(repo_root, modname=modname)
    try:
        assert mod._firmware_digest(repo_root) == "envdigest99"
    finally:
        sys.modules.pop(modname, None)


def test_firmware_digest_git_when_env_empty(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CEDE_EXPECT_DIGEST", raising=False)
    git = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if git.returncode != 0:
        pytest.skip("not a git checkout")
    modname = "_cede_fw_digest_git"
    mod = _load_lab_i2c_matrix(repo_root, modname=modname)
    try:
        assert mod._firmware_digest(repo_root) == (git.stdout or "").strip()
    finally:
        sys.modules.pop(modname, None)


def test_firmware_digest_empty_when_no_git_no_env(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv("CEDE_EXPECT_DIGEST", raising=False)
    fake = tmp_path / "not-a-git-repo"
    fake.mkdir()
    modname = "_cede_fw_digest_nogit"
    mod = _load_lab_i2c_matrix(repo_root, modname=modname)
    try:
        assert mod._firmware_digest(fake) == ""
    finally:
        sys.modules.pop(modname, None)
