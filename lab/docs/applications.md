# Firmware applications (multi-target products)

A **target** is physical (`pico`, `uno`, `pi`). An **application** is something you ship—often firmware in **`lab/pico/<app>/`** and **`lab/uno/<app>/`** with the **same application id** so the gateway can orchestrate both.

## Layout

- Reference firmware: **`hello_lab`** (default Docker/Make builds).
- Second reference app: **`lab_stack`** — sibling folders [lab/pico/lab_stack](../pico/lab_stack/) and [lab/uno/lab_stack](../uno/lab_stack/), each with **`cede_app.yaml`** describing USB/I2C resources for tooling.
- **Pi gateway application:** **`ssd1306_dual`** — Python on the Raspberry Pi driving two SSD1306 OLEDs over Linux I2C ([lab/pi/ssd1306_dual/README.md](../pi/ssd1306_dual/README.md)); registered under **`applications.ssd1306_dual.targets.pi`** with path keys in `lab.example.yaml`.
- **`ssd1306_eyes`** — dual OLED **cartoon eyes** (blink + gaze) on the gateway ([lab/pi/ssd1306_eyes/README.md](../pi/ssd1306_eyes/README.md)); **`applications.ssd1306_eyes.targets.pi`**.

## Configuration

- **`paths.*`** — artifact locations (additive keys such as `lab_stack_pico_build`).
- **`applications`** — maps `application_id` → per-target **`paths_build_key`** / **`paths_artifact_glob_key`** (see [lab.example.yaml](../config/lab.example.yaml)).
- **`targets`** — hardware roles (`pico` / `uno` / `pi`), unchanged.

## Builds

```bash
DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build-lab-stack uno-build-lab-stack CEDE_IMAGE_ID="$DIG"
# or
make -C lab/docker pico-build PICO_APP=lab_stack uno-build UNO_APP=lab_stack CEDE_IMAGE_ID="$DIG"
```

Pass **`CEDE_IMAGE_ID`** so USB banners match **`DIGEST`** / git short during **`pi-gateway-flash-test-*`** (same issue as **`hello_lab`** in Docker).

Deploy + validate from repo root (requires gateway + hardware): see [deploy-lab-stack-app.md](deploy-lab-stack-app.md).

Baseline **`hello_lab` E2E** (toolchain → flash both → I2C matrix copy-paste): [staged-bootstrap.md](staged-bootstrap.md).
