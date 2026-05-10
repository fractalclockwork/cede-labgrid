from __future__ import annotations

from pathlib import Path
import importlib.util

import pytest


def _load_attest(repo_root: Path):
    path = repo_root / "lab" / "pi" / "scripts" / "cede_firmware_attest.py"
    spec = importlib.util.spec_from_file_location("cede_firmware_attest", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.pico
def test_attestation_failure_reason_ok(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_lab rp2 ok digest=deadbeef1234 (i2c"
    assert m.attestation_failure_reason(buf, "pico", "deadbeef1234") is None


@pytest.mark.uno
def test_attestation_digest_mismatch(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_lab ok digest=aaaa (i2c"
    assert m.attestation_failure_reason(buf, "uno", "bbbb") is not None


@pytest.mark.pico
def test_attestation_missing_digest(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_lab rp2 ok no digest here"
    assert m.attestation_failure_reason(buf, "pico", "") is not None


@pytest.mark.uno
def test_digest_banner_line_extracts_uno_serial(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"noise\nCEDE hello_lab ok digest=t12345678_abcd1234 (i2c target 0x43)\n"
    assert m.digest_banner_line(buf, "uno") == "CEDE hello_lab ok digest=t12345678_abcd1234 (i2c target 0x43)"


@pytest.mark.uno
def test_attestation_uno_banner_digest_ok(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_lab ok digest=feedface99 (i2c target"
    assert m.attestation_failure_reason(buf, "uno", "feedface99") is None


@pytest.mark.gateway
def test_attestation_gateway_stdout_ok(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_gateway ok digest=abc123deadbeef\n"
    assert m.attestation_failure_reason(buf, "gateway", "abc123deadbeef") is None


@pytest.mark.gateway
def test_digest_banner_line_gateway(repo_root: Path) -> None:
    m = _load_attest(repo_root)
    buf = b"CEDE hello_gateway ok digest=t1_abcd1234\n"
    assert m.digest_banner_line(buf, "gateway") == "CEDE hello_gateway ok digest=t1_abcd1234"


def test_sync_lists_cede_firmware_attest(repo_root: Path) -> None:
    body = (repo_root / "lab" / "pi" / "scripts" / "sync_gateway_flash_deps.sh").read_text(encoding="utf-8")
    assert "cede_firmware_attest.py" in body
    assert "pi_validate_gateway_native.py" in body
