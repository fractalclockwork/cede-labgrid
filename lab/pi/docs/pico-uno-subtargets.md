# Pico / Uno sub-targets from Pi gateway

Use this runbook **after** gateway bootstrapping has passed its **E2E** checks (patched `.img`, verify, flash, SSH). Pico/Uno flashing assumes a sane Pi OS gateway and a working **`ssh`** session — not half-repaired cloud-init.

**Applications (multi-target firmware):** **[lab/docs/applications.md](../../docs/applications.md)** — e.g. **`i2c_hello`**, **`cede_app.yaml`**, **`make lg-test-pico-i2c-hello`**. **Deploy E2E:** [deploy-lab-stack-app.md](../../docs/deploy-lab-stack-app.md).

**Development preflight (goal-driven gate):** **[lab/docs/dev-preflight.md](../../docs/dev-preflight.md)** — **`make cede-dev-preflight`** chains workspace toolchains + gateway health + subtarget checks before feature work.

**Repeatable E2E (build, flash Pico + Uno, USB validate, I2C):** **[lab/docs/staged-bootstrap.md](../../docs/staged-bootstrap.md)** — section *Copy-paste: end-to-end bench validation (`hello_lab`)* — includes **`CEDE_IMAGE_ID`** for Docker and **`GATEWAY_REPO_ROOT`** for **`pi-gateway-validate-i2c-from-lab`**.

**Staged bootstrap:** **[lab/docs/staged-bootstrap.md](../../docs/staged-bootstrap.md)** — operator **validation command checklist** (workspace → gateway → MCUs → I2C → gateway native → smoke). **Stage 0** is **flash + unique firmware attestation** (`make bootstrap-stage-zero`); workspace build and gateway health are separate gates (`make bootstrap-stage-dev-host`, `make bootstrap-stage-gateway`).

**Gateway layout:** do **not** install a **`git clone`** of CEDE on the Pi. Dev-Host pushes only [**`sync_gateway_flash_deps.sh`**](../scripts/sync_gateway_flash_deps.sh) artifacts (**`lab/pi/Makefile`**, **`lab/pi/scripts/*.py|.sh`**) into a **sparse** directory (default **`~/cede`**). Treat **`GATEWAY_REPO_ROOT`** as that flash-deps root, not a full repository.

**Bus wiring reference:** [bus-wiring.md](bus-wiring.md) is the canonical no-rewire harness specification for USB baseline + I2C across Pi/Pico/Uno (SPI notes are hardware reference only, not a shared lab milestone).

