#!/usr/bin/env python3
"""YAML-driven Raspberry Pi cloud-init render and SD helpers (see lab/config/lab.example.yaml)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

_BOOTSTRAP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BOOTSTRAP_DIR.parent.parent.parent
if str(_BOOTSTRAP_DIR) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_DIR))

from cloud_init_render import render_cloud_init  # noqa: E402


def resolve_lab_config(repo_root: Path) -> Path:
    env = os.environ.get("CEDE_LAB_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    override = repo_root / "lab/config/lab.yaml"
    if override.is_file():
        return override.resolve()
    return (repo_root / "lab/config/lab.example.yaml").resolve()


def load_lab_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as e:
        raise SystemExit(
            "pi_bootstrap.py requires PyYAML (python3-yaml). "
            "Or run: docker compose -f lab/docker/docker-compose.yml run --rm orchestration-dev "
            "python /workspace/lab/pi/bootstrap/pi_bootstrap.py ..."
        ) from e
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid lab config: {path}")
    return data


def validate_schema(repo_root: Path, data: dict) -> None:
    try:
        import jsonschema
    except ImportError as e:
        raise SystemExit(
            "pi_bootstrap.py requires jsonschema for validation (python3-jsonschema), "
            "or run inside orchestration-dev."
        ) from e
    schema_path = repo_root / "lab/config/lab.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)


def resolve_hostname(cfg: dict) -> str:
    rpb = cfg.get("raspberry_pi_bootstrap") or {}
    if isinstance(rpb, dict) and rpb.get("hostname"):
        return str(rpb["hostname"]).strip()
    ssh_host = ((cfg.get("hosts") or {}).get("pi") or {}).get("ssh_host") or ""
    if isinstance(ssh_host, str) and ssh_host.endswith(".local"):
        return ssh_host[: -len(".local")]
    raise SystemExit(
        "Set raspberry_pi_bootstrap.hostname or hosts.pi.ssh_host as '<name>.local' "
        "to derive the hostname."
    )


def ensure_ssh_host_alignment(cfg: dict, hostname: str) -> None:
    ssh_host = ((cfg.get("hosts") or {}).get("pi") or {}).get("ssh_host") or ""
    if not ssh_host or not ssh_host.endswith(".local"):
        return
    expected = f"{hostname}.local"
    if ssh_host != expected:
        raise SystemExit(
            f"hosts.pi.ssh_host is {ssh_host!r}; use {expected!r} for mDNS consistency "
            "with raspberry_pi_bootstrap.hostname."
        )


def expand_path(p: str | None) -> Path | None:
    """Resolve paths from lab.yaml. Under `sudo`, `~` must not become /root for SSH keys."""
    if not p:
        return None
    s = os.path.expandvars(str(p))
    # sudo sets HOME=/root; YAML paths like ~/.ssh/foo should stay on the invoking user.
    if os.geteuid() == 0:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            try:
                sudo_home = pwd.getpwnam(sudo_user).pw_dir
            except KeyError:
                sudo_home = None
            if sudo_home:
                if s == "~":
                    s = sudo_home
                elif s.startswith("~/"):
                    s = sudo_home + s[1:]
    return Path(os.path.expanduser(s)).resolve()


def render_from_lab_config(
    repo_root: Path,
    cfg: dict,
    *,
    cloud_init_out_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    rpb = cfg.get("raspberry_pi_bootstrap") or {}
    hostname = resolve_hostname(cfg)
    ensure_ssh_host_alignment(cfg, hostname)

    ssh_user = ((cfg.get("hosts") or {}).get("pi") or {}).get("ssh_user") or "pi"
    ak = expand_path(rpb.get("authorized_keys_file")) if rpb.get("authorized_keys_file") else None
    if ak is not None and not ak.is_file():
        raise SystemExit(f"authorized_keys_file not found: {ak}")

    timezone = str(rpb.get("timezone") or "UTC")
    locale = str(rpb.get("locale") or "en_US.UTF-8")

    wifi: dict[str, str] | None = None
    wifi_cfg = rpb.get("wifi")
    if wifi_cfg:
        ssid = str(wifi_cfg["ssid"])
        if wifi_cfg.get("psk_file"):
            pf = expand_path(str(wifi_cfg["psk_file"]))
            if pf is None or not pf.is_file():
                raise SystemExit(f"wifi.psk_file not found: {wifi_cfg.get('psk_file')}")
            psk = pf.read_text(encoding="utf-8").strip()
        elif wifi_cfg.get("psk"):
            psk = str(wifi_cfg["psk"])
        else:
            raise SystemExit("wifi requires psk or psk_file")
        wifi = {
            "ssid": ssid,
            "psk": psk,
            "country": str(wifi_cfg.get("regulatory_domain") or "US"),
        }

    return render_cloud_init(
        repo_root,
        hostname=hostname,
        ssh_user=str(ssh_user),
        authorized_keys_file=ak,
        timezone=timezone,
        locale=locale,
        wifi=wifi,
        out_dir=cloud_init_out_dir,
    )


def cmd_render(repo_root: Path, cfg: Path) -> None:
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    ud, md, nc = render_from_lab_config(repo_root, data)
    print(f"Rendered:\n  {ud}\n  {md}\n  {nc}")


def cmd_flash(repo_root: Path, cfg: Path, device: str, yes: bool) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    rpb = data.get("raspberry_pi_bootstrap") or {}
    os_image = rpb.get("os_image") or {}
    url = os_image.get("url")
    if not url:
        raise SystemExit("flash requires raspberry_pi_bootstrap.os_image.url in the lab config")

    sha256 = (os_image.get("sha256") or "").strip()

    render_from_lab_config(repo_root, data)

    script = repo_root / "lab/pi/scripts/flash_sdcard.sh"
    args = ["sudo", str(script), "--device", device, "--url", str(url), "--yes", "--use-existing-rendered"]
    if sha256:
        args.extend(["--sha256", sha256])
    subprocess.run(args, check=True, cwd=repo_root)


def cmd_prepare_boot(repo_root: Path, cfg: Path, device: str, yes: bool) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    render_from_lab_config(repo_root, data)

    script = repo_root / "lab/pi/scripts/prepare_sdcard_boot.sh"
    args = ["sudo", str(script), "--device", device, "--yes", "--use-existing-rendered"]
    subprocess.run(args, check=True, cwd=repo_root)


def cmd_patch_image(repo_root: Path, cfg: Path, image: Path, yes: bool) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the image path")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    render_from_lab_config(repo_root, data)

    script = repo_root / "lab/pi/scripts/patch_image_boot.sh"
    subprocess.run(["sudo", str(script), "--image", str(image.resolve()), "--yes"], check=True, cwd=repo_root)


def _os_image_section(repo_root: Path, cfg: Path) -> tuple[str, Path, dict]:
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    rpb = data.get("raspberry_pi_bootstrap") or {}
    os_image = rpb.get("os_image") or {}
    url = os_image.get("url") or ""
    cache_rel = os_image.get("cache_path") or ""
    if not url or not cache_rel:
        raise SystemExit(
            "fetch-image / expand-image require raspberry_pi_bootstrap.os_image.url and cache_path"
        )
    dest = (repo_root / cache_rel).resolve()
    return url, dest, os_image


def cmd_fetch_image(repo_root: Path, cfg: Path, force: bool) -> None:
    url, dest, os_image = _os_image_section(repo_root, cfg)
    sha_expected = (os_image.get("sha256") or "").strip()

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print(f"Already present (use --force to re-download): {dest}")
        return

    print(f"==> Downloading\n    {url}\n -> {dest}")
    subprocess.run(
        ["curl", "-fL", "--retry", "3", "--retry-delay", "2", "-o", str(dest), url],
        check=True,
    )

    if sha_expected:
        print("==> Verifying SHA256")
        h = hashlib.sha256()
        with dest.open("rb") as f:
            while chunk := f.read(1 << 22):
                h.update(chunk)
        got = h.hexdigest()
        if got.lower() != sha_expected.lower():
            dest.unlink(missing_ok=True)
            raise SystemExit(f"SHA256 mismatch: expected {sha_expected}, got {got}")
        print("SHA256 OK")
    else:
        print("warn: os_image.sha256 empty; skipping checksum (pin sha256 in lab.yaml for reproducibility)")


def cmd_expand_image(repo_root: Path, cfg: Path, force: bool) -> None:
    _, xz_path, _ = _os_image_section(repo_root, cfg)
    if not xz_path.name.endswith(".xz"):
        raise SystemExit(f"expand-image expects cache_path to end with .xz, got: {xz_path}")

    img_path = xz_path.parent / xz_path.name.removesuffix(".xz")
    if not img_path.name.endswith(".img"):
        raise SystemExit(f"unexpected cache_path naming (want *.img.xz): {xz_path}")

    if not xz_path.is_file():
        raise SystemExit(f"missing downloaded image (run fetch-image first): {xz_path}")

    if img_path.exists() and not force:
        print(f"Already expanded (use --force to redo): {img_path}")
        return

    if img_path.exists():
        img_path.unlink()

    print(f"==> xz -dk {xz_path}")
    subprocess.run(["xz", "-dk", str(xz_path)], check=True)
    print(f"Wrote {img_path}")


def cmd_flash_file(repo_root: Path, cfg: Path, device: str, image: Path, yes: bool) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)

    img = image.resolve()
    if not img.is_file():
        raise SystemExit(f"image not found: {img}")

    render_from_lab_config(repo_root, data)

    script = repo_root / "lab/pi/scripts/flash_sdcard.sh"
    args = ["sudo", str(script), "--device", device, "--url", str(img), "--yes", "--use-existing-rendered"]
    subprocess.run(args, check=True, cwd=repo_root)


def main(argv: list[str] | None = None) -> int:
    repo_root = _REPO_ROOT
    default_cfg = resolve_lab_config(repo_root)

    parser = argparse.ArgumentParser(
        description="CEDE Raspberry Pi bootstrap from lab YAML (raspberry_pi_bootstrap)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_cfg,
        help=f"Lab YAML (default: {default_cfg})",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="Write lab/pi/cloud-init/rendered from lab.yaml")
    p_render.set_defaults(func=lambda a: cmd_render(repo_root, a.config))

    p_flash = sub.add_parser(
        "flash",
        help="Render then flash SD via rpi-imager using os_image.url from lab.yaml",
    )
    p_flash.add_argument("--device", required=True, help="Whole disk e.g. /dev/sdc")
    p_flash.add_argument("--yes", action="store_true", required=True)
    p_flash.set_defaults(func=lambda a: cmd_flash(repo_root, a.config, a.device, a.yes))

    p_prep = sub.add_parser(
        "prepare-boot",
        help="Render then copy cloud-init to an already-flashed card",
    )
    p_prep.add_argument("--device", required=True)
    p_prep.add_argument("--yes", action="store_true", required=True)
    p_prep.set_defaults(func=lambda a: cmd_prepare_boot(repo_root, a.config, a.device, a.yes))

    p_img = sub.add_parser(
        "patch-image",
        help="Render then inject cloud-init into a disk .img (loop-mount boot partition)",
    )
    p_img.add_argument("--image", type=Path, required=True)
    p_img.add_argument("--yes", action="store_true", required=True)
    p_img.set_defaults(func=lambda a: cmd_patch_image(repo_root, a.config, a.image, a.yes))

    p_fetch = sub.add_parser(
        "fetch-image",
        help="Download os_image.url to os_image.cache_path (see lab.yaml)",
    )
    p_fetch.add_argument("--force", action="store_true", help="Re-download even if cache exists")
    p_fetch.set_defaults(func=lambda a: cmd_fetch_image(repo_root, a.config, a.force))

    p_exp = sub.add_parser(
        "expand-image",
        help="Decompress os_image.cache_path (*.img.xz) to *.img using xz -dk",
    )
    p_exp.add_argument("--force", action="store_true", help="Remove existing .img and decompress again")
    p_exp.set_defaults(func=lambda a: cmd_expand_image(repo_root, a.config, a.force))

    p_ff = sub.add_parser(
        "flash-file",
        help="Render then flash a local disk image file (after patch-image / expand-image)",
    )
    p_ff.add_argument("--device", required=True, help="Whole disk e.g. /dev/sdc")
    p_ff.add_argument("--image", type=Path, required=True, help="Path to .img or .img.xz")
    p_ff.add_argument("--yes", action="store_true", required=True)
    p_ff.set_defaults(func=lambda a: cmd_flash_file(repo_root, a.config, a.device, a.image, a.yes))

    args = parser.parse_args(argv)

    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
