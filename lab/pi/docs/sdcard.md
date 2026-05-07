# Raspberry Pi SD card: image, hostname, and cloud-init

For a **CLI-oriented** path (`rpi-imager --cli`, `dd`, post-flash cloud-init, and `flash_sdcard.sh`), see [cli-flash.md](cli-flash.md). If you used the **GUI Imager** only and need CEDE **cloud-init** on the card without re-flashing, use [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) on the Dev-Host (documented in cli-flash § “Manual Imager write…”). Interactive **`sudo`** for flash/mount steps is expected and acceptable.

## Recommended: YAML-driven bootstrap (`lab.yaml`)

Declare Raspberry Pi imaging settings once in **`lab/config/lab.yaml`** (copy from [`lab.example.yaml`](../../config/lab.example.yaml); validate with `make -C lab/docker test-config`). Use optional **`raspberry_pi_bootstrap`** for hostname, OS image URL/checksum, timezone/locale, Wi‑Fi (optional), and SSH public keys—aligned with **`hosts.pi.ssh_host`** as `<hostname>.local` when you rely on **mDNS** on the LAN.

| Goal | Command (repo root) |
|------|---------------------|
| **Download + expand** official OS to a **raw block `.img`** (whole-disk image for `dd`; e.g. Pi 3 Model B + **Lite 64-bit** from `os_image`) | `make pi-raw-sd-image` → `lab/pi/dist/*.img` per `cache_path` (large download) |
| **Pi 3 gateway — DHCP + SSH baked into `.img`** (patch boot partition with rendered cloud-init) | `make pi-gateway-sd-ready` after **`lab.yaml`** + **`authorized_keys_file`** — see [rpi3-gateway-remote.md](rpi3-gateway-remote.md) |
| **Write `.img` to SD with `dd`** (whole disk only; destructive) | `make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img` or [`flash_raw_to_device.sh`](../scripts/flash_raw_to_device.sh) (also USB/HDD for hybrid ISOs — see [BOOT_MEDIA_FLASH.md](../../../docs/BOOT_MEDIA_FLASH.md)) |
| Render `user-data` / `meta-data` only | `python3 lab/pi/bootstrap/pi_bootstrap.py render` |
| Same without host PyYAML | `make -C lab/docker pi-bootstrap-render` |
| Same with **uv** at repo root | `uv sync` then `make pi-bootstrap-render` (see [README](../../../README.md) §5) |
| Flash SD from **`os_image.url`** then inject rendered cloud-init | `python3 lab/pi/bootstrap/pi_bootstrap.py flash --device /dev/sdX --yes` (`sudo` only inside the helper for `rpi-imager`) |
| Card already written—inject / refresh cloud-init only | `python3 lab/pi/bootstrap/pi_bootstrap.py prepare-boot --device /dev/sdX --yes` |
| Patch a **cached `.img`** before a single physical write | `python3 lab/pi/bootstrap/pi_bootstrap.py patch-image --image ./image.img --yes` |

The orchestrator validates against [`lab.schema.json`](../../config/lab.schema.json), renders networking so **Ethernet DHCP** works on first boot (primary path), and keeps **USB serial** as an optional troubleshooting path—see [serial-console.md](serial-console.md).

For **SSH public keys** (`authorized_keys_file`), create/test/deploy steps are in [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md).

**Containerized host tools:** `make -C lab/docker build-rpi-imager` then `make -C lab/docker shell-rpi-imager` for an Ubuntu-based image with **`rpi-imager`** and Python deps; **run imaging with `--privileged`** and access to **`/dev`** (see Makefile comment). Orchestration smoke/tests still use `orchestration-dev`; imaging is separate.

## Hardware

This project is tested with a **Raspberry Pi 3 Model B** (1 GiB RAM). Use **Raspberry Pi OS Lite (64-bit)** on a card with enough free space for Docker images you plan to load (8+ GiB class A1 card is a reasonable minimum; larger is better for logs and images).

## 1) Flash the OS (recommended: Raspberry Pi Imager)

### Install Imager on your Dev-Host

**Linux (apt):** CEDE assumes a Linux Dev-Host. Install Raspberry Pi Imager from your distro repositories:

```bash
sudo apt install rpi-imager
```

If the package is missing, refresh indexes first (`sudo apt update`) and retry. On some distributions the package may live in the **universe** (or equivalent) component—enable that repo if needed.

Launch Imager from your application menu or run **`rpi-imager`** in a terminal.

**Windows / macOS / other Linux:** use installers from [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/) (official Raspberry Pi downloads for Imager and OS images).

### Write the card

