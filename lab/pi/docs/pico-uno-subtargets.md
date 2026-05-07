# Pico / Uno sub-targets from Pi gateway

Use this runbook **after** gateway bootstrapping has passed its **E2E** checks (patched `.img`, verify, flash, SSH). Pico/Uno flashing assumes a sane Pi OS gateway and a working **`ssh`** session — not half-repaired cloud-init.

**Order:** finish the **[Gateway E2E verification gate](rpi3-gateway-remote.md#gateway-e2e-verification-gate)** (`make validate`, **`make pi-gateway-sd-ready`**, **`pi-gateway-verify-boot`**, bench flash, then **`ping`** + **`ssh`**). Fix wrong **`user-data`**, missing keys, or sudo policy by **remounting the SD or loop-mounting the `.img`** and re-running **`prepare_sdcard_boot.sh`** / **`patch-image`** ([cli-flash.md](cli-flash.md)); do not chase bring-up bugs by editing `/etc` on the live Pi from this workflow.

---

## Implemented today (Hello Lab–class Uno path)

These pieces are wired and repeatable from the **Dev-Host** without opening an interactive SSH session on the Pi:

| Step | What proves it |
|------|----------------|
| Minimal sync to gateway | Makefile + helpers under **`lab/pi/`** only ([`sync_gateway_flash_deps.sh`](../scripts/sync_gateway_flash_deps.sh); optional **`UNO_ONLY=1`** to omit Pico UF2 helper) |
| Uno **`PORT`** | Gateway-side [`pi_resolve_gateway_uno.py`](../scripts/pi_resolve_gateway_uno.py): **`/dev/serial/by-id/usb-Arduino*`** first; else unique **`ttyUSB*`**; else **`ttyACM*`** excluding devices whose realpath is a Pico symlink under **`glob /dev/serial/by-id/usb-Raspberry_Pi*`**. Ambiguous ⇒ fail (**`PORT=`** override). |
| Flash + verify firmware | **`avrdude`** on Pi via [`pi_flash_uno_avrdude.sh`](../scripts/pi_flash_uno_avrdude.sh); **verified bytes on device** printed by avrdude. |
| Serial data path | **`hello_lab.ino`** prints **`CEDE hello_lab ok`** @ 115200; [`pi_validate_uno_serial.py`](../scripts/pi_validate_uno_serial.py) (pyserial **or** **`stty`** + ioctl) checks the banner. |
| Offline tests | `uv run pytest -q lab/tests/test_uno_gateway_env.py` (resolver + lab config expectations; **no hardware**). |
| Hardware pytest stub | `test_flash_uno_from_pi` in [`lab/tests/test_hello_lab_matrix.py`](../../tests/test_hello_lab_matrix.py) remains **`@pytest.mark.hardware`** skipped until wired for Pi‑native pytest. |

Pico BOOTSEL/`picotool` paths below are unchanged; this document’s **automated Dev-Host targets** centre on **Uno** unless you extend them similarly.

---

## Dev-host driver (stay on workstation)

Root [`Makefile`](../../../Makefile) invokes [`devhost_pi_gateway.sh`](../scripts/devhost_pi_gateway.sh) over **`ssh`** to **`GATEWAY`** (default `pi@cede-pi.local`, tree at **`GATEWAY_REPO_ROOT`** default literal `~/cede` on the Pi — do not Bash‑expand **`~`** in defaults on the Dev-Host).

```bash
make -C lab/docker uno-build
make pi-gateway-health GATEWAY=pi@cede-pi.local

# Typical Uno smoke: sync helpers, scp HEX, resolve PORT on Pi, avrdude, then banner check:
make pi-gateway-flash-test-uno GATEWAY=pi@cede-pi.local
# Override when the resolver refuses (multiple ACM / clones):
make pi-gateway-flash-uno GATEWAY=pi@cede-pi.local PORT=/dev/ttyACM0

make pi-gateway-resolve-port-uno GATEWAY=pi@cede-pi.local   # print PORT only
make pi-gateway-print-serial GATEWAY=pi@cede-pi.local       # ttyACM/ttyUSB list on Pi

# HEX=/abs/path/hello.ino.hex  SKIP_SYNC=1  UNO_ONLY=1  as needed (see Makefile help)
make help    # Pi gateway bullet list
```

**Script directly:** `lab/pi/scripts/devhost_pi_gateway.sh` — **`health`**, **`resolve-port-uno`**, **`subtarget-check`**, **`print-serial`**, **`sync`** (delegates to `sync_gateway_flash_deps.sh`), **`flash-uno`**, **`validate-uno-serial`**.

Logical serial globs for **docs/tests** (`discover_serial.py`, `lab.yaml`) live under **`serial.devices.uno`** in [`lab.example.yaml`](../../config/lab.example.yaml).

---

## 1) Prerequisites on the Pi

Run **on the Pi** (optional if Dev-Host **`make pi-gateway-health`** is enough):

```bash
cd ~/cede   # adjust to GATEWAY_REPO_ROOT
python3 lab/pi/scripts/health_check.py
```

Expected output includes `health: ok (picotool, avrdude, python3 present)`.

Bootstrap if tools are missing:

```bash
cd ~/cede
sudo ./lab/pi/bootstrap/bootstrap_pi.sh --hostname cede-pi
```

Full repo checkout on the Pi is **not** required for the minimal sync path—you only need the directories **`sync_gateway_flash_deps.sh`** publishes (Makefile + **`lab/pi/scripts/*.py|.sh`**).

---

## 2) Build firmware artifacts on Dev-Host

From the repo root on Dev-Host:

```bash
make -C lab/docker pico-build
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
cd ~/cede
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

From the synced repo on the Pi:

```bash
cd ~/cede
make -C lab/pi flash-uno HEX=/tmp/hello_lab.ino.hex PORT=/dev/serial/by-id/usb-Arduino_…
# or PORT=/dev/ttyACM0 / ttyUSB0 when unambiguous on your bench
```

---

## 6) Validate serial bring‑up

**Structured check (recommended):**

```bash
# On gateway (needs synced pi_validate_uno_serial.py):
cd ~/cede
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

With repo helpers under **`~/cede`**:

```bash
make -C lab/pi help
make -C lab/pi subtarget-check
make -C lab/pi resolve-uno-port
make -C lab/pi print-serial
make -C lab/pi validate-uno-serial PORT=/dev/ttyACM0

make -C lab/pi flash-pico-uf2 UF2=/tmp/hello_lab.uf2
make -C lab/pi flash-uno HEX=/tmp/hello_lab.ino.hex PORT=<resolved_path>
```

**Scripts:** [`pi_flash_pico_uf2.sh`](../scripts/pi_flash_pico_uf2.sh), [`pi_flash_uno_avrdude.sh`](../scripts/pi_flash_uno_avrdude.sh), [`pi_resolve_gateway_uno.py`](../scripts/pi_resolve_gateway_uno.py), [`pi_validate_uno_serial.py`](../scripts/pi_validate_uno_serial.py).

**Dev-Host** remains authoritative for **`make -C lab/docker pico-build` / `uno-build`** unless you duplicate Arduino CLI bootstrap on the Pi.

---

## 8) Offline regression tests (`pytest`)

```bash
uv run pytest -q lab/tests/test_uno_gateway_env.py
```

Covers **`resolve_uno_tty()`** heuristics (mocked **glob**/paths), **`lab.example.yaml`** **`uno`** serial stanza, **`hello_lab`** banner string, **`sync_gateway_flash_deps.sh`** file list hooks, and **`discover_serial.py`** **`uno`** resolution against real YAML/mocked sysfs.
