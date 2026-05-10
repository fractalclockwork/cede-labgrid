#!/usr/bin/env python3
"""Run I2C matrix checks from lab.yaml (single bring-up path).

Reads i2c_matrix.pairs with status: enabled and pair.validation (controller + mode).
- rpi_master_i2cdev_read: SSH to gateway, sudo i2cget on linux_bus, probe_address, reg; optional USB serial
  attestation on the target MCU afterward.

Run from dev-host: uv run python lab/pi/scripts/lab_i2c_matrix_validate.py --gateway pi@cede-pi.local
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _default_config_path(repo: Path) -> Path:
    env = os.environ.get("CEDE_LAB_CONFIG")
    if env:
        return Path(env)
    override = repo / "lab" / "config" / "lab.yaml"
    if override.is_file():
        return override
    return repo / "lab" / "config" / "lab.example.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ssh(gateway: str, remote_cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", gateway, remote_cmd],
        check=False,
        capture_output=True,
        text=True,
    )


def _shell_quote(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "/._-=:@+" for c in s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _remote_python(gateway: str, gateway_repo: str, script: str, args: list[str]) -> int:
    inner = " ".join(_shell_quote(a) for a in args)
    rcmd = f"bash -lc 'cd {gateway_repo} && python3 lab/pi/scripts/{script} {inner}'"
    p = _ssh(gateway, rcmd)
    if p.stdout:
        print(p.stdout, end="" if p.stdout.endswith("\n") else "\n")
    if p.stderr:
        print(p.stderr, end="", file=sys.stderr)
    return int(p.returncode)


def _firmware_digest(repo: Path) -> str:
    env = (os.environ.get("CEDE_EXPECT_DIGEST") or "").strip()
    if env:
        return env
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if p.returncode == 0:
            return (p.stdout or "").strip()
    except OSError:
        pass
    return ""


def run_serial_banner_on_target(
    gateway: str,
    gateway_repo: str,
    target: str,
    firmware_digest: str,
    dry_run: bool,
) -> int:
    """USB serial attestation for rpi→pico / rpi→uno rows (after i2cget)."""
    if target not in ("pico", "uno"):
        return 0
    if dry_run:
        print(f"dry-run: serial hello_lab banner check for target={target}")
        return 0
    script = "pi_validate_pico_serial.py" if target == "pico" else "pi_validate_uno_serial.py"
    resolve = "pi_resolve_gateway_pico.py --wait 5" if target == "pico" else "pi_resolve_gateway_uno.py"
    port_cmd = f"bash -lc 'cd {gateway_repo} && python3 lab/pi/scripts/{resolve}'"
    pr = _ssh(gateway, port_cmd)
    if pr.returncode != 0:
        print(pr.stderr, file=sys.stderr)
        return pr.returncode
    port = (pr.stdout or "").strip()
    if not port:
        print("error: empty serial port from resolver", file=sys.stderr)
        return 1
    wait = "8" if target == "uno" else "5"
    args: list[str] = [port, "--wait", wait]
    if firmware_digest:
        args.extend(["--digest", firmware_digest])
    return _remote_python(gateway, gateway_repo, script, args)


def _parse_i2cget_byte(stdout: str) -> int | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("0x"):
            try:
                return int(line, 16)
            except ValueError:
                continue
    return None


def run_pair_rpi(
    gateway: str,
    gateway_repo: str,
    pair: dict[str, Any],
    firmware_digest: str,
    dry_run: bool,
) -> int:
    v = pair["validation"]
    if v["controller"] != "rpi" or pair["initiator"] != "rpi":
        print(f"error: rpi_master_i2cdev_read expects initiator/controller rpi, got {pair!r}", file=sys.stderr)
        return 1
    bus = v.get("linux_bus", pair.get("linux_bus"))
    if bus is None:
        print(f"error: missing linux_bus for pair {pair['initiator']}->{pair['target']}", file=sys.stderr)
        return 1
    addr = pair["probe_address"]
    reg = int(v.get("reg", 0))
    expect = int(v.get("expect_byte", 0xCE))
    cmd = f"sudo i2cget -y {int(bus)} {addr} {reg} b"
    if dry_run:
        print(f"dry-run: ssh {gateway} {cmd}")
        return 0
    p = _ssh(gateway, cmd)
    if p.stdout:
        print(p.stdout, end="")
    if p.returncode != 0:
        print(p.stderr, file=sys.stderr)
        return p.returncode
    got = _parse_i2cget_byte(p.stdout or "")
    if got is None:
        print(f"error: could not parse i2cget output: {p.stdout!r}", file=sys.stderr)
        return 1
    if got != expect:
        print(f"error: expected reg[{reg}] == 0x{expect:02x}, got 0x{got:02x}", file=sys.stderr)
        return 1
    print(f"ok: {pair['initiator']}->{pair['target']} (rpi i2cdev reg{reg} == 0x{got:02x})")
    tgt = pair.get("target")
    if isinstance(tgt, str) and tgt in ("pico", "uno"):
        rc2 = run_serial_banner_on_target(gateway, gateway_repo, tgt, firmware_digest, dry_run)
        if rc2 != 0:
            return rc2
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        default="",
        help="lab.yaml path (default: CEDE_LAB_CONFIG, else lab/config/lab.yaml if present, else lab.example.yaml)",
    )
    p.add_argument("--gateway", default=os.environ.get("GATEWAY", "pi@cede-pi.local"), help="SSH gateway (user@host)")
    p.add_argument(
        "--gateway-repo",
        default=os.environ.get("GATEWAY_REPO_ROOT", "~/cede"),
        help="Sparse repo root on gateway (default ~/cede)",
    )
    p.add_argument("--only", default="", help="optional filter initiator,target e.g. rpi,pico")
    p.add_argument("--dry-run", action="store_true", help="print planned steps only")
    p.add_argument("--json", action="store_true", help="print enabled pairs as JSON and exit")
    args = p.parse_args()

    repo = Path(__file__).resolve().parents[3]
    cfg_arg = (args.config or "").strip()
    cfg_path = Path(cfg_arg) if cfg_arg else _default_config_path(repo)
    if not cfg_path.is_file():
        print(f"error: config not found: {cfg_path}", file=sys.stderr)
        return 1
    data = _load_yaml(cfg_path)
    matrix = data.get("i2c_matrix") or {}
    pairs = matrix.get("pairs") or []
    enabled = [x for x in pairs if x.get("status") == "enabled"]
    if args.json:
        print(json.dumps(enabled, indent=2))
        return 0

    filt = args.only.strip().lower()
    if filt:
        pairs_run = [p for p in enabled if f"{p.get('initiator')},{p.get('target')}".lower() == filt]
        if not pairs_run:
            print(f"error: no enabled pair for --only {filt!r}", file=sys.stderr)
            return 1
    else:
        pairs_run = enabled

    if not pairs_run:
        print("error: no enabled i2c_matrix pairs", file=sys.stderr)
        return 1

    firmware_digest = _firmware_digest(repo)
    exit_code = 0
    for pair in pairs_run:
        v = pair.get("validation") or {}
        mode = v.get("mode")
        if not mode:
            print(f"error: enabled pair missing validation.mode: {pair!r}", file=sys.stderr)
            return 1
        if mode == "rpi_master_i2cdev_read":
            rc = run_pair_rpi(args.gateway, args.gateway_repo, pair, firmware_digest, args.dry_run)
        elif mode == "initiator_usb_i2c_master_probe":
            print(
                "error: validation.mode initiator_usb_i2c_master_probe is no longer supported "
                "(Pico↔Uno USB-triggered probes removed). Use rpi_master_i2cdev_read for Pi→Pico and Pi→Uno; "
                "delete pico↔uno rows from i2c_matrix in lab.yaml.",
                file=sys.stderr,
            )
            return 1
        else:
            print(f"error: unknown validation.mode {mode!r}", file=sys.stderr)
            return 1
        exit_code = max(exit_code, rc)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