**Order:** finish the **[Gateway E2E verification gate](rpi3-gateway-remote.md#gateway-e2e-verification-gate)** (`make validate`, **`make pi-gateway-sd-ready`**, **`pi-gateway-verify-boot`**, bench flash, then **`ping`** + **`ssh`**). Fix wrong **`user-data`**, missing keys, or sudo policy by **remounting the SD or loop-mounting the `.img`** and re-running **`prepare_sdcard_boot.sh`** / **`patch-image`** ([cli-flash.md](cli-flash.md)); do not chase bring-up bugs by editing `/etc` on the live Pi from this workflow.

---

## Implemented today (Hello Lab–class Uno path)

These pieces are wired and repeatable from the **Dev-Host** without opening an interactive SSH session on the Pi:

| Step | What proves it |
|------|----------------|
| Minimal sync to gateway | Makefile + helpers under **`lab/pi/`** only ([`sync_gateway_flash_deps.sh`](../scripts/sync_gateway_flash_deps.sh); **`UNO_ONLY=1`** omits **all** Pico **`cede-rp2`** helpers). |
| **cede-uno** **`PORT`** | Gateway-side [`pi_resolve_gateway_uno.py`](../scripts/pi_resolve_gateway_uno.py): **`/dev/serial/by-id/usb-Arduino*`** first; else unique **`ttyUSB*`**; else **`ttyACM*`** excluding Pico **`by-id`** realpaths. Ambiguous ⇒ fail (**`PORT=`** override). |
| **cede-rp2** **`PORT`** | Gateway-side [`pi_resolve_gateway_pico.py`](../scripts/pi_resolve_gateway_pico.py): **`/dev/serial/by-id/usb-Raspberry_Pi*`** first; else lone **`ttyACM*`** not claimed by **`usb-Arduino*`** . |
| Flash + verify (Uno) | **`avrdude`** via [`pi_flash_uno_avrdude.sh`](../scripts/pi_flash_uno_avrdude.sh). |
| Flash UF2 (**cede-rp2**) | [`pi_flash_pico_auto.sh`](../scripts/pi_flash_pico_auto.sh): tries **`picotool reboot -uf`** (`-f` helps when prior firmware is USB serial, e.g. MicroPython) when the Pi’s **`picotool`** build includes USB (**`reboot`** command); waits for **`RPI-RP2`**; copies UF2. **`PICO_BOOTSEL_ONLY=1`** skips **`picotool`** (Pico already in BOOTSEL). Fallback: [`pi_flash_pico_uf2.sh`](../scripts/pi_flash_pico_uf2.sh). |
| Serial (**cede-uno**) | Banner **`CEDE hello_lab ok digest=<id>`** @ 115200 (`<id>` = build-time git short or `CEDE_IMAGE_ID` / `nogit`); [`pi_validate_uno_serial.py`](../scripts/pi_validate_uno_serial.py) optional **`--digest`** to pin `<id>`. |
| I2C matrix (per pair) | Prefer **`make pi-gateway-validate-i2c-from-lab`** (reads **`lab.yaml`** **`i2c_matrix`** / **`validation`**). Pi→MCU aliases: **`pi-gateway-validate-i2c-pi-to-pico`**, **`…-pi-to-uno`** — [bus-wiring.md](bus-wiring.md) § *I2C matrix tests*. Flash+Pi I2C for one board: **`pi-gateway-flash-test-pico-i2c`** / **`pi-gateway-flash-test-uno-i2c`**. |
| Serial (**cede-rp2**) | **`CEDE hello_lab rp2 ok digest=<id>`** from USB CDC (same digest rules as Uno); [`pi_validate_pico_serial.py`](../scripts/pi_validate_pico_serial.py) optional **`--digest`**. |
| Gateway native (**cede-pi** aarch64) | Build on the **Dev-Host** only (**`make pi-gateway-build-native-hello`**). The gateway keeps **no** full repo — **`pi-gateway-sync`** + **`scp`** of the ELF to **`/tmp`**, then validate. Embed id: pass **`CEDE_IMAGE_ID`** into the Docker build via that Make target (defaults to same **git short** as **`FIRMWARE_DIGEST`**); raw **`make -C lab/docker gateway-native-hello-build`** without **`CEDE_IMAGE_ID`** can show **`digest=unknown`**. |
| Offline tests | `pytest lab/tests/test_uno_gateway_env.py`, **`lab/tests/test_pico_gateway_env.py`**. |
| Full hello_lab hardware (not CI) | **`make pi-gateway-hello-lab-hardware-smoke GATEWAY=pi@cede-pi.local`** — Docker **`pico-build` + `uno-build`** with a **new `CEDE_TEST_IMAGE_ID` every run** (override to pin: **`CEDE_TEST_IMAGE_ID=myid12 make …`**), then **`pi-gateway-flash-test-pico`** / **`…-uno`** with **`DIGEST`** set to that id so serial validators reject stale UF2/HEX. Needs Pico + Uno on the Pi; use **`UNO_PORT`** when **`PORT`** is the Pico. Pytest: **`CEDE_RUN_HARDWARE_FULL=1 uv run pytest lab/tests/test_hello_lab_hardware_full.py`**. |
| Uno-only digest smoke | **`make pi-gateway-hello-lab-hardware-smoke-uno`** — **`uno-build`** with fresh **`CEDE_TEST_IMAGE_ID`**, **`pi-gateway-flash-test-uno`** + **`DIGEST`**. Pytest: **`CEDE_RUN_HARDWARE_UNO=1 uv run pytest lab/tests/test_hello_lab_hardware_uno_digest.py`**. |
| Pico-only digest smoke | **`make pi-gateway-hello-lab-hardware-smoke-pico`** — **`pico-build`** with fresh **`CEDE_TEST_IMAGE_ID`**, **`pi-gateway-flash-test-pico`** + **`DIGEST`**. Pytest: **`CEDE_RUN_HARDWARE_PICO=1 uv run pytest lab/tests/test_hello_lab_hardware_pico_digest.py`**. |
| Hardware pytest stubs | [`test_hello_lab_matrix.py`](../../tests/test_hello_lab_matrix.py) — legacy skips; prefer **`test_hello_lab_hardware_full.py`** above. |

**Naming:** **`cede-pi`** = gateway host; **`cede-uno`** / **`cede-rp2`** = logical MCU subtargets (docs / Make); future **`cede-rp2-micropython`** is out of scope here.

Pico **`RPI-RP2`** is the BOOTSEL volume label (unchanged).

---

## Dev-host driver (stay on workstation)

Root [`Makefile`](../../../Makefile) invokes [`devhost_pi_gateway.sh`](../scripts/devhost_pi_gateway.sh) over **`ssh`** to **`GATEWAY`** (default `pi@cede-pi.local`). **`GATEWAY_REPO_ROOT`** is the **sparse** flash-deps directory on the Pi (default **`~/cede`**); omit it for that default, or set **`GATEWAY_REPO_ROOT='~/src/cede'`** (quoted so GNU Make / the shell does not expand **`~`** to the dev-host home). **`sync_gateway_flash_deps.sh`** writes **`lab/pi/…`** under that root — still **not** a full **`git clone`**.

```bash
make -C lab/docker uno-build
make -C lab/docker pico-build
make pi-gateway-health GATEWAY=pi@cede-pi.local

# cede-uno: sync, scp HEX, resolve PORT, avrdude, serial banner
make pi-gateway-flash-test-uno GATEWAY=pi@cede-pi.local

# cede-rp2: sync Pico helpers, scp UF2, flash (picotool reboot -uf when available), serial banner
make pi-gateway-flash-test-pico GATEWAY=pi@cede-pi.local
# Pico already in BOOTSEL or picotool without USB:
make pi-gateway-flash-pico GATEWAY=pi@cede-pi.local PICO_BOOTSEL_ONLY=1

# Flash both MCUs then inter-MCU I2C (see bus-wiring.md § I2C matrix tests)
make pi-gateway-resolve-port-uno GATEWAY=pi@cede-pi.local
make pi-gateway-resolve-port-pico GATEWAY=pi@cede-pi.local
make pi-gateway-print-serial GATEWAY=pi@cede-pi.local

make help
```

**Script directly:** `lab/pi/scripts/devhost_pi_gateway.sh` — **`health`**, **`resolve-port-uno`**, **`resolve-port-pico`**, **`subtarget-check`**, **`print-serial`**, **`sync`**, **`flash-uno`**, **`flash-pico`**, **`validate-uno-serial`**, **`validate-pico-serial`**.

Logical serial globs for **docs/tests** (`discover_serial.py`, `lab.yaml`) live under **`serial.devices.uno`** in [`lab.example.yaml`](../../config/lab.example.yaml).

---

## 1) Prerequisites on the Pi

With [**`sync_gateway_flash_deps.sh`**](../scripts/sync_gateway_flash_deps.sh) applied (or **`make pi-gateway-sync`** from Dev-Host), helpers live under **`${GATEWAY_REPO_ROOT}/lab/pi/`**. Example **`GATEWAY_REPO_ROOT=~/cede`**:

```bash
cd ~/cede    # sparse flash-deps root only — not a full repo checkout
python3 lab/pi/scripts/health_check.py
```

Expected output includes `health: ok (picotool, avrdude, python3 present)`.

**Extra gateway packages** (Docker, Arduino CLI, **`disk`** group, pip deps): copy **`lab/pi/bootstrap/bootstrap_pi.sh`** from Dev-Host and run on the Pi (**`scp`** + **`sudo /tmp/bootstrap_pi.sh --hostname …`**); see [sdcard.md](sdcard.md) §3 — still **no** full-tree **`git clone`** on the gateway.

---

## 2) Build firmware artifacts on Dev-Host

From the repo root on Dev-Host:

```bash
make -C lab/docker pico-build                 # default: plain Pico (`PICO_BOARD=pico`)
make -C lab/docker pico-build PICO_BOARD=pico_w   # Pico W
make -C lab/docker uno-build
```

Expected outputs (`lab.yaml` **`paths`** or defaults):

- `lab/pico/hello_lab/build/*.uf2`
- `lab/uno/hello_lab/build/hello_lab.ino.hex` (**`hello_lab.ino`** includes the **`CEDE hello_lab ok`** serial banner used by validation.)

---

## 3) Transfer artifacts to Pi

**Recommended (Uno):** use **`make pi-gateway-flash-uno`** — it **`scp`** s the HEX to **`/tmp/`** on **`GATEWAY`** (no manual copy).

**Manual** (either MCU), if you maintain artifacts yourself:

```bash
scp lab/pico/hello_lab/build/*.uf2 pi@cede-pi.local:/tmp/
scp lab/uno/hello_lab/build/hello_lab.ino.hex pi@cede-pi.local:/tmp/
```

On Pi:

```bash
ls -l /tmp/*.uf2 /tmp/hello_lab.ino.hex
```

---

## 4) Flash Pico from Pi

### Option A: BOOTSEL mass-storage path (simple)

1. Hold BOOTSEL, plug Pico into Pi USB.
2. Confirm mountpoint (often `/media/<user>/RPI-RP2`).
3. Copy UF2:

```bash
cp /tmp/hello_lab.uf2 /media/$USER/RPI-RP2/
sync
```

Or from synced helpers on the Pi:

```bash
cd ~/cede   # sparse flash-deps root (sync_gateway_flash_deps.sh)
make -C lab/pi flash-pico-uf2 UF2=/tmp/hello_lab.uf2
```

### Option B: `picotool` path

```bash
picotool info || true
# Use your bench-specific picotool load/reboot flow
```

---

## 5) Flash Uno from Pi

**Choose `PORT`** (stable order): **`ls -l /dev/serial/by-id/`** and prefer **`usb-Arduino*`** symlink(s), or **`./lab/pi/scripts/pi_resolve_gateway_uno.py`** on the gateway, Dev-Host **`make pi-gateway-resolve-port-uno`**, or omit **`PORT`** in **`devhost_pi_gateway`** and let **`pi_resolve_gateway_uno.py`** run on the Pi.

**Raw `avrdude`** (Arduino Uno / ATmega328P @ 115200):

```bash
avrdude -p atmega328p -c arduino -P /dev/serial/by-id/usb-Arduino_… -b 115200 -D \
  -U flash:w:/tmp/hello_lab.ino.hex:i
```

From the synced helpers on the Pi:

```bash
cd ~/cede   # sparse flash-deps root
make -C lab/pi flash-uno HEX=/tmp/hello_lab.ino.hex PORT=/dev/serial/by-id/usb-Arduino_…
# or PORT=/dev/ttyACM0 / ttyUSB0 when unambiguous on your bench
```

---

## 6) Validate serial bring‑up

**Structured check (recommended):**

```bash
# On gateway (needs synced pi_validate_uno_serial.py):
cd ~/cede   # sparse flash-deps root
make -C lab/pi resolve-uno-port
make -C lab/pi validate-uno-serial PORT=/dev/ttyACM0   # exact PORT required here
```

**From Dev-Host** (resolver optional; sync is automatic when **`PORT`** omitted):

```bash
make pi-gateway-validate-uno GATEWAY=pi@cede-pi.local
```

**Manual** probing:

```bash
python3 - <<'PY'
import glob
print("ACM:", glob.glob("/dev/ttyACM*"))
print("USB:", glob.glob("/dev/ttyUSB*"))
PY
```

Optional **`picocom`**: **`picocom -b 115200 <PORT>`**; exit with **`Ctrl-A`** then **`Ctrl-X`**.

---

## 7) Automation on the Pi (`lab/pi/Makefile`)

With synced helpers under **`~/cede`** (or **`GATEWAY_REPO_ROOT`** — **sparse** tree only):

```bash
cd ~/cede   # sparse flash-deps root
make -C lab/pi help
make -C lab/pi subtarget-check
make -C lab/pi resolve-uno-port
make -C lab/pi print-serial
make -C lab/pi validate-uno-serial PORT=/dev/ttyACM0

make -C lab/pi flash-pico-auto UF2=/tmp/hello_lab.uf2           # cede-rp2: picotool reboot -uf then UF2 copy
make -C lab/pi flash-pico-auto UF2=/tmp/hello_lab.uf2 PICO_BOOTSEL_ONLY=1   # BOOTSEL already / no picotool USB
make -C lab/pi flash-pico-uf2 UF2=/tmp/hello_lab.uf2          # copy only (RPI-RP2 already mounted)
make -C lab/pi resolve-pico-port
make -C lab/pi validate-pico-serial PORT=/dev/ttyACM0

make -C lab/pi flash-uno HEX=/tmp/hello_lab.ino.hex PORT=<resolved_path>
```

**Scripts:** [`pi_flash_pico_auto.sh`](../scripts/pi_flash_pico_auto.sh), [`pi_flash_pico_uf2.sh`](../scripts/pi_flash_pico_uf2.sh), [`pi_resolve_gateway_pico.py`](../scripts/pi_resolve_gateway_pico.py), [`pi_validate_pico_serial.py`](../scripts/pi_validate_pico_serial.py), [`pi_flash_uno_avrdude.sh`](../scripts/pi_flash_uno_avrdude.sh), [`pi_resolve_gateway_uno.py`](../scripts/pi_resolve_gateway_uno.py), [`pi_validate_uno_serial.py`](../scripts/pi_validate_uno_serial.py).

**Dev-Host** remains authoritative for **`make -C lab/docker pico-build` / `uno-build`** unless you duplicate Arduino CLI bootstrap on the Pi.

---

## 8) Offline regression tests (`pytest`)

```bash
uv run pytest -q lab/tests/test_uno_gateway_env.py
uv run pytest -q lab/tests/test_pico_gateway_env.py
```

Covers **`resolve_uno_tty()`** / **`resolve_pico_tty()`** heuristics (mocked **glob**/paths), **`lab.example.yaml`** **`uno`** serial stanza, **`hello_lab`** banner strings (Uno `.ino` / Pico **`main.c`**), **`sync_gateway_flash_deps.sh`** file list hooks, and **`discover_serial.py`** **`uno`** resolution against real YAML/mocked sysfs.
