# CLI / scripted Raspberry Pi imaging

The graphical **Raspberry Pi Imager** is optional: you can script the **write** step and apply **headless** configuration by patching the **boot partition** (cloud-init, SSH enable, etc.). This matches CEDE’s [`cloud-init` templates](../cloud-init/) and [`render_cloud_init.sh`](../bootstrap/render_cloud_init.sh).

**YAML-first (recommended):** Put **`raspberry_pi_bootstrap`** and **`hosts.pi`** in [`lab/config/lab.yaml`](../../config/lab.example.yaml), then drive render/flash from one entrypoint:

```bash
# Validate config
make -C lab/docker test-config

# Render cloud-init (or: make -C lab/docker pi-bootstrap-render)
python3 lab/pi/bootstrap/pi_bootstrap.py render

# Flash SD using os_image.url from lab.yaml, then copy rendered files (prompts for sudo when flashing)
python3 lab/pi/bootstrap/pi_bootstrap.py flash --device /dev/sdX --yes

# Card already imaged—only patch boot (same as prepare_sdcard_boot after render)
python3 lab/pi/bootstrap/pi_bootstrap.py prepare-boot --device /dev/sdX --yes
```

Under the hood, `flash` / `prepare-boot` call [`flash_sdcard.sh`](../scripts/flash_sdcard.sh) / [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) with **`--use-existing-rendered`** after validating and rendering from YAML (so Wi‑Fi, timezone, and keys stay in sync without repeating flags).

**Cached disk image:** Download the `.img.xz` once, optionally [`patch_image_boot.sh`](../scripts/patch_image_boot.sh) or `pi_bootstrap.py patch-image`, then flash the modified image once.

**Operator model:** Many steps need **`sudo`** (flash, `mount`, `partprobe`, `sync`). **Manually running those commands** when prompted—or typing `sudo` yourself for each block—is **fine**; nothing here requires passwordless automation unless you choose to configure it.

## `rpi-imager` CLI mode

