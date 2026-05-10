# Staged bootstrap (workspace → cede-pi → first flash → more targets)

Each **numbered stage** is **self-contained** for its intent. **Stage 0** is the first **hardware** gate: you **flash** a device and prove the **image you flashed** is the one running, using a **unique** firmware response (not just “something on the bus”).

**Naming (lab docs):** **cede-pi** = Raspberry Pi gateway; **cede-rp2** = Raspberry Pi Pico (USB `by-id`); **cede-uno** = Arduino Uno.

The gateway keeps **only** a **sparse** tree (**`sync_gateway_flash_deps.sh`** → **`~/cede/lab/pi/…`**); do **not** **`git clone`** CEDE on **cede-pi**. UF2, HEX, and **`hello_gateway`** are built on the Dev-Host and copied (**`scp`**) by **`make pi-gateway-*`** targets.

---

## Validation command checklist (environment + targets)

Use this section as the **operator index** after imaging **cede-pi** and wiring Pico/Uno. Order: **workspace → gateway → MCUs → I2C → (optional) gateway native**. **`GATEWAY`** defaults to **`pi@cede-pi.local`** in root **`Makefile`**; override when needed. **`unset DIGEST`** before smoke targets if your shell still exports an old **`DIGEST=`**.

### Copy-paste: end-to-end bench validation (`hello_lab`)

Run from the **repository root** on the Dev-Host. Requires SSH to **`GATEWAY`**, USB from Pi → Pico and Pi → Uno, and I2C harness per **[bus-wiring.md](../pi/docs/bus-wiring.md)** for the matrix step.

```bash
export DIG=$(git rev-parse --short=12 HEAD)
export GATEWAY=pi@cede-pi.local
export GATEWAY_REPO_ROOT='~/cede'

# Embed digest in firmware — Docker may not see .git; without this, banners can show digest=unknown and flash+validate fails.
make -C lab/docker pico-build uno-build CEDE_IMAGE_ID="$DIG"

make pi-gateway-health GATEWAY="$GATEWAY"
make pi-gateway-subtarget-check GATEWAY="$GATEWAY"

make pi-gateway-flash-test-pico GATEWAY="$GATEWAY"
make pi-gateway-flash-test-uno GATEWAY="$GATEWAY"

make pi-gateway-validate-i2c-from-lab \
  GATEWAY="$GATEWAY" \
  GATEWAY_REPO_ROOT="$GATEWAY_REPO_ROOT" \
  CEDE_LAB_CONFIG="$(pwd)/lab/config/lab.example.yaml"
```

**Notes:**

- **`GATEWAY_REPO_ROOT`** must be the sparse flash-deps root on the Pi (default **`~/cede`**) so remote **`python3 lab/pi/scripts/…`** paths resolve. Quote **`'~/cede'`** so GNU Make does not expand **`~`** on the Dev-Host.
- Optional quick bus-only check without the full matrix driver: **`ssh "$GATEWAY" 'sudo i2cget -y 1 0x42 0 b && sudo i2cget -y 1 0x43 0 b'`** (adjust bus **`1`** if your **`linux_bus`** differs).
- If **`pi-gateway-validate-i2c-from-lab`** exits non-zero despite **`i2cget`** succeeding, see serial-attestation / SSH quirks; USB **`pi-gateway-flash-test-*`** passing above already validates the primary firmware path.

### 1. Dev-Host workspace (no USB hardware)

| Goal | Command |
|------|---------|
| Python deps | **`uv sync`** (repo root) |
| Config schema | **`make test-config-local`** or **`uv run pytest -q lab/tests/test_config_schema.py`** |
| Toolchain + **hello_lab** artifacts + **hello_gateway** cross-build | **`make bootstrap-stage-dev-host`** (for digest-aligned **`hello_lab`**, run Docker **`pico-build`** / **`uno-build`** with **`CEDE_IMAGE_ID=$(git rev-parse --short=12 HEAD)`** if **`bootstrap-stage-dev-host`** alone produced **`digest=unknown`**) |
| CI-style container gate (Docker + builds + pytest in **orchestration-dev**) | **`make container-test-baseline`** |
| Full lab pytest (no hardware) | **`make validate`** |

**Pass:** commands exit 0; UF2/HEX under **`lab/pico/hello_lab/build/`** and **`lab/uno/hello_lab/build/`**; **`lab/pi/native/hello_gateway/build/hello_gateway`** exists (aarch64 ELF from Docker).

### 2. cede-pi gateway (SSH; no MCU flash required)

