# Multi-Exporter Setup

How to add a second (or Nth) LabGrid exporter gateway to the lab.

## Overview

Each exporter is a gateway board (Raspberry Pi, BeagleBone, etc.) with USB-attached MCU targets. All exporters connect to a single LabGrid coordinator and are declared in `lab/config/lab.yaml` under the `exporters` list.

## Steps

### 1. Identify the new gateway's USB serial IDs

Plug the MCU targets into the new gateway board and run:

```bash
udevadm info /dev/ttyACM0 | grep ID_SERIAL_SHORT
udevadm info /dev/ttyACM1 | grep ID_SERIAL_SHORT
```

### 2. Add the exporter to `lab/config/lab.yaml`

```yaml
exporters:
  - name: cede-pi          # existing
    # ... (unchanged) ...

  - name: cede-bbb         # new gateway
    hostname: cede-bbb
    ssh_user: debian
    ssh_host: cede-bbb.local
    location: cede-lab-bench-2
    authorized_keys_file: "~/.ssh/id_ed25519.pub"
    os_image:
      url: "https://..."
      sha256: "..."
      cache_path: "lab/pi/dist/beaglebone_latest.img.xz"
    resources:
      - group: bbb-pico-port
        type: USBSerialPort
        match:
          ID_SERIAL_SHORT: "XXXXXXXXXXXXXXXX"
        speed: 115200
        place: bbb-pico
        place_tags:
          board: pico
      - group: bbb-uno-port
        type: USBSerialPort
        match:
          ID_SERIAL_SHORT: "YYYYYYYYYYYYYYYY"
        speed: 115200
        place: bbb-uno
        place_tags:
          board: uno
```

### 3. Regenerate all config artifacts

```bash
make lg-render-configs
```

This generates:
- `env/exporters/cede-bbb.yaml` -- exporter config for the new gateway
- `env/remote.yaml` -- updated with the new targets and places
- `places.yaml` -- updated with the new places
- `lab/pi/scripts/setup_places.sh` -- updated with place creation commands

### 4. Create places on the coordinator

```bash
LG_COORDINATOR=192.168.1.111:20408 bash lab/pi/scripts/setup_places.sh
```

The script is idempotent; it will skip places that already exist.

### 5. Flash the gateway's SD card

```bash
make lg-bootstrap-sd EXPORTER=cede-bbb DEVICE=/dev/sdc
```

Or render cloud-init and flash manually:

```bash
python3 lab/pi/bootstrap/pi_bootstrap.py render --exporter cede-bbb
python3 lab/pi/bootstrap/pi_bootstrap.py flash --exporter cede-bbb --device /dev/sdc --yes
```

### 6. Boot the gateway

Insert the SD card and power on. Cloud-init will:
1. Set hostname, SSH keys, timezone
2. Install packages (ser2net, picotool, avrdude, i2c-tools, etc.)
3. Create a Python venv and install `labgrid>=25.0`
4. Deploy the exporter config and systemd service
5. Create `/var/cache/labgrid` with proper permissions
6. Start the exporter service

### 7. Verify the exporter

```bash
make lg-verify-exporter EXPORTER=cede-bbb
```

Or manually:

```bash
ssh debian@cede-bbb.local 'systemctl --user status labgrid-exporter.service'
labgrid-client -x 192.168.1.111:20408 resources
```

You should see the new resource groups (`bbb-pico-port`, `bbb-uno-port`) listed.

### 8. Run tests

```bash
make lg-test-pico   # tests all pico places across all exporters
make lg-test-uno    # tests all uno places across all exporters
```

## Architecture

```
lab/config/lab.yaml
  └── exporters:
        ├── cede-pi    → env/exporters/cede-pi.yaml    → Pi gateway
        └── cede-bbb   → env/exporters/cede-bbb.yaml   → BeagleBone gateway
                                    │
                                    ▼
                          labgrid-coordinator (Dev-Host)
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                   cede-pi exporter    cede-bbb exporter
                   ├── cede-pico-port  ├── bbb-pico-port
                   └── cede-uno-port   └── bbb-uno-port
```
