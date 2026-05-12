# CEDE bus wiring (Pi + Pico + Uno)

This document defines the fixed, no-rewire wiring harness for native bus bring-up in CEDE.

Scope for this harness:
- USB baseline (flash + serial validation)
- I2C
- SPI

Out of scope:
- UART bus bring-up
- Non-native/add-on buses (for example CAN adapters)

## 1) Harness rules

- Keep both MCUs connected to the Pi over USB at all times.
- Use a single shared ground across Pi, Pico, and Uno.
- Keep each board on its native power path.
- Pre-wire I2C and SPI once; switch test modes in software/config, not with rewiring.

## 2) USB baseline (always connected)

- Pi USB host <-> Pico USB device
- Pi USB host <-> Uno USB device

This remains the baseline for flashing and serial validators.

## 3) I2C pin-to-pin wiring

### Electrical requirements

- Use a bidirectional I2C level shifter (open-drain compatible).
- 3.3 V side: Pi + Pico.
- 5 V side: Uno.
- Do not directly connect Uno SDA/SCL to Pi/Pico SDA/SCL.

### Common ground

- Pi `GND` (physical pin `6`) <-> Pico `GND` <-> Uno `GND`

### 3.3 V side (Pi + Pico + shifter LV)

- Pi `GPIO2/SDA1` (physical pin `3`) -> shifter `LV SDA`
- Pi `GPIO3/SCL1` (physical pin `5`) -> shifter `LV SCL`
- Pico `GP0` (SDA) -> same `LV SDA` net
- Pico `GP1` (SCL) -> same `LV SCL` net
- Pi `3V3` (physical pin `1`) -> shifter `LV` supply

### 5 V side (Uno + shifter HV)

- Uno `A4` (SDA) -> shifter `HV SDA`
- Uno `A5` (SCL) -> shifter `HV SCL`
- Uno `5V` -> shifter `HV` supply

### I2C pull-up and preflight checklist

- Keep one intentional pull-up network per side:
  - LV pull-ups to `3.3V`
  - HV pull-ups to `5V`
- Avoid stacked strong pull-ups from multiple modules.
- **TXS0108E OE pin must be tied to VCCA (3.3 V)** — a floating OE causes intermittent bus failures.
- Preflight before tests:
  - SDA/SCL idle high on both sides
  - no stuck-low lines
  - bus scan sees only expected responders (`0x42`, `0x43`)

### I2C bring-up defaults

- Start with Pi as controller on bus `1`.
- Start at `100kHz`.
- Expand matrix only after stable baseline.

### Pi → Pico + Uno on one bus (distinct 7-bit addresses)

**hello_lab** firmware uses fixed **7-bit** addresses so **Pico** and **Uno** may both be attached on the shifter:

| Target | Address | Reg **0** read (`i2cget -y 1 <addr> 0 b`) |
|--------|---------|---------------------------------------------|
| **cede-rp2** (Pico) | **0x42** | **`0xce`** |
| **cede-uno** | **0x43** | **`0xce`** |

From **cede-pi**: `sudo i2cdetect -y 1` should show **`42`** and **`43`** when both targets run current `hello_lab`.

**Optional SSD1306 OLEDs** on the same Pi I2C bus use different addresses (typically **`3c`** and **`3d`** with an ADDR jumper). They do not collide with **`0x42`** / **`0x43`**. See [lab/pi/ssd1306_dual/README.md](../ssd1306_dual/README.md).

### I2C matrix tests (Pi → each MCU)

**Single bring-up path:** declare **`i2c_matrix.pairs[].validation`** in **`lab/config/lab.yaml`** (or copy from **`lab.example.yaml`**). Each enabled row uses **`mode: rpi_master_i2cdev_read`** with **`controller: rpi`** so the **Raspberry Pi** drives **SCL** and reads the target (**`i2cget`**) at **`probe_address`**. That is enough to validate the shared bus and level shifting to each MCU; dedicated Pico↔Uno USB-triggered matrix rows were removed as redundant with Pi→Pico and Pi→Uno checks.

Run every enabled row from the dev-host with **`make pi-gateway-validate-i2c-from-lab`** (optional **`ONLY_I2C_PAIR=rpi,pico`**; config path via **`CEDE_LAB_CONFIG`** or default **`lab.yaml`** / **`lab.example.yaml`**).

Per-pair **`make`** aliases (same wiring as the matrix):

| Initiator | Target | Dev-host make (after firmware matches this repo) |
|-----------|--------|-----------------------------------------------------|
| **Pi** | **Pico** | **`make pi-gateway-validate-i2c-pi-to-pico`** (`i2cget` @ **0x42**) |
| **Pi** | **Uno** | **`make pi-gateway-validate-i2c-pi-to-uno`** (`i2cget` @ **0x43**) |