| Goal | Command |
|------|---------|
| Push **lab/pi** scripts only (sparse tree) | **`make pi-gateway-sync GATEWAY=pi@cede-pi.local`** (or **`UNO_ONLY=1`** for Uno-only sync) |
| Health + subtarget check | **`make bootstrap-stage-gateway GATEWAY=pi@cede-pi.local`** |

**Pass:** **`health: ok`**; when boards are connected, **by-id** serial devices resolve (see **`make pi-gateway-subtarget-check`** / **`print-serial`** in [pico-uno-subtargets.md](../pi/docs/pico-uno-subtargets.md)).

### 3. MCU targets — flash + serial **`digest=`** attestation

Build on Dev-Host first (**`make -C lab/docker pico-build`** / **`uno-build`**) or rely on paths from §1. Pass **`CEDE_IMAGE_ID=$(git rev-parse --short=12 HEAD)`** into those Docker builds so the UF2/HEX embed the same token the validators expect (see **Copy-paste** above).

| Target | Flash + serial validate (default **digest** = dev-host **git** short) |
|--------|-----------------------------------------------------------------------|
| **Pico (cede-rp2)** | **`make pi-gateway-flash-test-pico GATEWAY=pi@cede-pi.local`** |
| **Uno (cede-uno)** | **`make pi-gateway-flash-test-uno GATEWAY=pi@cede-pi.local`** |
| Serial only (already flashed) | **`make pi-gateway-validate-pico`** / **`make pi-gateway-validate-uno`** optional **`DIGEST=…`** **`PORT=…`** |

**Pass:** banner lines contain **`digest=`** matching **`DIGEST`** when set, else repo git short; validators print **`digest-banner:`**.

### 4. I2C — Pi as master (**hello_lab** addresses)

Requires **`i2c-tools`** on **cede-pi**, wiring per **[bus-wiring.md](../pi/docs/bus-wiring.md)**.

| Goal | Command |
|------|---------|
| All enabled rows from **`lab.yaml`** / **`lab.example.yaml`** | **`make pi-gateway-validate-i2c-from-lab GATEWAY=pi@cede-pi.local GATEWAY_REPO_ROOT='~/cede' CEDE_LAB_CONFIG="$(pwd)/lab/config/lab.example.yaml"`** — **`GATEWAY_REPO_ROOT`** required so SSH **`cd ~/cede`** resolves **`lab/pi/scripts`** on the Pi |
| Pi → Pico then USB banner + digest | **`make pi-gateway-validate-i2c-pi-to-pico`** (alias **`pi-gateway-validate-pico-i2c`**) |
| Pi → Uno then USB banner + digest | **`make pi-gateway-validate-i2c-pi-to-uno`** (alias **`pi-gateway-validate-uno-i2c`**) |
| Both addresses + both USB banners | **`make pi-gateway-validate-i2c-both`** |
| Flash one MCU + Pi **i2cget** | **`make pi-gateway-flash-test-pico-i2c`** / **`…-uno-i2c`** |

### 5. Gateway native check (aarch64 **hello_gateway** on **cede-pi**)

Built on Dev-Host; Pi holds **no** full repo — **sync** + **`scp`** binary to **`/tmp`** only.

| Goal | Command |
|------|---------|
| Cross-build ELF | **`make pi-gateway-build-native-hello`** |
| Sync scripts + **`scp`** + run + **`digest=`** check | **`make pi-gateway-validate-gateway-native GATEWAY=pi@cede-pi.local`** optional **`DIGEST=…`** |
| Build + validate in one shot | **`make pi-gateway-build-test-gateway-native GATEWAY=pi@cede-pi.local`** |

**Pass:** stdout line **`CEDE hello_gateway ok digest=<id>`** matches **`FIRMWARE_DIGEST`** / **`DIGEST`** (same rules as §3).

### 6. Hardware smoke — unique **`CEDE_TEST_IMAGE_ID`** per run (both MCUs or one)

| Scope | Command |
|-------|---------|
| Pico + Uno rebuild + flash + validate | **`make pi-gateway-hello-lab-hardware-smoke GATEWAY=pi@cede-pi.local`** |
| Uno only | **`make pi-gateway-hello-lab-hardware-smoke-uno GATEWAY=pi@cede-pi.local`** |
| Pico only | **`make pi-gateway-hello-lab-hardware-smoke-pico GATEWAY=pi@cede-pi.local`** |

Pytest (requires hardware env vars): **`CEDE_RUN_HARDWARE_FULL=1`**, **`CEDE_RUN_HARDWARE_UNO=1`**, **`CEDE_RUN_HARDWARE_PICO=1`** — see **`lab/tests/test_hello_lab_hardware_*.py`**.

