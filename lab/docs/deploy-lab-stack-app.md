# Deploy and validate `lab_stack` on Pico + Uno

Assumes the **always-on** Raspberry Pi gateway (SSH), **USB** to both MCUs, and the **I2C harness** from [lab/pi/docs/bus-wiring.md](../pi/docs/bus-wiring.md). **`lab_stack`** uses the same I2C addresses as `hello_lab` (Pico **0x42**, Uno **0x43**), so **both boards cannot run `hello_lab` and `lab_stack` interchangeably on the same addresses without reflashing**—use one application at a time on the bench.

For the **`hello_lab`** reference path (digest-aligned Docker build, flash both MCUs, I2C from lab config), use **[staged-bootstrap.md](staged-bootstrap.md)** (*Copy-paste: end-to-end bench validation*).

## 1. Build on the dev-host (Docker)

```bash
DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build-lab-stack uno-build-lab-stack CEDE_IMAGE_ID="$DIG"
```

Artifacts:

- `lab/pico/lab_stack/build/lab_stack.uf2`
- `lab/uno/lab_stack/build/lab_stack.ino.hex`

## 2. Flash and validate USB serial (per MCU)

From the **repository root** (defaults: `GATEWAY=pi@cede-pi.local`, quote `GATEWAY_REPO_ROOT` if not default):

```bash
# Pico (expect banner containing CEDE lab_stack rp2 ok)
make pi-gateway-flash-test-pico-lab-stack GATEWAY=pi@cede-pi.local

# Uno (expect CEDE lab_stack ok)
make pi-gateway-flash-test-uno-lab-stack GATEWAY=pi@cede-pi.local
```

Optional: pin digest — `DIGEST=abc123def456 make pi-gateway-flash-test-pico-lab-stack …`

Run records (JSON under `paths.test_results_dir`) include **`application_id`: `lab_stack`** and **`transport_path`: `usb_serial`** when using these targets.

## 3. Validate I2C matrix (Pi → targets)

After both MCUs run **`lab_stack`** and USB checks passed:

```bash
make pi-gateway-validate-i2c-from-lab GATEWAY=pi@cede-pi.local
```

Or single-pair aliases already documented in the root `make help` output.

## 4. Cross-check manifests

Per-directory **`cede_app.yaml`** files document banner prefixes and I2C addresses for automation authors:

- [lab/pico/lab_stack/cede_app.yaml](../pico/lab_stack/cede_app.yaml)
- [lab/uno/lab_stack/cede_app.yaml](../uno/lab_stack/cede_app.yaml)

Central mapping of path keys: **`applications.lab_stack`** in [lab/config/lab.example.yaml](../config/lab.example.yaml).