Flash + Pi-side I2C for a **single** target: **`make pi-gateway-flash-test-pico-i2c`**, **`make pi-gateway-flash-test-uno-i2c`**.

**hello_lab** firmware may still accept USB **`m`** for optional manual Pico↔Uno master probes; that path is **not** part of the lab matrix or default **`make`** targets.

Optional Pi-only smoke (both addresses from the Pi): **`make pi-gateway-validate-i2c-both`**.

**Troubleshooting Pi→Uno:** If **0x43** *Read failed*, reflash Uno (**`make pi-gateway-flash-test-uno-i2c`**) and check **A4/A5** / HV shifter. **`make pi-gateway-diagnose-i2c`** should show **43** in the grid.

**TXS0108E level shifter — OE must be tied high.** If **0x43** (or **0x42**) drops off `i2cdetect` intermittently, check the **OE** (output-enable) pin on the **TXS0108E** level shifter. A floating OE causes the shifter to randomly enable and disable its outputs, making I2C devices appear and disappear from scans. **Tie OE to VCCA (3.3 V)** for reliable operation. This was the root cause of early "flaky Uno TWI" symptoms — the ATmega328P TWI peripheral is reliable when the level shifter is properly configured.

**Serial output and I2C:** The `hello_lab` firmware prints its banner only once at startup (Uno) or on DTR connect (Pico), then stays silent. No periodic serial output competes with the TWI/I2C ISR. The **D13** LED blinks from a **Timer1 ISR** (not `loop()`), keeping `loop()` free for serial commands only. With **SSD1306** or other chatty devices on the same bus, pause OLED demos during **`i2cdetect`** / **`i2cget`** checks so SDA/SCL are not contested during refresh.

## 4) SPI pin-to-pin wiring

### Electrical requirements

- Pi/Pico are 3.3 V logic.
- Uno is 5 V logic; level shifting/protection is required where voltage domains differ.
- Keep one active target path per test case.

### Common ground

- Reuse the same common ground as I2C harness.

### Pi SPI0 trunk (shared)

- Pi `GPIO11/SCLK` (physical pin `23`) -> `SCK` trunk
- Pi `GPIO10/MOSI` (physical pin `19`) -> `MOSI` trunk
- Pi `GPIO9/MISO` (physical pin `21`) -> `MISO` trunk

### Pi chip-select split

- Pi `GPIO8/CE0` (physical pin `24`) -> Pico CS path (`CS_PICO`)
- Pi `GPIO7/CE1` (physical pin `26`) -> Uno CS path (`CS_UNO`)

### Pico SPI mapping

- Pico `GP18` (SCK) <-> `SCK` trunk
- Pico `GP19` (MOSI/TX) <-> `MOSI` trunk
- Pico `GP16` (MISO/RX) <-> `MISO` trunk
- Pico `GP17` (CSn) <-> `CS_PICO`

### Uno SPI mapping

- Uno `D13/SCK` <-> `SCK` trunk
- Uno `D11/MOSI` <-> `MOSI` trunk
- Uno `D12/MISO` <-> `MISO` trunk
- Uno `D10/SS` <-> `CS_UNO`

### SPI electrical and contention checklist

- Treat level shifting directionally:
  - Pi/Pico outputs -> Uno inputs (`SCK`, `MOSI`, `CS_UNO`)
  - Uno output -> Pi input (`MISO`)
- Enforce strict target select:
  - only one CS asserted
  - non-selected target must not drive MISO
- Validate at low speed first (`100kHz` to `500kHz`), then increase gradually.

## 5) No-rewire test operation

- Keep all USB, I2C, and SPI wiring in place.
- Select active bus/pair by config and firmware role.
- Run USB flash/serial smoke before each bus test batch.
- For matrix expansion, mark unsupported/unsafe pairs as `n/a` in config with reason.

## 6) Matrix templates (config-facing)

Use `i2c_matrix` as the source of truth for I2C pair enablement, **`validation`** (controller + mode per row), and reasons.
For SPI, use the same pattern and keep it commented in `lab.example.yaml` until schema and runners are enabled.

Suggested SPI matrix fields:
- `clock_hz`
- `mode` (0..3)
- `pairs[]` with:
  - `initiator` (`rpi` for v1)
  - `target` (`pico` or `uno`)
  - `status` (`enabled` or `n/a`)
  - `chip_select` (`ce0` / `ce1`)
  - `reason` (required when `status: n/a`)
  - `notes`
