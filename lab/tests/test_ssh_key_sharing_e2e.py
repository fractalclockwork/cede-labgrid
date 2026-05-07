"""E2E (offline) SSH key sharing: Dev-Host .pub → lab config → cloud-init user-data.

Covers the pipeline in lab/pi/docs/ssh-keys-bootstrap.md without a live Pi: schema,
alignment of ``hosts.pi.ssh_host`` with ``hostname``, embedding keys under the Pi login user,
and rejecting invalid inputs.
"""

from __future__ import annotations

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
def base_lab_cfg(repo_root: Path) -> dict:
    path = repo_root / "lab/config/lab.example.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_e2e_public_key_embedded_for_pi_user(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    """Authorized key file content appears under cloud-init ``users`` / ``ssh_authorized_keys``."""
    pub = tmp_path / "dev_ed25519.pub"
    key_line = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGaaaatestcedekey lab-e2e-dev-host"
    pub.write_text(f"# dev-host\n{key_line}\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    out = tmp_path / "rendered"
    ud_path, _md, _nc = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=out
    )
    text = ud_path.read_text(encoding="utf-8")

    assert "users:" in text
    assert "ssh_authorized_keys:" in text
    assert "name: pi" in text
    assert "groups:" in text and "sudo" in text
    assert "sudo: ALL=(ALL) NOPASSWD:ALL" in text
    assert key_line in text
    assert "# dev-host" not in text  # comment lines from .pub are not copied


def test_e2e_multiple_keys_embedded(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    pub = tmp_path / "multi.pub"
    k1 = "ssh-ed25519 AAAAfirst lab-one"
    k2 = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCs lab-two"
    pub.write_text(f"{k1}\n{k2}\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    ud_path, *_ = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path / "r"
    )
    text = ud_path.read_text(encoding="utf-8")
    assert k1 in text and k2 in text


def test_e2e_custom_ssh_user_on_gateway(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    pub = tmp_path / "k.pub"
    pub.write_text("ssh-ed25519 AAAACUSTOM u\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("hosts", {}).setdefault("pi", {})["ssh_user"] = "cede"
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    ud_path, *_ = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path / "o"
    )
    t = ud_path.read_text(encoding="utf-8")
    assert "name: cede" in t
    assert "sudo: ALL=(ALL) NOPASSWD:ALL" in t


def test_e2e_misaligned_ssh_host_rejected(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    pub = tmp_path / "k.pub"
    pub.write_text("ssh-ed25519 AAAAlign test\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["hostname"] = "cede-pi"
    cfg.setdefault("hosts", {}).setdefault("pi", {})["ssh_host"] = "wrong-gw.local"
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    with pytest.raises(SystemExit, match="ssh_host|cede-pi"):
        pi_bootstrap.render_from_lab_config(repo_root, cfg, cloud_init_out_dir=tmp_path / "x")


def test_e2e_missing_authorized_keys_file_rejected(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(
        tmp_path / "nonexistent.pub"
    )

    pi_bootstrap.validate_schema(repo_root, cfg)
    with pytest.raises(SystemExit, match="authorized_keys_file not found"):
        pi_bootstrap.render_from_lab_config(repo_root, cfg, cloud_init_out_dir=tmp_path / "y")


def test_e2e_pub_file_only_comments_rejected(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    pub = tmp_path / "empty.pub"
    pub.write_text("# only a comment\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    with pytest.raises(SystemExit, match="no ssh public keys"):
        pi_bootstrap.render_from_lab_config(repo_root, cfg, cloud_init_out_dir=tmp_path / "z")


def test_e2e_key_line_escaping_for_yaml_string(
    pi_bootstrap,
    repo_root: Path,
    base_lab_cfg: dict,
    tmp_path: Path,
) -> None:
    """Backslashes and quotes in the key line survive cloud-init YAML quoting."""
    pub = tmp_path / "special.pub"
    pub.write_text(r'ssh-ed25519 AAAAspecial \\ \" inner lab-x' "\n", encoding="utf-8")

    cfg = yaml.safe_load(yaml.dump(base_lab_cfg))
    cfg.setdefault("raspberry_pi_bootstrap", {})["authorized_keys_file"] = str(pub.resolve())

    pi_bootstrap.validate_schema(repo_root, cfg)
    ud_path, *_ = pi_bootstrap.render_from_lab_config(
        repo_root, cfg, cloud_init_out_dir=tmp_path / "s"
    )
    text = ud_path.read_text(encoding="utf-8")
    assert "ssh_authorized_keys:" in text
    assert "AAAAspecial" in text
