# Raspberry Pi 3 Model B — physical validation & remote SSH image

Use this path to **prove hardware**, prepare a **single flashable raw `.img`** with **DHCP on Ethernet** and **SSH on first boot**, then reach the Pi **remotely** (`ssh`) without a monitor.

**Build the artifact, move it to a bench, and flash:** [pi-gateway-image-transfer-flash.md](pi-gateway-image-transfer-flash.md).

---

## What you need

| Item | Notes |
|------|--------|
| **Pi 3 Model B** | 1 GiB RAM — Lite 64-bit is fine; use **8 GiB+** SD (Class A1 or better). |
| **Power** | Official or known-good **5 V** supply (undervoltage causes flaky boots). |
| **Ethernet** | **RJ45 to your LAN** — cloud-init enables **DHCP on `eth0`** by default (primary remote path). Wi‑Fi can be added under `raspberry_pi_bootstrap.wifi` in `lab.yaml`. |
| **Dev-Host** | Linux/macOS with Docker/`uv` optional; **sudo** for loop-mount patch + optional `dd` flash. |

---

## 1. Lab config (`lab/config/lab.yaml`)

Copy from the example and edit:

```bash
cp lab/config/lab.example.yaml lab/config/lab.yaml
```

Set:

1. **`raspberry_pi_bootstrap.hostname`** — short name (e.g. `cede-pi`).
2. **`hosts.pi.ssh_host`** — must be **`<hostname>.local`** for mDNS (e.g. `cede-pi.local`).
3. **`raspberry_pi_bootstrap.authorized_keys_file`** — **uncomment** and point at your **Dev-Host public** key (passwordless SSH over the LAN). See [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md).

Validate:

```bash
make test-config-local
# or: make -C lab/docker test-config
```

Render once and confirm keys appear:

```bash
make pi-bootstrap-render
grep -E 'ssh-(ed25519|rsa)' lab/pi/cloud-init/rendered/user-data
```

---

## 2. Build a **patched** raw image (DHCP + SSH in cloud-init)

Summary — full steps, **transfer**, and **minimal-host `dd`**:

```bash
make pi-gateway-sd-ready
```

That target includes **`pi-gateway-img-patch`** and **`pi-gateway-verify-boot`** (`verify_boot_image.sh --compare-rendered`) so you do not flash an unpatched upstream `.img`.

See [pi-gateway-image-transfer-flash.md](pi-gateway-image-transfer-flash.md) for **`scp` / USB / `rsync`**, checksums, and flashing on a host with only **`dd`**.

**Iterating without a full re-download:** mount the FAT boot partition (USB reader on the Dev-Host) or loop-mount the `.img` and re-copy rendered cloud-init via **`prepare_sdcard_boot.sh --use-existing-rendered`** or **`pi_bootstrap.py prepare-boot`** / **`patch-image`** — see [cli-flash.md](cli-flash.md).

---

## Gateway E2E verification gate

Close **gateway validation** before opening [pico-uno-subtargets.md](pico-uno-subtargets.md):

| Step | Where | What |
|------|--------|------|
| 1 | Dev-Host | **`make validate`** — pytest for config schema, cloud-init render, and the offline SSH-key pipeline (no hardware). |
| 2 | Dev-Host | **`make pi-gateway-sd-ready`** — patch the raw `.img` and run **`make pi-gateway-verify-boot`** so boot **`user-data`** matches **`lab/pi/cloud-init/rendered/`**. |
| 3 | Bench | Flash the SD (below, § 3 *Flash*) or inject boot files on a mounted card (see **[cli-flash.md](cli-flash.md)**). |
| 4 | LAN | **`ping`** + **`ssh`** (§ 4 *Boot*); optional **`bootstrap_pi.sh`** copied from Dev-Host (**`scp`** + **`sudo /tmp/bootstrap_pi.sh`**) for Docker/Arduino extras — never a full **`git clone`** on the gateway. |

Wrong cloud-init, missing keys, or sudo for **`pi`** are fixed by **changing the FAT boot payload** (or the golden `.img`) and re-flashing or rebooting — not by bespoke edits to the running root filesystem in this repo’s process.

---

## 3. Flash to SD card

```bash
make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/raspios_trixie_arm64_latest.img
```

Or Imager / plain `dd` — same playbook as above.

---

## 4. Boot & physical checks

