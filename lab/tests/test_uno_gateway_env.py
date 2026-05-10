"""Offline tests for Uno-on-gateway tooling (resolver, lab serial config, scaffolding)."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest
import yaml

GLOB_KEYS = (
    "/dev/serial/by-id/usb-Arduino*",
    "/dev/ttyUSB*",
    "/dev/serial/by-id/usb-Raspberry_Pi*",
    "/dev/ttyACM*",
)


def _patch_glob(monkeypatch: pytest.MonkeyPatch, mod: object, mapping: dict[str, list[str]]) -> None:
    def _fake(pattern: str) -> list[str]:
        got = mapping.get(pattern)
        assert got is not None, f"unexpected glob pattern {pattern!r}"
        return list(got)

    monkeypatch.setattr(mod.glob, "glob", _fake)


@pytest.fixture
def resolve_gateway_uno(repo_root: Path):
    script = repo_root / "lab" / "pi" / "scripts" / "pi_resolve_gateway_uno.py"
    spec = importlib.util.spec_from_file_location("pi_resolve_gateway_uno", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def discover_serial_mod(repo_root: Path):
    script = repo_root / "lab" / "pi" / "scripts" / "discover_serial.py"
    spec = importlib.util.spec_from_file_location("discover_serial", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_lab_example_yaml_has_uno_serial_section(lab_config_path: Path) -> None:
    with open(lab_config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    uno = cfg.get("serial", {}).get("devices", {}).get("uno")
    assert uno is not None, "lab config must declare serial.devices.uno"
    assert "by_id_glob" in uno and uno["by_id_glob"]
    fb = uno.get("fallback_globs") or []
    assert isinstance(fb, list) and fb, "uno should declare fallback globs for clones"


def test_uno_hello_lab_sketch_has_serial_banner(repo_root: Path) -> None:
    path = repo_root / "lab" / "uno" / "hello_lab" / "hello_lab.ino"
    text = path.read_text(encoding="utf-8")
    assert "Serial.begin(115200)" in text
    assert "CEDE hello_lab ok" in text
    assert "digest=" in text
    assert "CEDE i2c uno_to_pico ok" in text


def test_sync_gateway_deps_includes_uno_scripts(repo_root: Path) -> None:
    script = repo_root / "lab" / "pi" / "scripts" / "sync_gateway_flash_deps.sh"
    body = script.read_text(encoding="utf-8")
    for name in (
        "pi_resolve_gateway_uno.py",
        "pi_validate_uno_serial.py",
        "cede_firmware_attest.py",
        "pi_flash_uno_avrdude.sh",
        "lab_i2c_matrix_validate.py",
    ):
        assert name in body, f"sync_gateway_flash_deps.sh should list {name}"


@pytest.mark.parametrize(
    ("mapping", "want"),
    [
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": ["/dev/serial/by-id/usb-Arduino_Blah"],
                "/dev/ttyUSB*": ["/bogus"],
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/ttyACM*": ["/bogus2"],
            },
            "/dev/serial/by-id/usb-Arduino_Blah",
            id="arduino_by_id_wins_before_other_globs_are_considered",
        ),
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyUSB*": ["/dev/ttyUSB0"],
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/ttyACM*": ["/dev/ttyACM0"],
            },
            "/dev/ttyUSB0",
            id="single_tty_usb_used_when_no_arduino_by_id",
        ),
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyUSB*": [],
                "/dev/serial/by-id/usb-Raspberry_Pi*": ["/dev/serial/by-id/usb-Raspberry_Pi_RP2_rp2040-if00"],
                "/dev/ttyACM*": ["/dev/ttyACM0"],
            },
            "/dev/ttyACM0",
            id="solo_acm_after_droping_mapped_pico",
        ),
    ],
)
def test_resolve_uno_tty_happy_path(
    resolve_gateway_uno,
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[str]],
    want: str,
) -> None:
    for k in GLOB_KEYS:
        assert k in mapping, f"mapping must declare {k}"

    def fake_real(path: str) -> str:
        if path.startswith("/dev/serial/by-id/usb-Raspberry_Pi"):
            return "/dev/ttyACM9"
        if path.startswith("/dev/ttyACM"):
            return path
        return path

    def fake_exists(_path: str) -> bool:
        return True

    _patch_glob(monkeypatch, resolve_gateway_uno, mapping)
    monkeypatch.setattr(resolve_gateway_uno.os.path, "realpath", lambda p: fake_real(p))
    monkeypatch.setattr(resolve_gateway_uno.os.path, "exists", lambda p: fake_exists(p))

    assert resolve_gateway_uno.resolve_uno_tty() == want


@pytest.mark.parametrize(
    "mapping",
    [
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": ["/dev/a", "/dev/b"],
                "/dev/ttyUSB*": [],
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/ttyACM*": [],
            },
            id="two_arduino_symlinks",
        ),
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyUSB*": ["/dev/ttyUSB0", "/dev/ttyUSB1"],
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/ttyACM*": [],
            },
            id="two_ttyusb",
        ),
        pytest.param(
            {
                "/dev/serial/by-id/usb-Arduino*": [],
                "/dev/ttyUSB*": [],
                "/dev/serial/by-id/usb-Raspberry_Pi*": [],
                "/dev/ttyACM*": ["/dev/ttyACM0", "/dev/ttyACM1"],
            },
            id="two_acm_without_arduino_ttyusb_or_pico_id",
        ),
    ],
)
def test_resolve_uno_tty_refuses_ambiguous(
    resolve_gateway_uno,
    monkeypatch: pytest.MonkeyPatch,
    mapping: dict[str, list[str]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    for k in GLOB_KEYS:
        assert k in mapping
    monkeypatch.setattr(resolve_gateway_uno.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(resolve_gateway_uno.os.path, "realpath", lambda p: p)
    _patch_glob(monkeypatch, resolve_gateway_uno, mapping)
    assert resolve_gateway_uno.resolve_uno_tty() is None
    err = capsys.readouterr().err
    assert "ambiguous" in err


def test_resolve_uno_none_when_empty(resolve_gateway_uno, monkeypatch) -> None:
    emp = {
        "/dev/serial/by-id/usb-Arduino*": [],
        "/dev/ttyUSB*": [],
        "/dev/serial/by-id/usb-Raspberry_Pi*": [],
        "/dev/ttyACM*": [],
    }
    _patch_glob(monkeypatch, resolve_gateway_uno, emp)
    assert resolve_gateway_uno.resolve_uno_tty() is None


def test_discover_serial_uno_via_yaml_globs(discover_serial_mod, lab_config_path: Path, monkeypatch) -> None:
    with open(lab_config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    hit = Path("/mocklab/uno/from/yaml/by_id")

    def fake_glob(pattern: str) -> list[str]:
        uno_glob = cfg["serial"]["devices"]["uno"]["by_id_glob"]
        if pattern == uno_glob:
            return [str(hit)]
        return []

    monkeypatch.setattr(discover_serial_mod.glob, "glob", fake_glob)
    tty, tried = discover_serial_mod.resolve_device("uno", cfg)
    assert tty == str(hit)
    assert tried and cfg["serial"]["devices"]["uno"]["by_id_glob"] in tried


def test_resolve_main_check_stdout_quiet(resolve_gateway_uno, monkeypatch) -> None:
    mapping = {
        "/dev/serial/by-id/usb-Arduino*": ["/solo"],
        "/dev/ttyUSB*": [],
        "/dev/serial/by-id/usb-Raspberry_Pi*": [],
        "/dev/ttyACM*": [],
    }
    monkeypatch.setattr(resolve_gateway_uno.glob, "glob", lambda pat: mapping[pat])

    err = io.StringIO()
    monkeypatch.setattr(resolve_gateway_uno.sys, "stderr", err)
    monkeypatch.setattr(resolve_gateway_uno.sys, "stdout", io.StringIO())
    monkeypatch.setattr(resolve_gateway_uno.sys, "argv", ["pi_resolve_gateway_uno", "--check"])
    assert resolve_gateway_uno.main() == 0
    assert err.getvalue() == ""

