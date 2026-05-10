from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml


@pytest.fixture
def schema(repo_root: Path) -> dict:
    schema_path = repo_root / "lab" / "config" / "lab.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def test_lab_example_validates(schema: dict, repo_root: Path) -> None:
    """Tracked example must satisfy the schema (CI has no lab/config/lab.yaml)."""
    example = repo_root / "lab" / "config" / "lab.example.yaml"
    with open(example, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    jsonschema.validate(instance=data, schema=schema)


def test_lab_i2c_matrix_validate_json_lists_enabled_pairs(repo_root: Path) -> None:
    script = repo_root / "lab" / "pi" / "scripts" / "lab_i2c_matrix_validate.py"
    example = repo_root / "lab" / "config" / "lab.example.yaml"
    proc = subprocess.run(
        [sys.executable, str(script), "--config", str(example), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    assert len(rows) >= 1
    assert all(p.get("status") == "enabled" for p in rows)
    assert all("validation" in p for p in rows)
