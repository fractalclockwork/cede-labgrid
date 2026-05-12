"""Tests for cede_emit_run_record JSON written under lab/tests/results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_cede_emit_run_record_writes_json(repo_root: Path, tmp_path: Path) -> None:
    script = repo_root / "lab" / "pi" / "scripts" / "cede_emit_run_record.py"
    out_rel = "lab/tests/results"
    cfg_path = _minimal_lab_yaml(tmp_path, out_rel)
    env = os.environ.copy()
    env["CEDE_LAB_CONFIG"] = str(cfg_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(tmp_path),
            "--target",
            "pico",
            "--tty",
            "/dev/ttyACM0",
            "--digest",
            "abc123def456",
            "--gateway",
            "pi@cede-pi.local",
            "--application-id",
            "i2c_hello",
            "--transport-path",
            "usb_serial",
            "--exit-status",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    written = Path((proc.stdout or "").strip())
    assert written.is_file()
    with open(written, encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == 1
    assert data["target"] == "pico"
    assert data["digest"] == "abc123def456"
    assert data["tty"] == "/dev/ttyACM0"
    assert data["gateway"] == "pi@cede-pi.local"
    assert data["exit_status"] == 0
    assert "utc_timestamp" in data
    assert data["application_id"] == "i2c_hello"
    assert data["transport_path"] == "usb_serial"


def _minimal_lab_yaml(tmp_path: Path, test_results_dir: str) -> Path:
    """Minimal valid lab yaml fragment with paths.test_results_dir under tmp_path."""
    import yaml

    cfg_path = tmp_path / "lab.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    # Paths relative to tmp_path as synthetic repo root for this test.
    cfg = {
        "schema_version": 1,
        "hosts": {
            "dev_host": {"role": "dev-host", "repo_root": "."},
            "pi": {"role": "raspberry-pi-gateway", "ssh_host": "x", "ssh_user": "pi", "repo_root": "."},
        },
        "serial": {
            "defaults": {"baud": 115200, "newline": "\n", "timeout_s": 2.0},
            "devices": {"uno": {"fallback_globs": ["/dev/ttyUSB0"]}},
        },
        "paths": {
            "pico_build": "lab/pico/hello_lab/build",
            "pico_uf2_glob": "lab/pico/hello_lab/build/*.uf2",
            "uno_build": "lab/uno/hello_lab/build",
            "uno_hex_glob": "lab/uno/hello_lab/build/*.hex",
            "logs_dir": "lab/pi/logs",
            "test_results_dir": test_results_dir,
        },
        "i2c_matrix": {
            "bus_hz": 100000,
            "probe_address": 66,
            "pairs": [
                {
                    "initiator": "rpi",
                    "target": "uno",
                    "status": "enabled",
                    "linux_bus": 1,
                    "probe_address": 67,
                    "validation": {
                        "mode": "rpi_master_i2cdev_read",
                        "controller": "rpi",
                        "reg": 0,
                        "expect_byte": 206,
                    },
                }
            ],
        },
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    return cfg_path
