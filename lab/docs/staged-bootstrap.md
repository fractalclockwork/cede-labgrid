# Staged bootstrap (workspace → cede-pi → first flash → more targets)

Each **numbered stage** is **self-contained** for its intent. **Stage 0** is the first **hardware** gate: you **flash** a device and prove the **image you flashed** is the one running, using a **unique** firmware response (not just “something on the bus”).

**Naming (lab docs):** **cede-pi** = Raspberry Pi gateway; **cede-rp2** = Raspberry Pi Pico (USB `by-id`); **cede-uno** = Arduino Uno.

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
