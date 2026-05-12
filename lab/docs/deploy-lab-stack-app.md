# Deploy and validate `i2c_hello` on Pico + Uno

Assumes the **always-on** Raspberry Pi gateway (SSH), **USB** to both MCUs, and the **I2C harness** from [lab/pi/docs/bus-wiring.md](../pi/docs/bus-wiring.md). **`i2c_hello`** uses the same I2C addresses as `hello_lab` (Pico **0x42**, Uno **0x43**), so **both boards cannot run `hello_lab` and `i2c_hello` interchangeably on the same addresses without reflashing**—use one application at a time on the bench.

For the **`hello_lab`** reference path (digest-aligned Docker build, flash both MCUs, I2C from lab config), use **[staged-bootstrap.md](staged-bootstrap.md)** (*Copy-paste: end-to-end bench validation*).

## 1. Build on the dev-host (Docker)

```bash
DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build-i2c-hello uno-build-i2c-hello CEDE_IMAGE_ID="$DIG"
```

Artifacts:

- `demo_apps/pico/i2c_hello/build/i2c_hello.uf2`
- `demo_apps/uno/i2c_hello/build/i2c_hello.ino.hex`

## 2. Flash and validate USB serial (per MCU)

**LabGrid (preferred):**

```bash
make lg-test-pico-i2c-hello    # flash + validate Pico
make lg-test-uno-i2c-hello     # flash + validate Uno
```

**SSH escape hatch** (when LabGrid coordinator/exporter not running):

```bash
make pi-gateway-flash-test-pico-lab-stack GATEWAY=pi@cede-pi.local
make pi-gateway-flash-test-uno-lab-stack GATEWAY=pi@cede-pi.local
```

## 3. Validate I2C (Pi → targets)

After both MCUs run **`i2c_hello`** and USB checks passed:

```bash
make lg-test-i2c    # LabGrid CedeI2CDriver (preferred)
```

## 4. Cross-check manifests

Per-directory **`cede_app.yaml`** files document banner prefixes and I2C addresses for automation authors:

- [demo_apps/pico/i2c_hello/cede_app.yaml](../../demo_apps/pico/i2c_hello/cede_app.yaml)
- [demo_apps/uno/i2c_hello/cede_app.yaml](../../demo_apps/uno/i2c_hello/cede_app.yaml)
