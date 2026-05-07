# Exporting boot images to physical media (Pi SD, x86 USB, disks)

CEDE provides a **small `dd` wrapper** — [`lab/pi/scripts/flash_raw_to_device.sh`](../lab/pi/scripts/flash_raw_to_device.sh) — to copy a **file** that is already a **raw block image** (or a **hybrid ISO** meant for `dd`) onto a **whole** Linux block device. The same tool applies whether the target is an **SD card**, a **USB thumb drive**, an **SSD in a USB enclosure**, or an **internal SATA/NVMe** disk node such as `/dev/nvme0n1` **when you intentionally erase that disk**.

---

## When `dd` is appropriate

| Artifact | Typical use |
|----------|-------------|
| **Raspberry Pi OS** `.img` (after decompressing `.img.xz`) | Pi SD card — see `make pi-raw-sd-image` → [`BOOT_IMAGES.md`](BOOT_IMAGES.md). |
| **Hybrid Linux installer / live ISO** (many Ubuntu/Debian images marked dd-able by upstream) | x86/amd64 **USB** installer or live USB. |
| **Raw appliance / cloud `.img`** | Only if the publisher documents **full-disk `dd`** — never assume. |

If the vendor says “copy files to a FAT partition” or supplies a **Windows-only** flasher, **`dd` is usually wrong** — follow their docs.

---

## Commands

**Makefile (repo root):**

```bash
make export-raw-dd DEVICE=/dev/sdX IMG=/path/to/image.img
# Pi convenience image from lab YAML:
make pi-raw-sd-image
make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
```

`make pi-dd-flash …` is an **alias** of `export-raw-dd`.

**Script directly:**

```bash
sudo ./lab/pi/scripts/flash_raw_to_device.sh --device /dev/sdX --image ~/Downloads/foo.iso --yes
```

Set **`CEDE_DD_DELAY_SEC=0`** to skip the default pre-write delay (e.g. automation).

If **`dd` finishes copying** then fails with **`fsync failed … Input/output error`**, the USB reader, cable, port, or SD card often faults on the **final flush** (fake-size cards, weak power). Check **`sudo dmesg | tail`** for `USB`/`I/O`/`mmc` errors; try another **port**, **reader**, or **card**. Retry with **`CEDE_DD_NO_FSYNC=1`** (skips **`conv=fsync`** inside the script; **`sync`** still runs afterward):

```bash
CEDE_DD_NO_FSYNC=1 make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
```

Plain `dd` without `conv=fsync`:

```bash
sudo dd if=… of=/dev/sdX bs=4M status=progress
sudo sync && sudo sync
```

---

## Minimal bring-up host

Some benches only run a **stock Linux** with **`dd`**, **`sync`**, **`lsblk`** / **`fdisk`**, and **`sudo`** — no checkout of this repo, no `make`, no Python/`uv`. That is enough if you already have a **final raw `.img`** (or hybrid ISO) on disk or USB.

1. **Elsewhere** (dev machine or CI): produce or download the artifact — e.g. `make pi-gateway-sd-ready` or copy a ready `.img` onto portable media.
2. **On the minimal host**: identify the **whole** block device (`lsblk -p`; use `/dev/sdX`, `/dev/mmcblk0`, etc., **not** `…p1`).
3. **Write** (same `dd` line as [`flash_raw_to_device.sh`](../lab/pi/scripts/flash_raw_to_device.sh); destructive):

```bash
sudo dd if=/path/to/image.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Wrong `of=` **erases** that disk — confirm **MODEL**, **SIZE**, and **RM** (removable) before running.

---

## Choosing `--device`

- Use **`lsblk -p`** and verify **MODEL**, **SIZE**, and **RM** (removable).
- Pass the **whole disk**: `/dev/sdc`, `/dev/mmcblk0`, `/dev/nvme0n1` — **not** `/dev/sdc1` or `/dev/nvme0n1p1`.
- Wrong `--device` **destroys** whatever disk you pointed at.

Internal laptop disks are easy to overwrite by mistake — triple-check before `--yes`.

---

## Related

- [BOOT_IMAGES.md](BOOT_IMAGES.md) — PC vs Pi artifacts  
- [lab/pi/docs/pi-gateway-image-transfer-flash.md](../lab/pi/docs/pi-gateway-image-transfer-flash.md) — build Pi gateway `.img`, move it, flash  
- [lab/pi/docs/cli-flash.md](../lab/pi/docs/cli-flash.md) — Pi-focused paths including Imager and `patch-image`  
- [lab/pi/docs/sdcard.md](../lab/pi/docs/sdcard.md) — YAML-driven Pi bootstrap  
