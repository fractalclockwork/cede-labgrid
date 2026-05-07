# Pre-SD verification and Pi-ish emulation

Goals:

1. **Catch mistakes before flashing** — confirm **`user-data`** / **`meta-data`** are actually on the disk **`.img`** boot partition (same checks help explain **`raspberrypi.lan`**).
2. **Optional QEMU smoke** — boot the raw `.img` far enough to see the kernel/cloud-init on **serial** (not a substitute for real hardware).

---

## Why the Pi showed up as `raspberrypi.lan` instead of `cede-pi.local`

Typical causes:

| Cause | What to check |
|-------|----------------|
| **Cloud-init never ran** | Boot partition missing **`user-data`** / **`meta-data`**, or flash script skipped copying them. Hostname stays the image default **`raspberrypi`**. |
| **Router DNS** | Some routers advertise **`*.lan`** from DHCP client hostname (`raspberrypi`) before mDNS **`cede-pi.local`** matters. |
| **Cloud-init order** | Hostname is applied during cloud-init; very early network/DHCP may still use the old name briefly. |

**Fix:** verify the **boot** partition on the **`.img`** (or SD) contains your rendered files **before** physical boot — see **`verify_boot_image.sh`** below.

---

## A. Offline checks (no root, uses repo `uv` venv)

Render + validate **`lab.yaml`** and sanity-check **`user-data`**:

```bash
cd ~/src/cede
uv sync
make test-config-local
make pi-bootstrap-render
uv run pytest -q lab/tests/test_pi_cloud_init_render.py
```

---

## B. Verify cloud-init **inside** the `.img` (needs `sudo`)

Loops the image, mounts partition **1** read-only, checks **`user-data`** / **`meta-data`**, prints **`hostname:`** line:

```bash
sudo ./lab/pi/scripts/verify_boot_image.sh lab/pi/dist/raspios_trixie_arm64_latest.img
```

Optional: compare to repo **`lab/pi/cloud-init/rendered/`** after **`pi_bootstrap.py render`**:

```bash
uv run python lab/pi/bootstrap/pi_bootstrap.py render
sudo ./lab/pi/scripts/verify_boot_image.sh lab/pi/dist/raspios_trixie_arm64_latest.img --compare-rendered
```

If **`--compare-rendered`** fails, the image on disk does not match what you think you patched — re-run **`patch-image`** or **`prepare-boot`**.

---

## C. QEMU serial smoke (optional; host packages)

Requires **`qemu-system-aarch64`** (e.g. `sudo apt install qemu-system-arm`).

This boots the **same** `.img` using **`kernel8.img`** + a **`.dtb`** taken from its boot partition. **Limitations:**

- Not cycle-accurate Pi hardware; networking inside QEMU is limited — use this for **kernel + cloud-init stage visibility on serial**, not production parity.
- Some OS builds panic if kernel/DTB and `-M` do not match; adjust flags in the script if needed.

```bash
sudo ./lab/pi/scripts/qemu_smoke_rpi_img.sh lab/pi/dist/raspios_trixie_arm64_latest.img
```

Logs serial to **`/tmp/cede-qemu-serial.log`** (override with **`CEDE_QEMU_SERIAL_LOG`**). Exit **`0`** if the log matches **`CEDE_QEMU_SUCCESS_PATTERN`** (default looks for **`cloud-init`** or **`Finished`**).

Increase wait: **`CEDE_QEMU_TIMEOUT_SEC=180`**.

---

## Suggested order before copying to SD

1. **`pi_bootstrap.py render`**
2. **`pytest`** (`test_pi_cloud_init_render.py`)
3. **`patch-image`** on `.img`
4. **`sudo verify_boot_image.sh … --compare-rendered`**
5. *(Optional)* **`qemu_smoke_rpi_img.sh`**
6. **`flash-file`** or **`prepare-boot`**

---

## See also

- [cli-flash.md](../docs/cli-flash.md)
- [ssh-keys-bootstrap.md](../docs/ssh-keys-bootstrap.md)