Debian/Ubuntu packages ship a non-GUI mode (see [rpi-imager(1)](https://manpages.ubuntu.com/manpages/noble/man1/rpi-imager.1.html)):

```bash
sudo rpi-imager --cli [--sha256 <expected-hash>] [--disable-verify] [--quiet] <image-uri> <destination-device>
```

- **`image-uri`**: path to a local `.img` / `.img.xz`, or an **`http://` / `https://` URL**.
- **`destination-device`**: the **whole** block device (e.g. `/dev/mmcblk0`, `/dev/sde`), **not** a partition (`/dev/mmcblk0p1` is wrong).
- **`--sha256`**: verify the image before writing (recommended for automation).
- **OS customization** from the Imager GUI (hostname, user, Wi‑Fi) is **not** exposed as CLI flags; use **cloud-init** or mount-and-patch after the write (below).

Example (replace the URL with the current **Raspberry Pi OS Lite (64-bit)** link from [downloads](https://www.raspberrypi.com/software/operating-systems/) and the checksum from the same page):

```bash
sudo rpi-imager --cli \
  --sha256 '<paste-sha256-from-download-page>' \
  'https://downloads.raspberrypi.com/raspios_lite_arm64/images/.../...img.xz' \
  /dev/mmcblk0
```

### How long it takes, and what “100%” means

There is **no single baseline** for how long a given image (e.g. `raspios_lite_arm64/.../raspios-trixie-arm64-lite.img.xz`) takes to flash. Time depends on **image size**, **`.xz` decompression CPU**, **HTTPS download** speed if not cached, **USB SD reader** and cable, **card speed**, other **disk I/O** on the host, and whether verification runs. An **external USB card reader** is often **slower** than a good built-in SD slot; long runtimes are normal if the job completes and partitions look correct afterward.

The progress bar reaching **`100%`** usually means the utility has reached the end of its **main write/download meter**—not necessarily that **every** kernel flush has finished, that **`rpi-imager`** will **exit immediately**, or that nothing else is pending (USB teardown, parent `sudo`, etc.). Treat **“really done”** as: the **shell returns**, `lsblk` shows **boot + root** partitions, and the reader’s activity indicator has gone idle.

For your own machine, run **`time sudo rpi-imager --cli ...`** once and keep that as an informal reference—not a guarantee for the next OS revision or reader.

**Stuck at `100%`, or `ps` shows `[rpi-imager] <defunct>` (zombie):** the `rpi-imager` process has **already exited**; a **zombie** means the parent (often `sudo`) has not reaped it yet. The image write has usually **finished**; the session can look hung because of **console/TTY** handling, not because bytes are still streaming.

1. In another terminal: **`lsblk /dev/sdX`** and **`sudo fdisk -l /dev/sdX`** — if you see **boot + root** partitions, the card was written.
2. Flush buffers for **only** the SD reader (see **Large disks & `sync`** below). Avoid bare **`sudo sync`** on a workstation with **Docker images / big disks**—that flushes **every** block device and can take **many minutes**, feeling like a hang.
3. For the **next** flash from an interactive terminal, detach stdin so Qt CLI does not wait on the TTY:

```bash
sudo rpi-imager --cli --disable-verify '<url>' /dev/sdX </dev/null
```

CEDE’s [`flash_sdcard.sh`](../scripts/flash_sdcard.sh) runs Imager with **`</dev/null`** for this reason.

### Large disks, Docker, and `sync`

On a typical Dev-Host, **`sudo sync`** with **no arguments** asks the kernel to flush **all** dirty buffers on **all** mounted filesystems—NVMe storage, Docker overlay volumes, bind mounts, etc. That can run for a **long** time and look like the terminal is stuck (including after **`rpi-imager`** appears done).

To flush **only** the SD card / USB reader block device (replace with your device):

```bash
sudo blockdev --flushbufs /dev/sdc
```

Then eject or unplug when the hardware allows. Use **global** `sync` only when you intentionally want everything flushed.

Then apply cloud-init (next section) or run [`flash_sdcard.sh`](../scripts/flash_sdcard.sh).

## Option: `wget` / `curl` + `dd` (no Imager)

1. Download the `.img.xz` and a checksum file or published SHA256 from [Raspberry Pi OS](https://www.raspberrypi.com/software/operating-systems/).
2. Verify: `echo '<hash>  <filename>' | sha256sum -c -` (or `sha256sum` the decompressed `.img` after `xz -d`).
3. Write (example — **triple-check `of=`**):

```bash
# xzcat streams to dd; OF must be your SD reader block device
sudo xzcat ./2026-04-21-raspios-trixie-arm64-lite.img.xz | sudo dd of=/dev/mmcblk0 bs=4M conv=fsync status=progress
```

Or decompress first, then `sudo dd if=...img of=/dev/mmcblk0 bs=4M conv=fsync status=progress`.

**CEDE helper** (same `dd`, with whole-disk checks and a short confirmation delay).  
Works for **Pi `.img`** and other **raw / hybrid-dd** images (many Linux ISOs on **x86 USB** sticks — see [BOOT_MEDIA_FLASH.md](../../../docs/BOOT_MEDIA_FLASH.md)):

```bash
# After: make pi-raw-sd-image   → lab/pi/dist/*.img
sudo ./lab/pi/scripts/flash_raw_to_device.sh \
  --device /dev/sdX \
  --image "$(pwd)/lab/pi/dist/raspios_trixie_arm64_latest.img" \
  --yes
```

From repo root with **GNU make**:

```bash
make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
# alias: make pi-dd-flash …
```

**Risk:** `dd` to the wrong `of=` destroys disks. Prefer explicit variables and a confirmation guard (see `flash_sdcard.sh --yes`).

## Using the full SD card (grow root to fill the media)

**Before vs after imaging:** Whatever **`fdisk -l /dev/sdc`** showed **before** you ran **`rpi-imager`** (old partitions from an earlier image, or no partitions on a blank card) is **not** what defines the final layout. **`rpi-imager`** replaces the partition table and filesystems with whatever the chosen `.img` expects, usually sizing partitions to fill the SD card.

**After imaging completes**, **`sudo fdisk -l /dev/sdc`** should list **`Device …`** rows for each partition (names like **`sdc1`**, **`sdc2`, …** on a USB reader). Typical Raspberry Pi OS Lite (arm64) layouts include a **small FAT boot** partition (cloud-init / **`config.txt`** live here), often **swap**, and a **Linux root** partition occupying most of the disk—the exact scheme varies by OS release (Bookworm vs Trixie, etc.).

If you **only** see disk summary lines (size, sectors, model) and **no partition table**, refresh the kernel view and recheck:

```bash
sudo partprobe /dev/sdc
sudo fdisk -l /dev/sdc
lsblk /dev/sdc
```

Unplug/replug the USB reader if needed; confirm the **`rpi-imager`** write reached **100 %** without errors.

The **ext4** root filesystem may still grow on **first boot** (online resize) even when partitions already span the card.

**Verify after first login:**

```bash
lsblk
df -h /
```

If **`/`** does not show nearly the full size of `sdc3`, expand manually (pick the root partition device from `lsblk`, e.g. `/dev/mmcblk0p3` on the Pi or whatever maps from your SD layout):

```bash
sudo raspi-config nonint do_expand_rootfs
# or, if growpart is available and partition still small:
# sudo growpart /dev/sdX 3 && sudo resize2fs /dev/sdX3
```

CEDE’s rendered **[`user-data.template`](../cloud-init/user-data.template)** includes **`resize_rootfs: true`** and **`growpart`** so **cloud-init** can grow the root partition and filesystem on first boot when you inject cloud-init before the initial boot. Re-render after pulling the template update: `./lab/pi/bootstrap/render_cloud_init.sh <hostname>`.

## Post-flash: mount boot and add cloud-init

After imaging, the **first FAT partition** is usually the firmware/boot filesystem (`config.txt`, etc.) — e.g. **`/dev/sdc1`** when the base device is **`/dev/sdc`** (USB reader).

1. Re-scan partitions: `sudo partprobe /dev/mmcblk0` (or unplug/replug the reader).
2. Pick the boot partition name:
   - If the base device is **`/dev/mmcblk0`** → first partition is **`/dev/mmcblk0p1`**.
   - If **`/dev/sde`** → **`/dev/sde1`**.
   - **`nvme0n1`** → **`nvme0n1p1`**.
3. Mount and copy rendered cloud-init files:

```bash
sudo mkdir -p /mnt/rpi-boot
sudo mount /dev/mmcblk0p1 /mnt/rpi-boot   # adjust partition

# From repo root, after: ./lab/pi/bootstrap/render_cloud_init.sh cede-gateway
sudo cp lab/pi/cloud-init/rendered/user-data /mnt/rpi-boot/
sudo cp lab/pi/cloud-init/rendered/meta-data /mnt/rpi-boot/

# Prefer device-scoped flush (avoid slow global `sync` on Docker/large disks):
sudo blockdev --flushbufs /dev/sdX
sudo umount /mnt/rpi-boot
```

On **Raspberry Pi OS Lite (Bookworm)** cloud-init is supported for headless setup; confirm against your exact image release notes.

### Already copied `user-data` / `meta-data` without keys: add `authorized-keys` (alternate path)

If you **already** imaged the card and copied `lab/pi/cloud-init/rendered/user-data` and `meta-data` to the boot partition **without** passing `AUTHORIZED_KEYS_FILE` (or before that feature), you can **continue from here** without re-flashing:

1. **Re-render** with the **same hostname** you used the first time (so `meta-data` and your Pi’s expected name stay aligned):

   ```bash
   cd ~/src/cede   # or your clone path
   AUTHORIZED_KEYS_FILE="$HOME/.ssh/id_ed25519.pub" \
     ./lab/pi/bootstrap/render_cloud_init.sh cede-gateway
   ```

   Use the same **`<hostname>`** as in your original `render_cloud_init.sh` run. Optional: `SSH_USER=youruser` if the account is not `pi` (see [`render_cloud_init.sh`](../bootstrap/render_cloud_init.sh)).

2. **Remount** the FAT boot partition (see the numbered steps in § “Post-flash” above) if it is not already mounted.

3. **Overwrite only what changed:** keys live in **`user-data`** — copy the regenerated file:

   ```bash
   sudo cp lab/pi/cloud-init/rendered/user-data /mnt/rpi-boot/
   ```

   Copy **`meta-data`** too only if you changed the hostname or re-rendered and want both files in sync; otherwise it is unchanged.

4. **Flush and unmount** the whole disk (same as above):

   ```bash
   sudo blockdev --flushbufs /dev/sdX   # whole disk, e.g. /dev/sdc not sdc1
   sudo umount /mnt/rpi-boot
   ```

**Equivalent automation:** if the SD is still in the reader under Linux, you can instead run [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) with the same **`--device`**, **`--hostname`**, **`--yes`**, and **`--authorized-keys`** — it re-runs `render_cloud_init.sh` and copies both files, which is idempotent when the hostname matches.

## Patch image file before writing (golden image)

For CI or repeatable artifacts:

1. Render cloud-init (`pi_bootstrap.py render` or [`render_cloud_init.sh`](../bootstrap/render_cloud_init.sh)).
2. Run [`patch_image_boot.sh`](../scripts/patch_image_boot.sh) **or** `python3 lab/pi/bootstrap/pi_bootstrap.py patch-image --image ./image.img --yes` (loop-mounts partition 1, copies `user-data` / `meta-data`, enables UART in `config.txt`).
3. Flash the modified `.img` once: `sudo rpi-imager --cli … ./image.img /dev/sdX`

Equivalent manual steps: `losetup -Pf ./image.img`, mount `…p1`, copy files, `losetup -d`. Layout assumptions match typical Raspberry Pi OS images (FAT boot first).

Heavier to maintain when partition layouts change.

## One-shot automation

Prefer **`pi_bootstrap.py flash`** (reads **`lab.yaml`**). Lower-level: [`flash_sdcard.sh`](../scripts/flash_sdcard.sh) flashes via `rpi-imager --cli`, optionally **`--hostname`** and cloud-init copy ( **`--authorized-keys`** for passwordless SSH), or **`--use-existing-rendered`** after a separate render step.

## Manual Imager write, then inject cloud-init on the host

If you already wrote the card with **Raspberry Pi Imager** (GUI or CLI: “Write successful”) and only need CEDE’s rendered **cloud-init** on the boot partition, **do not** run [`flash_sdcard.sh`](../scripts/flash_sdcard.sh) again—it invokes `rpi-imager` and would **re-flash** the device. Use the **prepare-only** script [`prepare_sdcard_boot.sh`](../scripts/prepare_sdcard_boot.sh) instead:

```bash
sudo ./lab/pi/scripts/prepare_sdcard_boot.sh --device /dev/sdc --hostname cede-gateway --yes \
  --authorized-keys /home/you/.ssh/id_ed25519.pub
```

Use **`--authorized-keys`** with the Dev-Host’s **public** key (one or more lines in a `.pub` file). Keys are written into rendered **`user-data`** as cloud-init `users[].ssh_authorized_keys` for user **`pi`** by default (override with **`--ssh-user`** if your image uses a different login). That gives passwordless SSH over Ethernet on first boot once cloud-init finishes.

When you run **`sudo`**, `~` may expand to **root’s** home—prefer **`$HOME/.ssh/...`** from a normal shell or an absolute path.

Pass the **whole-disk** device (e.g. `/dev/sdc`, not `/dev/sdc1`). The script runs `partprobe`, mounts the FAT **boot** partition (same naming rules as `flash_sdcard.sh`), runs [`render_cloud_init.sh`](../bootstrap/render_cloud_init.sh) for the given hostname, copies `user-data` / `meta-data`, runs **`blockdev --flushbufs`** on the disk (not a global `sync`), then umounts.

[`flash_sdcard.sh`](../scripts/flash_sdcard.sh) accepts the same **`--authorized-keys`** / **`--ssh-user`** options when **`--hostname`** is set.

Convenience from the repo (still runs `sudo` under the hood):

```bash
make -C lab/pi prepare-sdcard DEVICE=/dev/sdc HOSTNAME=cede-gateway AUTHORIZED_KEYS=/home/you/.ssh/id_ed25519.pub
```

### Remote host with the SD reader

To drive the machine that has the USB reader from **another** computer over SSH, use a login shell or ensure `cd` is correct. If **`sudo`** prompts for a password, allocate a TTY with **`-t`**:

```bash
ssh -t user@dev-host 'cd ~/src/cede && sudo ./lab/pi/scripts/prepare_sdcard_boot.sh --device /dev/sdc --hostname cede-gateway --yes --authorized-keys "$HOME/.ssh/id_ed25519.pub"'
```

### USB readers and `dmesg` (“capacity … to 0”)

Kernel messages such as **`detected capacity change from … to 0`** for the SD reader often mean the **reader lost the card** or was **unplugged**. Before prepare, confirm **`lsblk /dev/sdX`** lists **partitions** (`sdX1`, `sdX2`, …). If the device is empty or keeps disappearing, **replug** the reader or re-seat the card until `lsblk` stays stable.

Newer images (e.g. **Trixie**) may log **two** partitions in one line; layouts vary between **two** and **three** partitions. The **boot** filesystem is still the **first FAT** partition (commonly `sdX1`); the scripts pick **`p1` vs `1`** the same way as `flash_sdcard.sh`.

## End-to-end workflow (download → expand → patch `.img` → flash → SSH)

Use this when you want **one downloaded artifact**, **CEDE cloud-init baked into the raw image**, then a **single flash** to the SD card (same contents as flash-after-write, but you can archive the patched `.img`).

1. **Config:** `lab/config/lab.yaml` with **`raspberry_pi_bootstrap.os_image.url`**, **`cache_path`** (e.g. `lab/pi/dist/foo.img.xz`), **`hostname`**, **`hosts.pi.ssh_host`** (`<hostname>.local`), and preferably **`authorized_keys_file`** for SSH on first boot.

2. **Download and decompress** (no root):

   ```bash
   uv sync   # repo root
   uv run python lab/pi/bootstrap/pi_bootstrap.py fetch-image
   uv run python lab/pi/bootstrap/pi_bootstrap.py expand-image
   ```

3. **Patch the uncompressed `.img`** (needs **`sudo`** for `losetup` / mount). Avoid **`sudo uv run`** (see step 4 — **`uv`** is usually not on **`sudo`**’s **`PATH`**):

   ```bash
   sudo ./.venv/bin/python lab/pi/bootstrap/pi_bootstrap.py patch-image \
     --image lab/pi/dist/raspios_trixie_arm64_latest.img --yes
   ```

   Adjust `--image` if your **`cache_path`** basename differs.

4. **Unmount** any mounts on the SD reader (flash will fail if **`/dev/sdX`** partitions are mounted), then **flash**:

   **`sudo uv run …` usually fails** (`uv: command not found`) because **`sudo` drops your normal `PATH`** and does not include **`~/.local/bin`** where **`uv`** is installed. Prefer one of:

   ```bash
   lsblk /dev/sdX
   sudo umount /dev/sdX1 /dev/sdX2 2>/dev/null || true

   # Recommended: project venv (after `uv sync` at repo root)
   sudo ./.venv/bin/python lab/pi/bootstrap/pi_bootstrap.py flash-file \
     --device /dev/sdX --image lab/pi/dist/raspios_trixie_arm64_latest.img --yes

   # Or wrapper script (same effect)
   chmod +x lab/pi/bootstrap/pi_bootstrap_sudo.sh
   ./lab/pi/bootstrap/pi_bootstrap_sudo.sh flash-file \
     --device /dev/sdX --image lab/pi/dist/raspios_trixie_arm64_latest.img --yes

   # Alternative: preserve PATH for sudo (fragile across machines)
   sudo env "PATH=$PATH" uv run python lab/pi/bootstrap/pi_bootstrap.py flash-file ...
   ```

   Replace **`sdX`** with your **whole-disk** device (not `sdX1`). Triple-check **`lsblk`** before **`--yes`**.

5. **Boot the Pi** with Ethernet (or Wi‑Fi if configured). **SSH** when cloud-init finishes:

   ```bash
   ssh pi@<hostname>.local
   # or: ssh pi@$(getent hosts <hostname>.local | awk '{print $1}')
   ```

6. **Gateway installer** on the Pi (see [sdcard.md](sdcard.md) §3):

   ```bash
   sudo ./lab/pi/bootstrap/bootstrap_pi.sh --hostname <hostname>
   ```

**Note:** If you skip patching the `.img`, you can instead **`flash`** from **`lab.yaml`** (writes the URL with **`rpi-imager`**, then injects cloud-init on the card):

`uv run python lab/pi/bootstrap/pi_bootstrap.py flash --device /dev/sdX --yes`

## See also

- [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md) — **`authorized_keys_file`**: create, test, deploy for passwordless SSH / E2E.
- [sdcard.md](sdcard.md) — GUI Imager, first boot, gateway bootstrap.
- [DESIGN.md](../../../DESIGN.md) §9 — Hello Lab ordering.
