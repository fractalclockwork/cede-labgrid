# Boot images vs container artifacts (PC Dev-Host × Raspberry Pi ARM)

CEDE mixes two different notions of “environment”: **what boots bare metal** versus **what runs inside Docker after boot.** This page grounds the repo layout so **Intel/AMD PCs** and **ARM64 Raspberry Pi gateways** stay mentally distinct.

---

## Summary

| Tier | Typical hardware | Bootable artifact (bare metal) | CEDE portable runtime |
|------|-------------------|-------------------------------|------------------------|
| **Dev-Host** | PC, laptop, NUC, x86_64 VM/CI | **None from this repo** — you install Linux/macOS/Windows + Docker yourself | **OCI images** built from `lab/docker/` targeting **`linux/amd64`** (native on Intel). See [TOOLCHAINS.md](TOOLCHAINS.md). |
| **Gateway** | Raspberry Pi (64-bit OS) | **Raspberry Pi OS Lite arm64** `.img` / `.img.xz` (URL in `lab/config/lab.yaml` → `raspberry_pi_bootstrap.os_image`) | Host OS + Docker on the Pi; optional **`linux/arm64`** orchestration image (`make -C lab/docker build-gateway-images`, etc.). |

Cross-building **`linux/arm64`** containers on an Intel Dev-Host (**QEMU binfmt**) validates **Dockerfile parity** with the gateway; it does **not** replace flashing the Pi **disk image**.

---

## PC / Dev-Host (Intel / AMD64)

- **Boot disk:** Whatever OS image **you** choose for the machine (Ubuntu Desktop, Fedora, WSL2 + Docker, …). CEDE does **not** ship a generic “PC boot ISO.”
- **Reproducible lab tier:** **`docker compose`** / **`make -C lab/docker`** builds images tagged `cede/*:local` with **`docker-compose.platform-amd64.yml`** so the stack is explicitly **`linux/amd64`** on x86_64 hosts.
- **Checks:** `make validate`, `make emulation-environments-test` (native smoke + pytest bundle), CI workflows using the same Dockerfiles.

Use this tier for editors, Git, cross-compilation (Pico/Uno), pytest, and rendering cloud-init **before** touching SD hardware.

---

## Raspberry Pi ARM (gateway)

- **Boot disk:** A single **raw SD/eMMC image** for the Pi: today **Raspberry Pi OS Lite (64-bit)** — download URL and cache path live under **`raspberry_pi_bootstrap.os_image`** (copy from [`lab/config/lab.example.yaml`](../lab/config/lab.example.yaml)).
- **Bootstrap payload (not the OS kernel):** Rendered **`user-data`**, **`meta-data`**, and **`network-config`** (Pi OS **Trixie+** cloud-init path) — hostname, **`enable_ssh`**, SSH keys, packages, Ethernet/DHCP (and optional Wi‑Fi in `network-config`) — injected onto the **FAT boot partition** or baked into the `.img` via project scripts.
- **Operational docs:** [lab/pi/docs/sdcard.md](../lab/pi/docs/sdcard.md), [lab/pi/docs/cli-flash.md](../lab/pi/docs/cli-flash.md), [lab/pi/docs/ssh-keys-bootstrap.md](../lab/pi/docs/ssh-keys-bootstrap.md).
- **Prep on Dev-Host:** `make pi-raw-sd-image` downloads **`os_image.url`** from lab YAML and expands **`*.img.xz` → raw block `*.img`** under `lab/pi/dist/` (gitignored). Flash it with **`make export-raw-dd`** / [`flash_raw_to_device.sh`](../lab/pi/scripts/flash_raw_to_device.sh). For **x86 USB / HDD** bootstrap media (hybrid ISOs and other dd-safe images), use the same helper — see [BOOT_MEDIA_FLASH.md](BOOT_MEDIA_FLASH.md).
- **Pi 3 gateway (Ethernet DHCP + SSH):** configure **`lab/config/lab.yaml`** with **`authorized_keys_file`**, then **`make pi-gateway-sd-ready`** — see [lab/pi/docs/rpi3-gateway-remote.md](../lab/pi/docs/rpi3-gateway-remote.md).
- **Pre-flash verification:** [lab/pi/emulate/README.md](../lab/pi/emulate/README.md) (`verify_boot_image.sh`, optional QEMU).

After first boot, the gateway runs **Docker** (see `lab/pi/bootstrap/bootstrap_pi.sh` direction in docs) and can load the same **ARM64** orchestration image family you cross-built on the Dev-Host.

---

## Pipeline placement

Stages **C–D** in [CONTAINER_BOOTSTRAP.md](CONTAINER_BOOTSTRAP.md) (**bootstrap payload** + **deployable disk image**) are where the **Pi `.img`** and **cloud-init** live. Stages **A–B** are Dev-Host/CI **container** builds and **lab.yaml** contract validation — **no** flashable PC image.

---

## Related

- [BOOT_MEDIA_FLASH.md](BOOT_MEDIA_FLASH.md) — export raw / hybrid images to SD, USB, HDD/NVMe with `make export-raw-dd`  
- [CONTAINER_BOOTSTRAP.md](CONTAINER_BOOTSTRAP.md) — unified stages and gates  
- [TOOLCHAINS.md](TOOLCHAINS.md) — Docker services, platforms, `linux/arm64` emulation on Intel  
- [DESIGN.md](../DESIGN.md) — roles (Dev-Host vs gateway vs MCUs)
