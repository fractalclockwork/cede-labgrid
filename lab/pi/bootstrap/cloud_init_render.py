#!/usr/bin/env python3
"""Render lab/pi/cloud-init templates into lab/pi/cloud-init/rendered/."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _read_ssh_keys(keys_file: Path) -> list[str]:
    keys: list[str] = []
    for line in keys_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.append(line)
    if not keys:
        raise SystemExit(f"error: no ssh public keys found in {keys_file}")
    return keys


# Pi OS default-style supplementary groups + passwordless sudo (cloud-init must set these when the
# user stanza is present; a minimal entry with only ssh_authorized_keys can leave 'pi' without sudo).
_PI_GATEWAY_GROUPS = (
    "users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,"
    "gpio,spi,i2c,render,disk,sudo"
)


def _render_optional_ssh_users_block(ssh_user: str, keys: list[str]) -> str:
    lines = [
        "users:",
        f"  - name: {ssh_user}",
        f"    groups: {_PI_GATEWAY_GROUPS}",
        "    shell: /bin/bash",
        "    sudo: ALL=(ALL) NOPASSWD:ALL",
        "    ssh_authorized_keys:",
    ]
    for k in keys:
        escaped = k.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'      - "{escaped}"')
    lines.append("")
    return "\n".join(lines)


def _network_config_dict(wifi: dict[str, str] | None) -> dict:
    """Netplan-style payload for Raspberry Pi OS `network-config` on the boot partition."""
    ethernets = {"eth0": {"dhcp4": True, "optional": True}}
    net: dict = {
        "version": 2,
        "renderer": "NetworkManager",
        "ethernets": ethernets,
    }
    if wifi:
        country = (wifi.get("country") or "US").strip().upper()[:2]
        net["wifis"] = {
            "wlan0": {
                "dhcp4": True,
                "optional": True,
                "regulatory-domain": country,
                "access-points": {wifi["ssid"]: {"password": wifi["psk"]}},
            }
        }
    return {"network": net}


def _render_network_config_file(wifi: dict[str, str] | None) -> str:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as e:
        raise SystemExit(
            "cloud_init_render.py requires PyYAML (e.g. apt install python3-yaml or pip install pyyaml)"
        ) from e

    blob = yaml.safe_dump(
        _network_config_dict(wifi),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return blob.rstrip() + "\n"


def render_cloud_init(
    repo_root: Path,
    *,
    hostname: str,
    ssh_user: str = "pi",
    authorized_keys_file: Path | None = None,
    timezone: str = "UTC",
    locale: str = "en_US.UTF-8",
    wifi: dict[str, str] | None = None,
    out_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Write user-data, meta-data, and network-config under cloud-init/rendered/."""
    out = out_dir or (repo_root / "lab/pi/cloud-init/rendered")
    out.mkdir(parents=True, exist_ok=True)

    template_dir = repo_root / "lab/pi/cloud-init"
    ud_template = (template_dir / "user-data.template").read_text(encoding="utf-8")
    md_template_path = template_dir / "meta-data.template"
    md_template = md_template_path.read_text(encoding="utf-8") if md_template_path.exists() else ""

    ssh_block = ""
    if authorized_keys_file is not None:
        keys = _read_ssh_keys(authorized_keys_file)
        ssh_block = _render_optional_ssh_users_block(ssh_user, keys)

    ud = ud_template
    ud = ud.replace("@@HOSTNAME@@", hostname)
    ud = ud.replace("@@TIMEZONE@@", timezone)
    ud = ud.replace("@@LOCALE@@", locale)
    ud = ud.replace("@@OPTIONAL_SSH_USERS@@", ssh_block)

    ud_path = out / "user-data"
    ud_path.write_text(ud, encoding="utf-8")

    md_path = out / "meta-data"
    if md_template:
        md_path.write_text(md_template.replace("@@HOSTNAME@@", hostname), encoding="utf-8")

    nc_path = out / "network-config"
    nc_path.write_text(_render_network_config_file(wifi), encoding="utf-8")

    return ud_path, md_path, nc_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render CEDE cloud-init user-data and meta-data.")
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repository root (default: inferred from script location)",
    )
    parser.add_argument("hostname", nargs="?", help="Pi hostname (short name, for cloud-init)")
    parser.add_argument("--ssh-user", default=os.environ.get("SSH_USER", "pi"))
    parser.add_argument("--authorized-keys", type=Path, dest="authorized_keys", metavar="FILE")
    parser.add_argument("--timezone", default=os.environ.get("CEDE_TIMEZONE", "UTC"))
    parser.add_argument("--locale", default=os.environ.get("CEDE_LOCALE", "en_US.UTF-8"))
    parser.add_argument("--wifi-ssid", default=os.environ.get("CEDE_WIFI_SSID", ""))
    parser.add_argument("--wifi-psk", default=os.environ.get("CEDE_WIFI_PSK", ""))
    parser.add_argument("--wifi-psk-file", type=Path, dest="wifi_psk_file", metavar="FILE")
    parser.add_argument(
        "--out",
        type=Path,
        dest="out_dir",
        metavar="DIR",
        help="Output directory (default: lab/pi/cloud-init/rendered)",
    )
    args = parser.parse_args(argv)

    repo = args.repo or _repo_root_from_here()
    hostname = args.hostname or os.environ.get("CEDE_HOSTNAME", "")
    if not hostname:
        parser.error("hostname is required (positional or CEDE_HOSTNAME)")

    ak = args.authorized_keys
    if ak is None and os.environ.get("AUTHORIZED_KEYS_FILE"):
        akPath = Path(os.environ["AUTHORIZED_KEYS_FILE"]).expanduser()
        if akPath.is_file():
            ak = akPath

    wifi: dict[str, str] | None = None
    if args.wifi_ssid:
        psk = args.wifi_psk
        if args.wifi_psk_file:
            if psk:
                parser.error("use either --wifi-psk or --wifi-psk-file, not both")
            psk = args.wifi_psk_file.read_text(encoding="utf-8").strip()
        if not psk:
            parser.error("Wi-Fi SSID set; provide --wifi-psk or --wifi-psk-file")
        wifi = {"ssid": args.wifi_ssid, "psk": psk}

    ud, md, nc = render_cloud_init(
        repo,
        hostname=hostname,
        ssh_user=args.ssh_user,
        authorized_keys_file=ak,
        timezone=args.timezone,
        locale=args.locale,
        wifi=wifi,
        out_dir=args.out_dir,
    )
    print(f"wrote {ud}")
    print(f"wrote {md}")
    print(f"wrote {nc}")
    print("")
    print(f"Copy {ud}, {md}, and {nc} to the SD card boot partition (see lab/pi/docs/sdcard.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