### 7. Full staged pipeline (workspace → gateway → Stage 0 → second MCU)

| Goal | Command |
|------|---------|
| End-to-end **`bootstrap-pipeline`** | **`make bootstrap-pipeline GATEWAY=pi@cede-pi.local`** (**`ZERO_TARGET=pico`** default) |

### Tier summary (quick reference)

| Tier | Role | Flash / action | Test | Validate (pass) |
|------|------|----------------|------|------------------|
| **Workspace** | Dev-Host | *Build* UF2 + HEX (no device) | Config schema; Docker `pico-build` / `uno-build` | Artifacts exist; builds exit 0 |
| **(prereq)** | cede-pi | No MCU flash; OS on SD is out of band ([sdcard.md](../pi/docs/sdcard.md)) | `health_check` + `by-id` listing | `health: ok`; USB devices visible when connected |
| **Stage 0** | **First device — flash + attestation** | Program **one** MCU (UF2 or HEX) | Flash script + serial read (and optional I2C) | **Unique** response from **this** firmware (see below) |
| **Stage 1** | Second subtarget (typical) | Other MCU on the same gateway | Same pattern: flash + serial | Other banner / contract |
| **Later** | Buses / matrix | I2C/SPI per [bus-wiring.md](../pi/docs/bus-wiring.md) | `i2cdetect`, scope, etc. | As in `i2c_matrix` / tests |

---

## What “unique firmware responds” means (Stage 0)

**Attestation** = the running image matches the **hello_lab** you deploy, not an old UF2/HEX or a different sketch.

| Path | After flash, you must see |
|------|---------------------------|
| **cede-rp2** | USB CDC line containing **`CEDE hello_lab rp2 ok`** and **`digest=<id>`** (validator default is banner prefix only). **`<id>`** is **`git rev-parse --short=12 HEAD`** at image build time (or **`CEDE_IMAGE_ID`** if set when building), else **`unknown`**. **Optional second channel:** I2C reg **0** @ **0x42** reads **`0xce`** (Uno uses **0x43** on the same bus; [bus-wiring.md](../pi/docs/bus-wiring.md)). |
| **cede-uno** | Serial line **`CEDE hello_lab ok`** with **`digest=<id>`** @ 115200 (same **`CEDE_IMAGE_ID`** rules; Uno runs **`tools/gen_cede_image_id.sh`** before **`arduino-cli compile`** in **`lab/docker` `uno-build`**). |

`pi_validate_*_serial.py` uses a **substring** expect for the banner prefix and **always** requires a **`digest=`** token in the same capture (old hello_lab without digest fails). From the Dev-Host, **`make pi-gateway-validate-pico`** / **`…-validate-uno`** pass **`--digest`** automatically when **`git rev-parse --short=12 HEAD`** succeeds in **`$(REPO_ROOT)`**; override with **`DIGEST=…`**. **`devhost_pi_gateway.sh`** accepts **`--digest`** on serial validate commands.

---

## Workspace (not Stage 0)

**Prerequisites:** Docker for `lab/docker` builds, `uv` for pytest.

| Column | What |
|--------|------|
| **Flash** | *None* — only **build** `hello_lab.uf2` / `hello_lab.ino.hex`. |
| **Test** | `lab/config` schema; cross-compiles. |
| **Validate** | Files under `lab/pico/hello_lab/build/` and `lab/uno/hello_lab/build/`. |

```bash
make bootstrap-stage-dev-host
# Or CI-parity: make container-test-baseline
```

---

## Prerequisite: gateway answers (before remote flash from Dev-Host)

**Prerequisites:** **SSH** to `GATEWAY` (default `pi@cede-pi.local`). First-time SD imaging: [sdcard.md](../pi/docs/sdcard.md), **`make pi-gateway-sd-ready`**, [rpi3-gateway-remote.md](../pi/docs/rpi3-gateway-remote.md).

| Column | What |
|--------|------|
| **Flash** | No MCU. Optional: **`bootstrap_pi.sh`** on the Pi ([sdcard.md](../pi/docs/sdcard.md) §3). |
| **Test** | `health` + `subtarget-check` on the Pi. |
| **Validate** | `health: ok`; expected serial devices when boards are plugged in. |

```bash
make bootstrap-stage-gateway GATEWAY=pi@cede-pi.local
```

---

## Stage 0 — Flash one device + confirm unique firmware

