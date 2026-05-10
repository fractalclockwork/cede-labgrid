# `ssd1306_dual` — dual SSD1306 on the Pi

Python application for the **Raspberry Pi gateway** that drives **two** SSD1306 I2C OLED modules on the same Linux I2C bus.

## Wiring

- **Power:** `3V3` + `GND` from the Pi (breakouts are 3.3 V logic).
- **I2C:** `SDA` → Pi pin 3 (`GPIO2` / `SDA1`), `SCL` → Pi pin 5 (`GPIO3` / `SCL1`). Use **bus `1`** (`i2cdetect -y 1`).
- **Addresses:** Both panels must have **different** 7-bit addresses on one bus. Typical factory defaults:
  - **`0x3C`** — SA0 / ADDR pin low (often printed as `0x78` in 8-bit form on datasheets).
  - **`0x3D`** — SA0 high (solder jumper or strap on the breakout).

If both boards came fixed at `0x3C`, use a breakout that exposes ADDR, an **I2C multiplexer**, or move one display to another bus.

**Harness coexistence:** Lab MCUs on the level-shifter harness use **`0x42`** / **`0x43`** ([bus-wiring.md](../docs/bus-wiring.md)). SSD1306 modules use **`0x3C`** / **`0x3D`**, so they can share the **same** Pi I2C bus **without** address clashes.

## Setup on the Pi

From the sparse gateway tree (after [sync_gateway_flash_deps.sh](../scripts/sync_gateway_flash_deps.sh)), or a full checkout:

```bash
cd ~/cede/lab/pi/ssd1306_dual
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Or: python3 -m pip install --user -r requirements.txt
# (On PEP 668–managed OS images you may need a venv or pip --break-system-packages.)
# Ensure user is in group i2c (bootstrap_pi.sh does this):
groups | grep -q i2c || sudo usermod -aG i2c "$USER"
```

Run:

```bash
.venv/bin/python main.py
# or: python3 main.py
```

Optional: `python3 main.py --bus 1 --addr-a 0x3C --addr-b 0x3D --fps 12`

Stop with **Ctrl+C** (blank display on exit).

## From dev-host (SSH)

Run against **`cede-pi`** from the **repository root** (runs **`sync_gateway_flash_deps.sh`**, **`make -C lab/pi ssd1306-dual-install`**, then **`ssd1306-dual-run`** on the gateway until **Ctrl+C**):

```bash
make pi-gateway-ssd1306-dual GATEWAY=pi@cede-pi.local
```

If the sparse tree is already up to date: **`SKIP_SYNC=1 make pi-gateway-ssd1306-dual`**.

### Bus throughput benchmark

Full-frame alternating fills on **both** panels (same code path as `main.py`). Reports **dual rounds/s** (one full refresh of each display per round), panel draws/s, and approximate framebuffer KiB/s.

On the **gateway**:

```bash
make -C ~/cede/lab/pi ssd1306-dual-bus-speed
# Longer sample: SSD1306_SPEED_DURATION=20 make -C ~/cede/lab/pi ssd1306-dual-bus-speed
```

From the **dev-host** (sync + install + benchmark):

```bash
make pi-gateway-ssd1306-dual-bus-speed GATEWAY=pi@cede-pi.local
# Optional: SSD1306_SPEED_DURATION=15 make pi-gateway-ssd1306-dual-bus-speed
```

JSON for scripts: **`python3 bus_speed_test.py --duration 10 --json`**.

To maximize line rate, raise the Pi I2C clock when wiring allows (e.g. **`dtparam=i2c_arm_baudrate=400000`** in `/boot/firmware/config.txt`) and reboot — compare before/after with this benchmark.

## Lab configuration

See root **`applications.ssd1306_dual.targets.pi`** in `lab/config/lab.example.yaml` — path keys point at this folder and `main.py` for tooling that resolves application artifacts.
