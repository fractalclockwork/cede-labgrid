"""SD image pipeline test via LabGrid -- fetch, expand, and patch a Pi OS image.

This test calls the existing pi_bootstrap.py functions programmatically to
build a gateway-ready SD image.  It does NOT write to a physical SD card
(that requires ``--device`` and sudo); it validates the image-preparation
pipeline only.

The actual dd-to-SD step remains a manual ``make export-raw-dd`` operation
because CEDE does not have SD-Mux hardware for automated card switching.

Requires:
    - Network access (fetches the Pi OS image on first run; cached thereafter)
    - Sufficient disk space under lab/pi/dist/ (~1.5 GB for .xz + .img)
    - sudo for loop-mount patch (``patch-image`` step)

Run:
    pytest --lg-env env/remote.yaml lab/tests/test_sd_image_labgrid.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_DIR = REPO_ROOT / "lab" / "pi" / "bootstrap"


def _ensure_importable() -> None:
    """Put the bootstrap directory on sys.path so pi_bootstrap can be imported."""
    d = str(BOOTSTRAP_DIR)
    if d not in sys.path:
        sys.path.insert(0, d)


@pytest.fixture
def lab_cfg() -> Path:
    """Resolve the lab config path (lab.yaml or lab.example.yaml)."""
    _ensure_importable()
    from pi_bootstrap import resolve_lab_config

    return resolve_lab_config(REPO_ROOT)


@pytest.mark.labgrid
def test_fetch_image(lab_cfg):
    """Download the compressed Pi OS image (skipped if already cached)."""
    _ensure_importable()
    from pi_bootstrap import cmd_fetch_image

    cmd_fetch_image(REPO_ROOT, lab_cfg, force=False)


@pytest.mark.labgrid
def test_expand_image(lab_cfg):
    """Decompress the .xz to a raw .img (skipped if already expanded)."""
    _ensure_importable()
    from pi_bootstrap import cmd_expand_image

    cmd_expand_image(REPO_ROOT, lab_cfg, force=False)


@pytest.mark.labgrid
def test_render_cloud_init(lab_cfg):
    """Render cloud-init templates (user-data, meta-data, network-config)."""
    _ensure_importable()
    from pi_bootstrap import cmd_render

    cmd_render(REPO_ROOT, lab_cfg)
