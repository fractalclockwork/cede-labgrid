from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml


@pytest.fixture
def schema(repo_root: Path) -> dict:
    schema_path = repo_root / "lab" / "config" / "lab.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def test_lab_example_validates(schema: dict, lab_config_path: Path) -> None:
    with open(lab_config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    jsonschema.validate(instance=data, schema=schema)
