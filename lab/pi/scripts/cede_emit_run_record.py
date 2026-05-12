#!/usr/bin/env python3
"""Write a JSON run record under lab/tests/results (path from lab config).

Used after successful flash+serial validation when CEDE_RUN_RECORD=1 (see devhost_pi_gateway.sh).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
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
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _results_dir(repo: Path) -> Path:
    cfg_path = _default_config_path(repo)
    cfg = _load_yaml(cfg_path)
    paths = cfg.get("paths") or {}
    rel = paths.get("test_results_dir") or "lab/tests/results"
    out = (repo / rel).resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Emit CEDE flash/validate run record JSON.")
    p.add_argument("--repo", type=Path, required=True, help="Repository root (full checkout)")
    p.add_argument("--target", required=True, choices=("pico", "uno"), help="MCU target id")
    p.add_argument("--stage", default="flash_validate_serial", help="Pipeline stage name")
    p.add_argument("--tty", default="", help="Resolved serial device on gateway (optional)")
    p.add_argument("--digest", default="", help="Firmware digest string")
    p.add_argument("--gateway", default="", help="SSH gateway target e.g. pi@cede-pi.local")
    p.add_argument("--exit-status", type=int, default=0)
    p.add_argument(
        "--application-id",
        default="",
        help="Logical application id (e.g. i2c_hello); optional",
    )
    p.add_argument(
        "--transport-path",
        default="",
        help="Transport layer for this stage (e.g. usb_serial, i2c)",
    )
    args = p.parse_args()

    repo = args.repo.resolve()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_tty = (args.tty or "").replace("/", "_") or "no_tty"
    out_dir = _results_dir(repo)
    path = out_dir / f"run_{ts}_{args.target}_{safe_tty}.json"

    record = {
        "schema_version": 1,
        "target": args.target,
        "stage": args.stage,
        "digest": (args.digest or "").strip(),
        "tty": args.tty.strip() if args.tty else None,
        "gateway": args.gateway.strip() if args.gateway else None,
        "exit_status": args.exit_status,
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    aid = (args.application_id or "").strip()
    if aid:
        record["application_id"] = aid
    tp = (args.transport_path or "").strip()
    if tp:
        record["transport_path"] = tp

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
