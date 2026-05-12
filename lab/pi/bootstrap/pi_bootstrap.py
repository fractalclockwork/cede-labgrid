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
import textwrap
import warnings
from pathlib import Path

_BOOTSTRAP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BOOTSTRAP_DIR.parent.parent.parent
if str(_BOOTSTRAP_DIR) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_DIR))

from cloud_init_render import render_cloud_init, render_exporter_yaml  # noqa: E402


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


# ---------------------------------------------------------------------------
# Exporter resolution: new 'exporters' list or deprecated 'raspberry_pi_bootstrap'
# ---------------------------------------------------------------------------

def _resolve_coordinator_address(cfg: dict) -> str:
    lg = cfg.get("labgrid")
    if lg and lg.get("coordinator_address"):
        return str(lg["coordinator_address"])
    rpb = cfg.get("raspberry_pi_bootstrap") or {}
    rpb_lg = rpb.get("labgrid") or {}
    if rpb_lg.get("coordinator_address"):
        return str(rpb_lg["coordinator_address"])
    raise SystemExit(
        "labgrid.coordinator_address (or raspberry_pi_bootstrap.labgrid.coordinator_address) is required."
    )


def _legacy_to_exporter(rpb: dict) -> dict:
    """Convert a raspberry_pi_bootstrap section to an exporter entry."""
    lg = rpb.get("labgrid") or {}
    exporter: dict = {
        "name": lg.get("exporter_name", rpb.get("hostname", "")),
        "hostname": rpb.get("hostname", ""),
        "ssh_user": "pi",
        "location": lg.get("location", "cede-lab-bench-1"),
        "resources": [],
    }
    if rpb.get("authorized_keys_file"):
        exporter["authorized_keys_file"] = rpb["authorized_keys_file"]
    if rpb.get("timezone"):
        exporter["timezone"] = rpb["timezone"]
    if rpb.get("locale"):
        exporter["locale"] = rpb["locale"]
    if rpb.get("os_image"):
        exporter["os_image"] = rpb["os_image"]
    if rpb.get("wifi"):
        exporter["wifi"] = rpb["wifi"]

    if lg.get("pico_usb_serial_short"):
        exporter["resources"].append({
            "group": "cede-pico-port",
            "type": "USBSerialPort",
            "match": {"ID_SERIAL_SHORT": lg["pico_usb_serial_short"]},
            "speed": 115200,
            "place": "cede-pico",
            "place_tags": {"board": "pico"},
        })
    if lg.get("uno_usb_serial_short"):
        exporter["resources"].append({
            "group": "cede-uno-port",
            "type": "USBSerialPort",
            "match": {"ID_SERIAL_SHORT": lg["uno_usb_serial_short"]},
            "speed": 115200,
            "place": "cede-uno",
            "place_tags": {"board": "uno"},
        })
    return exporter


def resolve_exporters(cfg: dict) -> list[dict]:
    """Return the normalized list of exporter entries from the config."""
    if cfg.get("exporters"):
        return list(cfg["exporters"])

    rpb = cfg.get("raspberry_pi_bootstrap")
    if rpb:
        warnings.warn(
            "raspberry_pi_bootstrap is deprecated; migrate to labgrid + exporters "
            "(see lab/config/lab.example.yaml).",
            DeprecationWarning,
            stacklevel=2,
        )
        return [_legacy_to_exporter(rpb)]

    return []


def filter_exporters(exporters: list[dict], name: str | None) -> list[dict]:
    if name is None:
        return exporters
    matched = [e for e in exporters if e["name"] == name]
    if not matched:
        names = [e["name"] for e in exporters]
        raise SystemExit(f"exporter {name!r} not found; available: {names}")
    return matched


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def expand_path(p: str | None) -> Path | None:
    """Resolve paths from lab.yaml. Under `sudo`, `~` must not become /root for SSH keys."""
    if not p:
        return None
    s = os.path.expandvars(str(p))
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


