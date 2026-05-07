# Raspberry Pi serial console (first-boot validation)

Use a **USB–TTL adapter** on the Dev-Host to watch **kernel + cloud-init** on the Pi’s GPIO UART. That validates the semi-automated path (`flash_sdcard.sh` / `prepare_sdcard_boot.sh` + cloud-init) **before** SSH is up—especially when the Pi still shows hostname **`raspberrypi`** or **`ssh` is refused** (cloud-init may not have run).

CEDE’s SD prep scripts append **`enable_uart=1`** to **`config.txt`** on the boot partition when they copy `user-data` / `meta-data`, so the mini-UART on GPIO14/15 is usable on first boot after a prepare or flash that injects cloud-init.

## Wiring (40-pin header — Pi 3 Model B v1.2 and most full-size Pis)

| Signal | GPIO | Physical pin | Connect to USB–TTL |
|--------|------|----------------|-------------------|
| GND | — | 6 (or any GND) | GND |
| UART TX (Pi → host) | GPIO14 | **8** | adapter **RX** |
| UART RX (Pi ← host) | GPIO15 | **10** | adapter **TX** |

**Crossover:** Pi TX (pin 8) goes to the adapter’s **RX**; adapter **TX** goes to Pi RX (pin 10). Use a **3.3 V** logic-level adapter; do not drive 5 V TTL into the Pi’s GPIO. Power the Pi from its normal supply (not from the adapter’s 3.3 V rail).

**26-pin boards** (original Pi 1 Model A/B): same **pin 8 = TX**, **pin 10 = RX** on the smaller header.

## Pi 3 / Bluetooth and `config.txt`

On **Pi 3** (and similar), the **PL011** UART is often tied to **Bluetooth**; GPIO14/15 is typically the **mini-UART**. Without a fixed core clock, the mini-UART baud can drift—**`enable_uart=1`** in `config.txt` fixes the clock so **115200** is stable.

Optional overlays (only if you need the full PL011 on the GPIO pins or have trouble with Bluetooth sharing):

- `dtoverlay=miniuart-bt` — Bluetooth on mini-UART; PL011 on GPIO (common compromise).
- `dtoverlay=disable-bt` — disable Bluetooth; frees PL011 for GPIO serial (if you do not need BT).

See Raspberry Pi documentation on [UART configuration](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts) for your OS release.

## Host: terminal app and settings

**Recommended (Linux):** `picocom`

```bash
sudo picocom -b 115200 /dev/ttyUSB0
```

Replace `/dev/ttyUSB0` with your device (`/dev/ttyACM0`, etc.). Add your user to the **`dialout`** group so `sudo` is not required for every session:

```bash
sudo usermod -aG dialout "$USER"
```

(log out and back in.)

**Alternatives:** `screen /dev/ttyUSB0 115200`, `tio -b 115200 /dev/ttyUSB0`, `minicom`. **Windows:** PuTTY, serial, pick **COMx**, **115200**.

| Setting | Value |
|---------|--------|
| Baud | **115200** |
| Data / parity / stop | **8N1** |
| Flow control | **Off** (unless RTS/CTS are wired) |

Open the serial session **before** powering the Pi if you want to catch the earliest firmware/kernel lines.

## First-boot validation checklist

What you generally want to see on a card prepared with CEDE cloud-init:

1. Firmware / kernel boot messages.
2. **`cloud-init`** stages (e.g. “Running cloud-init …”).
3. **`Cloud-init … finished`** (or equivalent completion).
4. Hostname becomes **`cede-gateway`** (or whatever you passed to `render_cloud_init.sh` / `--hostname`).
5. **`sshd`** listening on port 22 once packages finish (rendered `user-data` installs **`openssh-server`**).

Then from the Dev-Host: `ssh pi@cede-gateway` (or your chosen user).

## When hostname stays `raspberrypi` or SSH is refused

| Symptom | Likely cause |
|---------|----------------|
| Still **`raspberrypi`** | **`user-data` / `meta-data` never reached** the FAT boot partition root, or first boot happened **before** they were copied. |
| **`ssh: Connection refused`** | **`openssh-server`** not installed yet (cloud-init did not run the package list) or first boot still running; less often, sshd disabled. |

**Recovery (no re-flash):** power off the Pi, mount the card on the Dev-Host, then run [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) with the correct **`--device`**, **`--hostname`**, **`--yes`**, and optionally **`--authorized-keys`**. That re-renders cloud-init and copies both files to bootfs; see [cli-flash.md](cli-flash.md) § “Manual Imager write…”.

**Sanity-check on the Dev-Host** (boot partition mounted at `/mnt/rpi-boot`):

```bash
ls -l /mnt/rpi-boot/user-data /mnt/rpi-boot/meta-data
grep -E '^enable_uart=' /mnt/rpi-boot/config.txt || true
```

If boot text never appears, confirm **`config.txt`** contains **`enable_uart=1`** and that **`cmdline.txt`** still includes a serial console for the primary UART, e.g. **`console=serial0,115200`** (Raspberry Pi OS usually ships this; CEDE does not rewrite `cmdline.txt`).

## See also

- [sdcard.md](sdcard.md) — imaging, cloud-init, first boot.
- [cli-flash.md](cli-flash.md) — `flash_sdcard.sh`, `prepare_sdcard_boot.sh`, post-flash steps.
