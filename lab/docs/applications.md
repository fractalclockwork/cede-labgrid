# Firmware applications (multi-target products)

A **target** is physical (`pico`, `uno`, `pi`). An **application** is something you ship—often firmware in **`lab/pico/<app>/`** and **`lab/uno/<app>/`** with the **same application id** so the gateway can orchestrate both.

## Layout

- Reference firmware: **`hello_lab`** (default Docker/Make builds).
- Demo app: **`i2c_hello`** — under [demo_apps/pico/i2c_hello](../../demo_apps/pico/i2c_hello/) and [demo_apps/uno/i2c_hello](../../demo_apps/uno/i2c_hello/), each with **`cede_app.yaml`** describing USB/I2C resources for tooling.
- **Pi gateway demo applications** live under **`demo_apps/`** — each has its own `cede_app.yaml` manifest and self-contained Makefile. See `demo_apps/*/README.md` for per-app details.

## Configuration

Each application is self-describing via its **`cede_app.yaml`** manifest — no
registration in `lab/config/lab.example.yaml` is needed. The manifest declares
the `application_id`, target type, `entrypoint`, and hardware resources.

## Builds

```bash
DIG=$(git rev-parse --short=12 HEAD)
make -C lab/docker pico-build-i2c-hello uno-build-i2c-hello CEDE_IMAGE_ID="$DIG"
```

Pass **`CEDE_IMAGE_ID`** so USB banners match the expected digest during validation.

## Deploy + validate

**LabGrid (preferred):**

```bash
make lg-test-pico-i2c-hello   # flash + validate i2c_hello on Pico
make lg-test-uno-i2c-hello    # flash + validate i2c_hello on Uno
```

**SSH escape hatch:** see [deploy-lab-stack-app.md](deploy-lab-stack-app.md).

Baseline **`hello_lab` E2E** (toolchain → flash both → I2C): [staged-bootstrap.md](staged-bootstrap.md).