# ---------------------------------------------------------------------------
# Cloud-init render (per exporter)
# ---------------------------------------------------------------------------

def render_exporter_cloud_init(
    repo_root: Path,
    coordinator_address: str,
    exporter: dict,
    *,
    cloud_init_out_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Render cloud-init files for a single exporter."""
    hostname = exporter["hostname"]
    ssh_user = exporter.get("ssh_user", "pi")

    ak_str = exporter.get("authorized_keys_file")
    ak = expand_path(ak_str)
    if ak is not None and not ak.is_file():
        raise SystemExit(f"authorized_keys_file not found: {ak}")

    timezone = str(exporter.get("timezone", "UTC"))
    locale = str(exporter.get("locale", "en_US.UTF-8"))

    wifi: dict[str, str] | None = None
    wifi_cfg = exporter.get("wifi")
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
            "country": str(wifi_cfg.get("regulatory_domain", "US")),
        }

    out_dir = cloud_init_out_dir or (
        repo_root / "lab/pi/cloud-init/rendered" / exporter["name"]
    )

    return render_cloud_init(
        repo_root,
        hostname=hostname,
        ssh_user=ssh_user,
        authorized_keys_file=ak,
        timezone=timezone,
        locale=locale,
        wifi=wifi,
        coordinator_address=coordinator_address,
        exporter=exporter,
        out_dir=out_dir,
    )


# ---------------------------------------------------------------------------
# Legacy compat: render_from_lab_config (used by old callers)
# ---------------------------------------------------------------------------

def render_from_lab_config(
    repo_root: Path,
    cfg: dict,
    *,
    cloud_init_out_dir: Path | None = None,
    exporter_name: str | None = None,
) -> tuple[Path, Path, Path]:
    """Render cloud-init for one exporter (first match or named)."""
    exporters = resolve_exporters(cfg)
    if not exporters:
        rpb = cfg.get("raspberry_pi_bootstrap") or {}
        hostname = rpb.get("hostname", "")
        if not hostname:
            ssh_host = ((cfg.get("hosts") or {}).get("pi") or {}).get("ssh_host", "")
            if isinstance(ssh_host, str) and ssh_host.endswith(".local"):
                hostname = ssh_host[: -len(".local")]
        if not hostname:
            raise SystemExit("No exporters or raspberry_pi_bootstrap.hostname found")
        return render_cloud_init(
            repo_root,
            hostname=hostname,
            out_dir=cloud_init_out_dir,
        )

    selected = filter_exporters(exporters, exporter_name)
    coordinator_address = _resolve_coordinator_address(cfg)
    return render_exporter_cloud_init(
        repo_root,
        coordinator_address,
        selected[0],
        cloud_init_out_dir=cloud_init_out_dir,
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_render(repo_root: Path, cfg: Path, exporter_name: str | None) -> None:
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    if not exporters:
        raise SystemExit("No exporters defined in config")
    selected = filter_exporters(exporters, exporter_name)
    coordinator_address = _resolve_coordinator_address(data)
    for exp in selected:
        ud, md, nc = render_exporter_cloud_init(repo_root, coordinator_address, exp)
        print(f"Rendered {exp['name']}:\n  {ud}\n  {md}\n  {nc}")


def cmd_flash(repo_root: Path, cfg: Path, device: str, yes: bool, exporter_name: str | None) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    selected = filter_exporters(exporters, exporter_name)
    if len(selected) != 1:
        raise SystemExit("flash requires exactly one exporter (use --exporter NAME)")
    exp = selected[0]
    os_image = exp.get("os_image") or {}
    url = os_image.get("url")
    if not url:
        raise SystemExit(f"flash requires os_image.url for exporter {exp['name']}")

    sha256 = (os_image.get("sha256") or "").strip()
    coordinator_address = _resolve_coordinator_address(data)
    flat_rendered = repo_root / "lab/pi/cloud-init/rendered"
    render_exporter_cloud_init(repo_root, coordinator_address, exp, cloud_init_out_dir=flat_rendered)

    script = repo_root / "lab/pi/scripts/flash_sdcard.sh"
    args = ["sudo", str(script), "--device", device, "--url", str(url), "--yes", "--use-existing-rendered"]
    if sha256:
        args.extend(["--sha256", sha256])
    subprocess.run(args, check=True, cwd=repo_root)


def cmd_prepare_boot(repo_root: Path, cfg: Path, device: str, yes: bool, exporter_name: str | None) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    selected = filter_exporters(exporters, exporter_name)
    if len(selected) != 1:
        raise SystemExit("prepare-boot requires exactly one exporter (use --exporter NAME)")
    coordinator_address = _resolve_coordinator_address(data)
    flat_rendered = repo_root / "lab/pi/cloud-init/rendered"
    render_exporter_cloud_init(repo_root, coordinator_address, selected[0], cloud_init_out_dir=flat_rendered)

    script = repo_root / "lab/pi/scripts/prepare_sdcard_boot.sh"
    args = ["sudo", str(script), "--device", device, "--yes", "--use-existing-rendered"]
    subprocess.run(args, check=True, cwd=repo_root)


def cmd_patch_image(repo_root: Path, cfg: Path, image: Path, yes: bool, exporter_name: str | None) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the image path")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    selected = filter_exporters(exporters, exporter_name)
    if len(selected) != 1:
        raise SystemExit("patch-image requires exactly one exporter (use --exporter NAME)")
    coordinator_address = _resolve_coordinator_address(data)
    flat_rendered = repo_root / "lab/pi/cloud-init/rendered"
    render_exporter_cloud_init(repo_root, coordinator_address, selected[0], cloud_init_out_dir=flat_rendered)

    script = repo_root / "lab/pi/scripts/patch_image_boot.sh"
    subprocess.run(["sudo", str(script), "--image", str(image.resolve()), "--yes"], check=True, cwd=repo_root)


def _os_image_section(repo_root: Path, cfg: Path, exporter_name: str | None) -> tuple[str, Path, dict]:
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    selected = filter_exporters(exporters, exporter_name)
    if len(selected) != 1:
        raise SystemExit("fetch-image/expand-image require exactly one exporter (use --exporter NAME)")
    os_image = selected[0].get("os_image") or {}
    url = os_image.get("url") or ""
    cache_rel = os_image.get("cache_path") or ""
    if not url or not cache_rel:
        raise SystemExit(
            f"fetch-image / expand-image require os_image.url and cache_path for exporter {selected[0]['name']}"
        )
    dest = (repo_root / cache_rel).resolve()
    return url, dest, os_image


def cmd_fetch_image(repo_root: Path, cfg: Path, force: bool, exporter_name: str | None) -> None:
    url, dest, os_image = _os_image_section(repo_root, cfg, exporter_name)
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


def cmd_expand_image(repo_root: Path, cfg: Path, force: bool, exporter_name: str | None) -> None:
    _, xz_path, _ = _os_image_section(repo_root, cfg, exporter_name)
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


def cmd_flash_file(repo_root: Path, cfg: Path, device: str, image: Path, yes: bool, exporter_name: str | None) -> None:
    if not yes:
        raise SystemExit("refusing: pass --yes after confirming the SD device")
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    selected = filter_exporters(exporters, exporter_name)
    if len(selected) != 1:
        raise SystemExit("flash-file requires exactly one exporter (use --exporter NAME)")

    img = image.resolve()
    if not img.is_file():
        raise SystemExit(f"image not found: {img}")

    coordinator_address = _resolve_coordinator_address(data)
    flat_rendered = repo_root / "lab/pi/cloud-init/rendered"
    render_exporter_cloud_init(repo_root, coordinator_address, selected[0], cloud_init_out_dir=flat_rendered)

    script = repo_root / "lab/pi/scripts/flash_sdcard.sh"
    args = ["sudo", str(script), "--device", device, "--url", str(img), "--yes", "--use-existing-rendered"]
    subprocess.run(args, check=True, cwd=repo_root)


# ---------------------------------------------------------------------------
# New generation commands
# ---------------------------------------------------------------------------

def cmd_generate_exporter_configs(repo_root: Path, cfg: Path, exporter_name: str | None) -> None:
    """Generate env/exporters/<name>.yaml for each exporter."""
    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    if not exporters:
        raise SystemExit("No exporters defined")
    selected = filter_exporters(exporters, exporter_name)

    out_dir = repo_root / "env" / "exporters"
    out_dir.mkdir(parents=True, exist_ok=True)

    for exp in selected:
        content = render_exporter_yaml(exp)
        out_path = out_dir / f"{exp['name']}.yaml"
        out_path.write_text(content, encoding="utf-8")
        print(f"wrote {out_path}")


def cmd_generate_env(repo_root: Path, cfg: Path, exporter_name: str | None) -> None:
    """Generate env/remote.yaml from the exporters config."""
    try:
        import yaml
    except ImportError as e:
        raise SystemExit("PyYAML required") from e

    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    if not exporters:
        raise SystemExit("No exporters defined")
    selected = filter_exporters(exporters, exporter_name)

    targets: dict = {}
    for exp in selected:
        ssh_user = exp.get("ssh_user", "pi")
        ssh_host = exp.get("ssh_host", f"{exp['hostname']}.local")

        targets[f"{exp['name']}"] = {
            "resources": {
                "NetworkService": {
                    "address": ssh_host,
                    "username": ssh_user,
                },
            },
            "drivers": {
                "SSHDriver": {},
                "CedeI2CDriver": {"bus": 1},
            },
        }

        for res in exp.get("resources", []):
            place = res.get("place")
            if not place:
                continue
            tags = res.get("place_tags", {})
            board = tags.get("board", "")

            target_entry: dict = {
                "resources": {
                    "NetworkService": {
                        "address": ssh_host,
                        "username": ssh_user,
                    },
                    res["type"]: {
                        "match": dict(res["match"]),
                        "speed": res.get("speed", 115200),
                    },
                },
                "drivers": {"SSHDriver": {}, "SerialDriver": {}},
            }

            if board == "pico":
                target_entry["drivers"]["PicotoolFlashDriver"] = {"image": "pico_uf2"}
                target_entry["drivers"]["CedeValidationDriver"] = {"role": "pico", "image": "pico_uf2"}
                target_entry["drivers"]["CedeResetDriver"] = {"method": "picotool"}
                target_entry["drivers"]["CedeStrategy"] = {}
            elif board == "uno":
                target_entry["drivers"]["AvrdudeFlashDriver"] = {"image": "uno_hex"}
                target_entry["drivers"]["CedeValidationDriver"] = {"role": "uno", "image": "uno_hex"}
                target_entry["drivers"]["CedeResetDriver"] = {"method": "dtr"}
                target_entry["drivers"]["CedeStrategy"] = {}

            targets[place] = target_entry

    env: dict = {
        "targets": targets,
        "images": {
            "pico_uf2": "lab/pico/hello_lab/build/hello_lab.uf2",
            "uno_hex": "lab/uno/hello_lab/build/hello_lab.ino.hex",
            "pico_uf2_i2c_hello": "demo_apps/pico/i2c_hello/build/i2c_hello.uf2",
            "uno_hex_i2c_hello": "demo_apps/uno/i2c_hello/build/i2c_hello.ino.hex",
        },
        "tools": {
            "picotool": "/usr/bin/picotool",
            "avrdude": "/usr/bin/avrdude",
        },
        "imports": [
            "cede_labgrid.drivers.picotool_flash",
            "cede_labgrid.drivers.avrdude_flash",
            "cede_labgrid.drivers.cede_validation",
            "cede_labgrid.drivers.cede_reset",
            "cede_labgrid.drivers.cede_i2c",
            "cede_labgrid.strategies.cede_strategy",
        ],
    }

    out_path = repo_root / "env" / "remote.yaml"
    header = textwrap.dedent("""\
        # AUTO-GENERATED by pi_bootstrap.py generate-env -- do not edit manually.
        # Source: lab/config/lab.yaml (exporters section)
        # Regenerate: uv run python lab/pi/bootstrap/pi_bootstrap.py generate-env

    """)
    out_path.write_text(
        header + yaml.safe_dump(env, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {out_path}")


def cmd_generate_places(repo_root: Path, cfg: Path, exporter_name: str | None) -> None:
    """Generate places.yaml and lab/pi/scripts/setup_places.sh."""
    try:
        import yaml
    except ImportError as e:
        raise SystemExit("PyYAML required") from e

    data = load_lab_yaml(cfg)
    validate_schema(repo_root, data)
    exporters = resolve_exporters(data)
    if not exporters:
        raise SystemExit("No exporters defined")
    selected = filter_exporters(exporters, exporter_name)

    places: dict = {}
    script_lines = [
        "#!/usr/bin/env bash",
        "# AUTO-GENERATED by pi_bootstrap.py generate-places -- do not edit manually.",
        "# Idempotently creates LabGrid places on the coordinator.",
        "# Usage: LG_COORDINATOR=host:port bash lab/pi/scripts/setup_places.sh",
        'set -euo pipefail',
        '',
        'LGC="${LGC:-labgrid-client}"',
        '',
    ]

    for exp in selected:
        for res in exp.get("resources", []):
            place = res.get("place")
            if not place:
                continue
            group = res["group"]
            tags = res.get("place_tags", {})

            places[place] = {
                "exporter": exp["name"],
                "group": group,
                "tags": tags,
            }

            script_lines.append(f'# Place: {place} (exporter: {exp["name"]})')
            script_lines.append(f'$LGC -p {place} create 2>/dev/null || true')
            script_lines.append(f'$LGC -p {place} add-match "{exp["name"]}/{group}/*" 2>/dev/null || true')
            for k, v in tags.items():
                script_lines.append(f'$LGC -p {place} set-tags {k}={v}')
            script_lines.append("")

    script_lines.append('echo "Places configured successfully."')

    places_path = repo_root / "places.yaml"
    places_path.write_text(
        "# AUTO-GENERATED by pi_bootstrap.py generate-places -- do not edit manually.\n"
        + yaml.safe_dump(places, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {places_path}")

    script_path = repo_root / "lab" / "pi" / "scripts" / "setup_places.sh"
    script_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")
    script_path.chmod(0o755)
    print(f"wrote {script_path}")


def cmd_generate_all(repo_root: Path, cfg: Path, exporter_name: str | None) -> None:
    """Generate all config artifacts: exporter YAMLs, remote.yaml, places."""
    cmd_generate_exporter_configs(repo_root, cfg, exporter_name)
    cmd_generate_env(repo_root, cfg, exporter_name)
    cmd_generate_places(repo_root, cfg, exporter_name)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _add_exporter_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--exporter",
        type=str,
        default=None,
        metavar="NAME",
        help="Target a specific exporter by name (default: all exporters)",
    )


def main(argv: list[str] | None = None) -> int:
    repo_root = _REPO_ROOT
    default_cfg = resolve_lab_config(repo_root)

    parser = argparse.ArgumentParser(
        description="CEDE Raspberry Pi bootstrap from lab YAML (exporters / raspberry_pi_bootstrap)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_cfg,
        help=f"Lab YAML (default: {default_cfg})",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="Write cloud-init from lab.yaml (per exporter)")
    _add_exporter_arg(p_render)
    p_render.set_defaults(func=lambda a: cmd_render(repo_root, a.config, a.exporter))

    p_flash = sub.add_parser(
        "flash",
        help="Render then flash SD via rpi-imager using os_image.url",
    )
    p_flash.add_argument("--device", required=True, help="Whole disk e.g. /dev/sdc")
    p_flash.add_argument("--yes", action="store_true", required=True)
    _add_exporter_arg(p_flash)
    p_flash.set_defaults(func=lambda a: cmd_flash(repo_root, a.config, a.device, a.yes, a.exporter))

    p_prep = sub.add_parser(
        "prepare-boot",
        help="Render then copy cloud-init to an already-flashed card",
    )
    p_prep.add_argument("--device", required=True)
    p_prep.add_argument("--yes", action="store_true", required=True)
    _add_exporter_arg(p_prep)
    p_prep.set_defaults(func=lambda a: cmd_prepare_boot(repo_root, a.config, a.device, a.yes, a.exporter))

    p_img = sub.add_parser(
        "patch-image",
        help="Render then inject cloud-init into a disk .img (loop-mount boot partition)",
    )
    p_img.add_argument("--image", type=Path, required=True)
    p_img.add_argument("--yes", action="store_true", required=True)
    _add_exporter_arg(p_img)
    p_img.set_defaults(func=lambda a: cmd_patch_image(repo_root, a.config, a.image, a.yes, a.exporter))

    p_fetch = sub.add_parser(
        "fetch-image",
        help="Download os_image.url to os_image.cache_path",
    )
    p_fetch.add_argument("--force", action="store_true", help="Re-download even if cache exists")
    _add_exporter_arg(p_fetch)
    p_fetch.set_defaults(func=lambda a: cmd_fetch_image(repo_root, a.config, a.force, a.exporter))

    p_exp = sub.add_parser(
        "expand-image",
        help="Decompress os_image.cache_path (*.img.xz) to *.img using xz -dk",
    )
    p_exp.add_argument("--force", action="store_true", help="Remove existing .img and decompress again")
    _add_exporter_arg(p_exp)
    p_exp.set_defaults(func=lambda a: cmd_expand_image(repo_root, a.config, a.force, a.exporter))

    p_ff = sub.add_parser(
        "flash-file",
        help="Render then flash a local disk image file (after patch-image / expand-image)",
    )
    p_ff.add_argument("--device", required=True, help="Whole disk e.g. /dev/sdc")
    p_ff.add_argument("--image", type=Path, required=True, help="Path to .img or .img.xz")
    p_ff.add_argument("--yes", action="store_true", required=True)
    _add_exporter_arg(p_ff)
    p_ff.set_defaults(func=lambda a: cmd_flash_file(repo_root, a.config, a.device, a.image, a.yes, a.exporter))

    # --- Generation commands ---
    p_gen_exp = sub.add_parser(
        "generate-exporter-configs",
        help="Generate env/exporters/<name>.yaml for each exporter",
    )
    _add_exporter_arg(p_gen_exp)
    p_gen_exp.set_defaults(func=lambda a: cmd_generate_exporter_configs(repo_root, a.config, a.exporter))

    p_gen_env = sub.add_parser(
        "generate-env",
        help="Generate env/remote.yaml from exporters config",
    )
    _add_exporter_arg(p_gen_env)
    p_gen_env.set_defaults(func=lambda a: cmd_generate_env(repo_root, a.config, a.exporter))

    p_gen_places = sub.add_parser(
        "generate-places",
        help="Generate places.yaml and lab/pi/scripts/setup_places.sh",
    )
    _add_exporter_arg(p_gen_places)
    p_gen_places.set_defaults(func=lambda a: cmd_generate_places(repo_root, a.config, a.exporter))

    p_gen_all = sub.add_parser(
        "generate-all",
        help="Generate all config artifacts (exporter YAMLs, remote.yaml, places)",
    )
    _add_exporter_arg(p_gen_all)
    p_gen_all.set_defaults(func=lambda a: cmd_generate_all(repo_root, a.config, a.exporter))

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
