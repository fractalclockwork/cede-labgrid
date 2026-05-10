"""Unit tests for lab/pi/scripts/cede_test_image_id.py (unique per invocation)."""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path


def _load_mod(repo_root: Path):
    path = repo_root / "lab" / "pi" / "scripts" / "cede_test_image_id.py"
    spec = importlib.util.spec_from_file_location("_cede_test_image_id", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_make_test_image_id_unique_sequential_calls(repo_root: Path) -> None:
    m = _load_mod(repo_root)
    a = m.make_test_image_id()
    time.sleep(0.002)
    b = m.make_test_image_id()
    assert a != b
    assert a.startswith("t")
    assert b.startswith("t")
    assert "_" in a