1. Insert SD, **Ethernet** plugged into LAN (**DHCP**).
2. Power on — **activity LED** should blink during boot.
3. On the Dev-Host (same LAN), wait **1–3 minutes** first boot (resize, `cloud-init`, packages).

**Reachability:**

```bash
ping -c 3 cede-pi.local
ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o UserKnownHostsFile="${HOME}/.ssh/cede_gateway_known_hosts" \
  -o StrictHostKeyChecking=accept-new \
  pi@cede-pi.local true && echo OK
```

Host keys: use a **dedicated** **`UserKnownHostsFile`** (as above) so re-flashes do not require **`ssh-keygen -R`** against **`~/.ssh/known_hosts`** — see [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md) § *Host keys*.

Use **`hosts.pi.ssh_user`** if not `pi`.

---

## 5. Hardware validation (beyond SSH)

| Check | Command / note |
|-------|----------------|
| **SSH session** | Confirms CPU/RAM/OS/network stack. |
| **USB** | Plug Pico/Uno — `ls /dev/ttyACM*` after firmware/tests (Hello Lab). |
| **I2C** | Enable in `raspi-config` / overlay if needed; Hello Lab matrix in `lab.yaml`. |
| **Power** | `vcgencmd get_throttled` — should read `0x0` under normal load. |

---

## Troubleshooting

| Symptom | Action |
|---------|--------|
| **`Connection refused` on port 22** | Pi may still be in **first-boot cloud-init** (`package_upgrade` can take **10–20+ minutes** before SSH listens). Wait, ping the host, retry. **Images patched by this repo** also drop an empty **`ssh`** file on the FAT boot partition so sshd starts early — re-run **`prepare-boot`** / **`patch-image`** if your card was prepared without that step. With keyboard/serial: `sudo systemctl status ssh` / `journalctl -u ssh -b`. |
| **`cede-pi.local` not found** | Router DHCP lease list; try IP from router admin; ensure Avahi/mDNS on Dev-Host; see [emulate README](../emulate/README.md) hostname notes. |
| **`raspberrypi` / `raspberrypi.lan`** | You flashed **Bookworm (or older) Pi OS lite** — it does **not** apply boot-partition **`user-data`**. Rebuild from **`lab.example.yaml`** (Trixie URL + **`make pi-gateway-sd-ready`**) and re-flash **or** rename with keyboard or Imager customization. |
| **No SSH at all (wrong OS)** | Non-Trixie image ignores boot **`user-data`** — see **`raspberrypi`** row above. |
| **`Too many authentication failures`** | SSH tried **every agent key** before password; use **`ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 pi@…`** ([ssh-keys-bootstrap.md](ssh-keys-bootstrap.md)). |
| **`REMOTE HOST IDENTIFICATION HAS CHANGED`** | You re-flashed the Pi (new host key). Clear the **lab** known_hosts file (e.g. **`rm ~/.ssh/cede_gateway_known_hosts`**) or **`ssh-keygen -f ~/.ssh/cede_gateway_known_hosts -R cede-pi.local`** — avoid wiping **`~/.ssh/known_hosts`** unless you intend to. See [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md) § *Host keys*. |
| **SSH asks for password** | **`authorized_keys_file`** unset or wrong path when imaging — cloud-init never installed your `.pub`. Set it in **`lab.yaml`**, **`make pi-bootstrap-render`**, **`grep ssh-ed25519`** in **`user-data`**, then **`patch-image`** / **`prepare-boot`** and re-boot **or** flash again. |
| **patch-image fails** | Run with **`uv`** / Python deps; ensure `.img` exists (`make pi-raw-sd-image`). Needs **sudo** for loop mounts. |

---

## Related

- [pi-gateway-image-transfer-flash.md](pi-gateway-image-transfer-flash.md) — build, transfer, flash  
- [pico-uno-subtargets.md](pico-uno-subtargets.md) — Pico/Uno from the gateway; Uno path includes Dev-Host **`make pi-gateway-flash-test-uno`**, **`pi_resolve_gateway_uno.py`**, **`pytest …/test_uno_gateway_env.py`**  
- [sdcard.md](sdcard.md) — YAML-driven imaging overview  
- [ssh-keys-bootstrap.md](ssh-keys-bootstrap.md) — keys end-to-end  
- [BOOT_MEDIA_FLASH.md](../../../docs/BOOT_MEDIA_FLASH.md) — `export-raw-dd` safety  
