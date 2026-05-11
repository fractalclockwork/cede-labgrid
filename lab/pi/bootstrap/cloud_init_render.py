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


_LABGRID_FINAL_MSG = (
    "CEDE cloud-init finished (SSH; picotool/avrdude/python3; labgrid-exporter). "
    "The exporter connects to the coordinator on startup."
)
_BASE_FINAL_MSG = (
    "CEDE cloud-init finished (SSH; picotool/avrdude/python3). "
    "Do not git clone the full repo on this gateway."
)


def _render_labgrid_write_files(
    ssh_user: str,
    labgrid: dict[str, str],
) -> str:
    """Generate cloud-init write_files entries for the exporter config and systemd unit."""
    coord = labgrid["coordinator_address"]
    exporter_name = labgrid.get("exporter_name", "")
    location = labgrid.get("location", "cede-lab-bench-1")
    pico_serial = labgrid["pico_usb_serial_short"]
    uno_serial = labgrid["uno_usb_serial_short"]

    name_flag = f" --name {exporter_name}" if exporter_name else ""

    exporter_yaml = (
        f"cede-pico-port:\n"
        f"  location: {location}\n"
        f"  USBSerialPort:\n"
        f"    match:\n"
        f"      ID_SERIAL_SHORT: '{pico_serial}'\n"
        f"    speed: 115200\n"
        f"\n"
        f"cede-uno-port:\n"
        f"  location: {location}\n"
        f"  USBSerialPort:\n"
        f"    match:\n"
        f"      ID_SERIAL_SHORT: '{uno_serial}'\n"
        f"    speed: 115200\n"
    )

    systemd_unit = (
        "[Unit]\n"
        "Description=LabGrid Exporter (CEDE Pi Gateway)\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart=%h/labgrid/venv/bin/labgrid-exporter %h/labgrid/exporter.yaml -c {coord}{name_flag}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "Environment=HOME=%h\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )

    home = f"/home/{ssh_user}"
    lines = [
        "write_files:",
        f"  - path: {home}/labgrid/exporter.yaml",
        f"    owner: {ssh_user}:{ssh_user}",
        "    permissions: '0644'",
        "    content: |",
    ]
    for eline in exporter_yaml.splitlines():
        lines.append(f"      {eline}" if eline else "")
    lines.append(f"  - path: {home}/.config/systemd/user/labgrid-exporter.service")
    lines.append(f"    owner: {ssh_user}:{ssh_user}")
    lines.append("    permissions: '0644'")
    lines.append("    content: |")
    for sline in systemd_unit.splitlines():
        lines.append(f"      {sline}" if sline else "")
    lines.append("")
    return "\n".join(lines)


def _render_labgrid_runcmd(ssh_user: str) -> str:
    """Generate cloud-init runcmd entries to create the labgrid venv and enable the exporter."""
    home = f"/home/{ssh_user}"
    cmds = [
        f'  - [ sh, -c, "mkdir -p {home}/labgrid && python3 -m venv {home}/labgrid/venv" ]',
        f'  - [ sh, -c, "{home}/labgrid/venv/bin/pip install --no-cache-dir labgrid>=25.0" ]',
        f'  - [ sh, -c, "mkdir -p {home}/.config/systemd/user" ]',
        f"  - [ loginctl, enable-linger, {ssh_user} ]",
        f'  - [ su, {ssh_user}, -c, "systemctl --user daemon-reload" ]',
        f'  - [ su, {ssh_user}, -c, "systemctl --user enable --now labgrid-exporter.service" ]',
    ]
    return "\n".join(cmds)


def render_cloud_init(
    repo_root: Path,
    *,
    hostname: str,
    ssh_user: str = "pi",
    authorized_keys_file: Path | None = None,
    timezone: str = "UTC",
    locale: str = "en_US.UTF-8",
    wifi: dict[str, str] | None = None,
    labgrid: dict[str, str] | None = None,
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

    if labgrid:
        lg_write_files = _render_labgrid_write_files(ssh_user, labgrid) + "\n"
        lg_runcmd = _render_labgrid_runcmd(ssh_user)
        final_msg = _LABGRID_FINAL_MSG
    else:
        lg_write_files = ""
        lg_runcmd = ""
        final_msg = _BASE_FINAL_MSG

    ud = ud_template
    ud = ud.replace("@@HOSTNAME@@", hostname)
    ud = ud.replace("@@TIMEZONE@@", timezone)
    ud = ud.replace("@@LOCALE@@", locale)
    ud = ud.replace("@@OPTIONAL_SSH_USERS@@", ssh_block)
    ud = ud.replace("@@LABGRID_WRITE_FILES@@\n", lg_write_files)
    ud = ud.replace("@@LABGRID_RUNCMD@@", lg_runcmd)
    ud = ud.replace("@@FINAL_MESSAGE@@", final_msg)

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
