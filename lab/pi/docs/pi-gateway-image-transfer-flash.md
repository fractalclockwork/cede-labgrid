# Pi gateway image — build, transfer, and flash

End-to-end playbook for a **single raw `.img`** with **Ethernet (DHCP)** and **SSH** (via cloud-init), from the Dev-Host through a **bring-up machine** that may only have **`dd`** and baseline tools.

See also: [rpi3-gateway-remote.md](rpi3-gateway-remote.md) (hardware checks, first-boot verification).

---

## 1. Prerequisites (Dev-Host, repo checkout)

1. **`lab/config/lab.yaml`** — copy from `lab/config/lab.example.yaml` and set:
   - **`raspberry_pi_bootstrap.hostname`**
   - **`hosts.pi.ssh_host`** = `<hostname>.local`
   - **`authorized_keys_file`** — uncomment and point at your **public** key for passwordless SSH ([ssh-keys-bootstrap.md](ssh-keys-bootstrap.md))

2. Validate and render:

```bash
make test-config-local
make pi-bootstrap-render
```

---

## 2. Create the image

From the **repository root** (needs **network** for first-time download; **sudo** for loop-mount patch and verification):

```bash
make pi-gateway-sd-ready
```

This runs **download/expand**, **`patch-image`** (inject `user-data` / `meta-data` / `network-config` / empty `ssh`), and **`verify_boot_image.sh … --compare-rendered`** so the `.img` cannot be mistaken for an unpatched upstream image.

Equivalent manual sequence:

```bash
make pi-raw-sd-image   # upstream .img only — not gateway-ready by itself
uv run python lab/pi/bootstrap/pi_bootstrap.py patch-image \
  --image lab/pi/dist/raspios_trixie_arm64_latest.img --yes
sudo ./lab/pi/scripts/verify_boot_image.sh lab/pi/dist/raspios_trixie_arm64_latest.img --compare-rendered
```

(or `make pi-gateway-img-patch` then `make pi-gateway-verify-boot` with default `IMG=`.)

**Artifact** (default path; gitignored):

| File | Description |
|------|-------------|
| **`lab/pi/dist/raspios_trixie_arm64_latest.img`** | Full disk image — flash **entire** SD with `dd` (or `make export-raw-dd`). |

Override basename only if your `lab.yaml` **`os_image.cache_path`** / tooling uses a different **`IMG`** — keep **`IMG=`** consistent for patch and flash.

**Optional:** sanity-check cloud-init on the file before leaving the Dev-Host:

```bash
make pi-verify-boot-img IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
```

---

## 3. Transfer to the bring-up host

The `.img` is large (order of **1–2 GiB** uncompressed depending on release). Pick one path.

### 3a. Removable USB / SSD (simplest)

On the Dev-Host:

```bash
# Mount portable drive at /media/usb (adjust mountpoint)
cp -v lab/pi/dist/raspios_trixie_arm64_latest.img /media/usb/
# Checksum must reference the same basename as on the USB (for sha256sum -c)
( cd /media/usb && sha256sum raspios_trixie_arm64_latest.img > raspios_trixie_arm64_latest.img.sha256 )
sync
```

On the bring-up host (after mount):

```bash
cd /path/to/mounted/usb
sha256sum -c raspios_trixie_arm64_latest.img.sha256
```

### 3b. `scp` over the network

Generate a checksum **on the Dev-Host** so the bring-up host can prove the file matches what left the builder:

```bash
( cd lab/pi/dist && sha256sum raspios_trixie_arm64_latest.img > /tmp/raspios_trixie_arm64_latest.img.sha256 )
scp lab/pi/dist/raspios_trixie_arm64_latest.img /tmp/raspios_trixie_arm64_latest.img.sha256 bringup@bench-host:/var/tmp/
```

On bring-up host:

```bash
cd /var/tmp && sha256sum -c raspios_trixie_arm64_latest.img.sha256
```

### 3c. `rsync` (resume-friendly)

```bash
rsync -avP lab/pi/dist/raspios_trixie_arm64_latest.img bringup@bench-host:/var/tmp/
```

Re-run **`sha256sum`** on the Dev-Host and compare to the copy on the bring-up host if you did not ship a `.sha256` file.

---

## 4. Flash the SD card

**Always** target the **whole disk**, never a partition (`lsblk -p`).

### On a machine **with** this repo (recommended wrapper)

```bash
make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
```

(`make pi-dd-flash …` is the same.)

### On a **minimal** bring-up host (`dd` only)

```bash
lsblk -p
sudo dd if=/var/tmp/raspios_trixie_arm64_latest.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Details and safety notes: [BOOT_MEDIA_FLASH.md](../../../docs/BOOT_MEDIA_FLASH.md).

---

## 5. After flash

1. Eject/unmount safely; insert SD into Pi; **Ethernet** to DHCP LAN; power on.
2. Wait **1–3 minutes** (first boot resize + cloud-init).
3. From the LAN: **`ssh pi@<hostname>.local`** (or IP from the router).

---

## Related

- [rpi3-gateway-remote.md](rpi3-gateway-remote.md) — Pi 3 Model B checklist  
- [BOOT_MEDIA_FLASH.md](../../../docs/BOOT_MEDIA_FLASH.md) — `dd` safety, minimal host  
- [sdcard.md](sdcard.md) — YAML-driven bootstrap overview  