**Prerequisites:** **Workspace** artifacts for that target; **prerequisite** gateway (and **Pico** or **Uno** on USB to **cede-pi**). From Dev-Host, flash goes through **SSH** + **sync** to the Pi (see [pico-uno-subtargets.md](../pi/docs/pico-uno-subtargets.md)).

| Column | What |
|--------|------|
| **Flash** | UF2 (**cede-rp2**) or HEX (**cede-uno**) via gateway. |
| **Test** | `pi-gateway-flash-test-pico` or `pi-gateway-flash-test-uno` (sync, program, read serial). |
| **Validate** | **Unique** banner (table above). **Optional (Pico only):** `BOOTSTRAP_ZERO_I2C=1` also runs `i2cget` for register **0** = **`0xce`**. |

**Default first target is Pico** (`ZERO_TARGET=pico`).

```bash
# Stage 0 — cede-rp2 (default)
make bootstrap-stage-zero GATEWAY=pi@cede-pi.local

# Same, plus I2C register read (wiring + i2c-tools on Pi)
make bootstrap-stage-zero GATEWAY=pi@cede-pi.local BOOTSTRAP_ZERO_I2C=1

# Stage 0 — cede-uno only
make bootstrap-stage-zero-uno GATEWAY=pi@cede-pi.local

# Explicit Pico target
make bootstrap-stage-zero-pico GATEWAY=pi@cede-pi.local
```

---

## Stage 1 — Second MCU (typical)

After Stage 0 on **cede-rp2**, bring up **cede-uno** (or the reverse order if you prefer).

```bash
make bootstrap-stage-uno GATEWAY=pi@cede-pi.local
```

---

## Full hello_lab hardware smoke (unique digest every run)

**Not for CI** — needs Docker, SSH **`GATEWAY`**, and **Pico + Uno** on the Pi.

**`make pi-gateway-hello-lab-hardware-smoke`** rebuilds **`hello_lab`** in containers with a **fresh `CEDE_TEST_IMAGE_ID`** each invocation (generator: **`lab/pi/scripts/cede_test_image_id.py`**), embeds it as **`digest=<id>`** in both UF2 and HEX, flashes Pico then Uno via the gateway, and runs serial validators with **`DIGEST=<id>`** so an old image on disk or on-chip fails. Pin the id for debugging: **`CEDE_TEST_IMAGE_ID=mytoken12 make pi-gateway-hello-lab-hardware-smoke`**.

Pytest wrapper (same gate): **`CEDE_RUN_HARDWARE_FULL=1 GATEWAY=pi@cede-pi.local uv run pytest -q lab/tests/test_hello_lab_hardware_full.py`**.

**Uno only:** **`make pi-gateway-hello-lab-hardware-smoke-uno`** or **`CEDE_RUN_HARDWARE_UNO=1 uv run pytest -q lab/tests/test_hello_lab_hardware_uno_digest.py`**.

**Pico only:** **`make pi-gateway-hello-lab-hardware-smoke-pico`** or **`CEDE_RUN_HARDWARE_PICO=1 uv run pytest -q lab/tests/test_hello_lab_hardware_pico_digest.py`**.

If validation says **digest mismatch** but the timestamp prefix matches, check for a **stale `DIGEST` in the shell environment** (run **`unset DIGEST`** or use a clean shell). The smoke targets pin **`CEDE_TEST_IMAGE_ID`** once per **`make`** invocation so echo, Docker **`CEDE_IMAGE_ID`**, and **`DIGEST=`** all match.

**Offline digest (Uno facet):** **`uv run pytest -q lab/tests/test_firmware_attest.py -m uno`**. **Pico facet:** **`-m pico`**.

---

## Full pipeline (Dev-Host)

Order: **workspace** → **gateway prerequisite** → **Stage 0** (one MCU, **`ZERO_TARGET`**) → **second MCU** (the other one).

```bash
make bootstrap-pipeline GATEWAY=pi@cede-pi.local
# Default: ZERO_TARGET=pico → Stage 0 = Pico attestation, then Uno flash-test.

ZERO_TARGET=uno make bootstrap-pipeline GATEWAY=pi@cede-pi.local
# Stage 0 = Uno attestation, then Pico flash-test.
```

Optional second-channel check on Pico Stage 0: **`BOOTSTRAP_ZERO_I2C=1`** (see Stage 0 above).

---

## Related docs

- [pico-uno-subtargets.md](../pi/docs/pico-uno-subtargets.md) — flash/resolve/validate details.
- [bus-wiring.md](../pi/docs/bus-wiring.md) — I2C for second-channel attestation.
- [CONTAINER_BOOTSTRAP.md](../../docs/CONTAINER_BOOTSTRAP.md) — container/image north star.
