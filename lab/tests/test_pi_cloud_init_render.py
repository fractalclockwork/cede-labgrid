"""Offline checks: lab YAML renders cloud-init user-data with expected hostname and labgrid setup."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def pi_bootstrap(repo_root: Path):
    bootstrap_dir = repo_root / "lab/pi/bootstrap"
    sys.path.insert(0, str(bootstrap_dir))
    import pi_bootstrap as pb

    yield pb
    sys.path.remove(str(bootstrap_dir))


@pytest.fixture
def _fake_ssh_key(tmp_path: Path, lab_config_path: Path):
    """Create a temp SSH pub key so render doesn't fail in environments without ~/.ssh/."""
    pub = tmp_path / "ci_test_key.pub"
    pub.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGtlc3Qga2V5 ci-test\n", encoding="utf-8")
    return pub


def _patch_authorized_keys(cfg: dict, pub_path: Path) -> dict:
    """Return a deep copy of cfg with authorized_keys_file pointing at pub_path."""
    cfg = copy.deepcopy(cfg)
    for exp in cfg.get("exporters", []):
        exp["authorized_keys_file"] = str(pub_path)
    rpb = cfg.get("raspberry_pi_bootstrap")
    if rpb and "authorized_keys_file" in rpb:
        rpb["authorized_keys_file"] = str(pub_path)
    return cfg


def test_rendered_user_data_contains_cloud_config_and_hostname(
    pi_bootstrap, repo_root: Path, lab_config_path: Path, tmp_path: Path, _fake_ssh_key: Path,
):
    cfg = pi_bootstrap.load_lab_yaml(lab_config_path)
    cfg = _patch_authorized_keys(cfg, _fake_ssh_key)
    pi_bootstrap.validate_schema(repo_root, cfg)
    exporters = pi_bootstrap.resolve_exporters(cfg)
    assert exporters, "expected at least one exporter in example config"
    hostname = exporters[0]["hostname"]
    ud_path, _md, nc_path = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path
    )
    text = ud_path.read_text(encoding="utf-8")
    assert "#cloud-config" in text
    assert "enable_ssh: true" in text
    assert hostname in text
    nc = nc_path.read_text(encoding="utf-8")
    assert "NetworkManager" in nc and "eth0:" in nc


def test_rendered_user_data_includes_labgrid_exporter_setup(
    pi_bootstrap, repo_root: Path, lab_config_path: Path, tmp_path: Path, _fake_ssh_key: Path,
):
    cfg = pi_bootstrap.load_lab_yaml(lab_config_path)
    cfg = _patch_authorized_keys(cfg, _fake_ssh_key)
    pi_bootstrap.validate_schema(repo_root, cfg)
    exporters = pi_bootstrap.resolve_exporters(cfg)
    if not exporters:
        pytest.skip("lab config has no exporters section")

    exp = exporters[0]
    coordinator_address = pi_bootstrap._resolve_coordinator_address(cfg)

    ud_path, _md, _nc = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path
    )
    text = ud_path.read_text(encoding="utf-8")

    assert "ser2net" in text
    assert "write_files:" in text
    assert "labgrid-exporter" in text
    for res in exp["resources"]:
        for v in res["match"].values():
            assert v in text
    assert coordinator_address in text
    assert "labgrid>=25.0" in text
    assert "enable-linger" in text


def test_rendered_user_data_without_labgrid(
    pi_bootstrap, repo_root: Path, lab_config_path: Path, tmp_path: Path
):
    """When both exporters and raspberry_pi_bootstrap are absent, no exporter config is rendered."""
    cfg = pi_bootstrap.load_lab_yaml(lab_config_path)
    pi_bootstrap.validate_schema(repo_root, cfg)
    cfg.pop("exporters", None)
    cfg.pop("labgrid", None)
    cfg.pop("raspberry_pi_bootstrap", None)

    from cloud_init_render import render_cloud_init
    ud_path, _md, _nc = render_cloud_init(
        repo_root,
        hostname="test-pi",
        out_dir=tmp_path,
    )
    text = ud_path.read_text(encoding="utf-8")

    assert "write_files:" not in text
    assert "labgrid-exporter" not in text
