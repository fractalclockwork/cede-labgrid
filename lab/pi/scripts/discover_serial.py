#!/usr/bin/env python3
"""Resolve serial device paths from lab config (lab.example.yaml / lab.yaml)."""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
from typing import Any

import yaml


def load_lab_config() -> dict[str, Any]:
    path = os.environ.get("CEDE_LAB_CONFIG")
    if path:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    repo = Path(__file__).resolve().parents[3]
    for name in ("lab.yaml", "lab.example.yaml"):
        p = repo / "lab" / "config" / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("No lab config found; set CEDE_LAB_CONFIG or add lab/config/lab.yaml")


def first_match(patterns: list[str]) -> str | None:
    for pat in patterns:
        matches = sorted(glob.glob(pat))
        if matches:
            return matches[0]
    return None


def resolve_device(dev_id: str, cfg: dict[str, Any]) -> tuple[str | None, list[str]]:
    devices = cfg.get("serial", {}).get("devices", {})
    entry = devices.get(dev_id)
    if not entry:
        return None, []
    tried: list[str] = []
    if entry.get("by_id_glob"):
        tried.append(entry["by_id_glob"])
        m = first_match([entry["by_id_glob"]])
        if m:
            return m, tried
    for g in entry.get("fallback_globs", []):
        tried.append(g)
        m = first_match([g])
        if m:
            return m, tried
    return None, tried


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", nargs="?", choices=("pico", "uno"), help="Logical device id")
    parser.add_argument("--json", action="store_true", help="Print machine-readable lines")
    args = parser.parse_args()

    cfg = load_lab_config()

    if args.device:
        path, tried = resolve_device(args.device, cfg)
        if args.json:
            print(f"{args.device}\t{path or ''}\t{';'.join(tried)}")
        else:
            print(f"{args.device}: {path or 'NOT FOUND'}")
            if path is None:
                print("  tried:", tried)
        raise SystemExit(0 if path else 2)

    for dev_id in ("pico", "uno"):
        path, tried = resolve_device(dev_id, cfg)
        print(f"{dev_id}: {path or 'NOT FOUND'}")
        if path is None:
            print("  tried:", tried)


if __name__ == "__main__":
    main()