1. Start **Raspberry Pi Imager**.
2. Choose **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**.
3. Select your SD card / reader as storage (double-check the device).
4. Open the **gear icon (OS customization)** *before* clicking Write:
   - **Hostname:** e.g. `cede-pi` (must match **`lab.yaml`** `hosts.pi.ssh_host` as `cede-pi.local` when using mDNS, or match **`raspberry_pi_bootstrap.hostname`**).
   - Enable **SSH** (password or public key).
   - Set user/password or SSH keys.
   - Optionally configure Wi‑Fi if not using Ethernet.
5. Click **Write** and wait until verification finishes.

Eject the card safely, insert it into the Pi, and power on.

**After a manual Write with Imager only:** Imager does **not** run CEDE’s `render_cloud_init.sh` or copy `user-data` / `meta-data` to bootfs. Either customize in Imager (gear icon) as above, or leave the card inserted on the Dev-Host and run [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) (see [cli-flash.md](cli-flash.md) § “Manual Imager write…”) so the gateway hostname and cloud-init match this repo—**do not** re-run `flash_sdcard.sh` unless you intend to **re-image** the card.

**Imaging time:** there is no fixed duration for a given OS image; the Imager **100%** mark is the end of the main progress phase, not always an instant return to the shell. See [cli-flash.md](cli-flash.md) § “How long it takes, and what 100% means”.

**Using the full SD card:** Partition layout **before** flashing is irrelevant once **`rpi-imager`** finishes—inspect the card again with **`fdisk -l`** / **`lsblk`** after writing. Imager usually fills the card; root ext4 may still grow on first boot. See [cli-flash.md](cli-flash.md) § “Using the full SD card”.

## 2) Optional: cloud-init files on the boot partition

If you prefer **`cloud-init`** instead of (or in addition to) Imager fields:

From the **cede** repo on your Dev-Host:

```bash
chmod +x lab/pi/bootstrap/render_cloud_init.sh
./lab/pi/bootstrap/render_cloud_init.sh cede-gateway
```

This writes `lab/pi/cloud-init/rendered/user-data` and `meta-data`. Copy both to the **bootfs** root of the flashed card (same partition as `config.txt`; paths vary slightly between firmware layouts—often `/boot/firmware/` after boot).

To inject the Dev-Host’s **SSH public key** for passwordless login (recommended with Ethernet), pass **`AUTHORIZED_KEYS_FILE`** when rendering (see [`render_cloud_init.sh`](../bootstrap/render_cloud_init.sh)), or use **`prepare_sdcard_boot.sh` / `flash_sdcard.sh`** with **`--authorized-keys`** (documented in [cli-flash.md](cli-flash.md)).

If you **already** copied `user-data` and `meta-data` once and only need to **add keys**, re-render with **`AUTHORIZED_KEYS_FILE`** set and copy the new **`user-data`** onto boot again — see [cli-flash.md](cli-flash.md) § “Already copied user-data / meta-data without keys”.

If Imager already set hostname/user/SSH, **either** rely on Imager **or** use rendered cloud-init—avoid conflicting duplicate hostname definitions and duplicate SSH key injection for the same user.

## 3) First boot and full bootstrap

**Typical path:** connect **Ethernet**, wait for cloud-init to finish, then **SSH** to `hosts.pi.ssh_host` (often `<hostname>.local`). Serial console is **optional** (bring-up and debugging only)—see [serial-console.md](serial-console.md).

1. Boot the Pi with Ethernet (or Wi‑Fi if configured under **`raspberry_pi_bootstrap.wifi`**).
2. SSH in as your user.
3. Clone or rsync this repository onto the Pi (e.g. `~/cede`).
4. Run the gateway installer (hostname must match your choice):

```bash
cd ~/cede
chmod +x lab/pi/bootstrap/bootstrap_pi.sh
sudo ./lab/pi/bootstrap/bootstrap_pi.sh --hostname cede-pi
```

This installs **Docker**, **Arduino CLI** (user-local), **Python** orchestration dependencies, enables **I2C**, and configures groups for serial/USB.

Log out and back in (or reboot) so **docker** and **dialout** groups apply.

## 4) Load ARM64 toolchain images (optional)

Dev-Host images are typically **amd64**. On the Dev-Host, build **linux/arm64** orchestration for the gateway:

```bash
# If `docker buildx build ... arm64` fails with "exec format error" on an amd64 PC:
make -C lab/docker setup-binfmt

make -C lab/docker build-gateway-images
make -C lab/docker save-gateway-orchestration   # writes lab/pi/dist/orchestration-dev_arm64.tar.gz
```

Copy the tarball to the Pi and load:

```bash
gzip -dc orchestration-dev_arm64.tar.gz | docker load
```

Then run tests inside the container per `lab/docker/docker-compose.gateway.yml`.

## 5) HDMI dashboard (later)

See [dashboard-hdmi.md](dashboard-hdmi.md) for a kiosk-style path (Chromium + URL) when you add Grafana or another web UI.
