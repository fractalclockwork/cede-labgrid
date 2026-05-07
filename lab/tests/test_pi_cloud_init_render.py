"""Offline checks: lab YAML renders cloud-init user-data with expected hostname."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture
def pi_bootstrap(repo_root: Path):
    bootstrap_dir = repo_root / "lab/pi/bootstrap"
    sys.path.insert(0, str(bootstrap_dir))
    import pi_bootstrap as pb

    yield pb
    sys.path.remove(str(bootstrap_dir))


def test_rendered_user_data_contains_cloud_config_and_hostname(
    pi_bootstrap, repo_root: Path, lab_config_path: Path, tmp_path: Path
):
    cfg = pi_bootstrap.load_lab_yaml(lab_config_path)
    pi_bootstrap.validate_schema(repo_root, cfg)
    ud_path, _md, nc_path = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path
    )
    text = ud_path.read_text(encoding="utf-8")
    assert "#cloud-config" in text
    assert "enable_ssh: true" in text
    hn = pi_bootstrap.resolve_hostname(cfg)
    assert hn in text
    nc = nc_path.read_text(encoding="utf-8")
    assert "NetworkManager" in nc and "eth0:" in nc
