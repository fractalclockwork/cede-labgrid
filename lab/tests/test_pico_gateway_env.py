"""Offline tests for cede-rp2 (Pico) gateway tooling."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

GLOB_KEYS_PICO = (
    "/dev/serial/by-id/usb-Raspberry_Pi*",
    "/dev/serial/by-id/usb-Arduino*",
    "/dev/ttyACM*",
)


def _patch_glob(monkeypatch: pytest.MonkeyPatch, mod: object, mapping: dict[str, list[str]]) -> None:
    def _fake(pattern: str) -> list[str]:
        got = mapping.get(pattern)
        assert got is not None, f"unexpected glob pattern {pattern!r}"
        return list(got)

    monkeypatch.setattr(mod.glob, "glob", _fake)


@pytest.fixture
def resolve_gateway_pico(repo_root: Path):
    script = repo_root / "lab" / "pi" / "scripts" / "pi_resolve_gateway_pico.py"
    spec = importlib.util.spec_from_file_location("pi_resolve_gateway_pico", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sync_gateway_deps_lists_pico_cede_rp2_scripts(repo_root: Path) -> None:
    body = (repo_root / "lab" / "pi" / "scripts" / "sync_gateway_flash_deps.sh").read_text(encoding="utf-8")
    for name in (
        "pi_flash_pico_mount_lib.sh",
        "pi_flash_pico_auto.sh",
        "pi_resolve_gateway_pico.py",
        "pi_validate_pico_serial.py",
        "pi_flash_pico_uf2.sh",
    ):
        assert name in body, f"sync_gateway_flash_deps.sh should list {name}"


def test_hello_lab_prints_rp2_banner(repo_root: Path) -> None:
    text = (repo_root / "lab" / "pico" / "hello_lab" / "src" / "main.c").read_text(encoding="utf-8")
    assert "stdio_init_all" in text
    assert "CEDE hello_lab rp2 ok" in text


@pytest.mark.parametrize(
    ("mapping", "want"),
    [
        pytest.param(
            {
                "/dev/serial/by-id/usb-Raspberry_Pi*": ["/dev/serial/by-id/usb-Raspberry_Pi_Pico"],
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyACM*": ["/dev/ttyACM0"],
            },
            "/dev/serial/by-id/usb-Raspberry_Pi_Pico",
            id="single_pico_by_id",
        ),
        pytest.param(
            {
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyACM*": ["/dev/ttyACM0"],
            },
            "/dev/ttyACM0",
            id="lone_acm_when_no_arduino",
        ),
    ],
)
def test_resolve_pico_tty_happy_path(
    resolve_gateway_pico,
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[str]],
    want: str,
) -> None:
    for k in GLOB_KEYS_PICO:
        assert k in mapping

    monkeypatch.setattr(resolve_gateway_pico.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(resolve_gateway_pico.os.path, "realpath", lambda p: p)
    _patch_glob(monkeypatch, resolve_gateway_pico, mapping)
    assert resolve_gateway_pico.resolve_pico_tty() == want


def test_resolve_pico_ambiguous_two_pico(resolve_gateway_pico, monkeypatch, capsys) -> None:
    mapping = {
        "/dev/serial/by-id/usb-Raspberry_Pi*": ["/a", "/b"],
        "/dev/serial/by-id/usb-Arduino*": [],
        "/dev/ttyACM*": [],
    }
    monkeypatch.setattr(resolve_gateway_pico.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(resolve_gateway_pico.os.path, "realpath", lambda p: p)
    _patch_glob(monkeypatch, resolve_gateway_pico, mapping)
    assert resolve_gateway_pico.resolve_pico_tty() is None
    assert "ambiguous" in capsys.readouterr().err


def test_resolve_pico_main_check_quiet(resolve_gateway_pico, monkeypatch) -> None:
    mapping = {
        "/dev/serial/by-id/usb-Raspberry_Pi*": ["/solo"],
        "/dev/serial/by-id/usb-Arduino*": [],
        "/dev/ttyACM*": [],
    }
    monkeypatch.setattr(resolve_gateway_pico.glob, "glob", lambda pat: mapping[pat])
    err = io.StringIO()
    monkeypatch.setattr(resolve_gateway_pico.sys, "stderr", err)
    monkeypatch.setattr(resolve_gateway_pico.sys, "stdout", io.StringIO())
    monkeypatch.setattr(resolve_gateway_pico.sys, "argv", ["x", "--check"])
    assert resolve_gateway_pico.main() == 0
    assert err.getvalue() == ""
