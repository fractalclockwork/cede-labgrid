# Toolchains and container images (Dev-Host)

This is the **inventory of built tools and cross-compilers** in CEDE. Use it to map **Tier 0 (laptop + Docker)** to real OCI images before designing cluster or topology layers.

**Bare-metal vs containers:** the Dev-Host uses **Docker images** (`linux/amd64` / `linux/arm64`), not a repo-supplied PC boot ISO; the Pi gateway uses a **Raspberry Pi OS disk image** plus cloud-init — see [BOOT_IMAGES.md](BOOT_IMAGES.md).

**Version pins:** all images share the same pin file: [`lab/docker/TOOLCHAIN_VERSIONS`](../lab/docker/TOOLCHAIN_VERSIONS).

---

## Compose services ([`lab/docker/docker-compose.yml`](../lab/docker/docker-compose.yml))

| Service | Image tag | Role |
|---------|-----------|------|
| **pico-dev** | `cede/pico-dev:local` | Pico SDK + ARM GCC cross-build |
| **arduino-dev** | `cede/arduino-dev:local` | AVR GCC + avrdude + Arduino CLI |
| **orchestration-dev** | `cede/orchestration-dev:local` | Python lab tests, YAML/schema, serial orchestration |
| **rpi-imager-dev** | `cede/rpi-imager-dev:local` | Host-side SD imaging (`rpi-imager`), not a compiler |

Build all Dev-Host images for **this machine’s architecture** (explicit `linux/amd64` or `linux/arm64`):

```bash
make -C lab/docker build-images
# same as:
make -C lab/docker build-images-host
```

**Target workflow** (same order: **host** → **emulated `linux/arm64` (aarch64 / RPi)** → **emulated `linux/amd64` (x86_64)** when the host is the other; then **restore host** `:local` tags):

```bash
make docker-workflow-print    # show steps only
make docker-workflow          # full matrix (alias: make docker-test-arch)
make -C lab/docker workflow-docker-all
```

Individual steps: `workflow-docker-host`, `workflow-emulated-arm64`, `workflow-emulated-amd64`, `workflow-emulated-targets` (cross-only). Manual CI run: [`.github/workflows/docker-target-workflow.yml`](../.github/workflows/docker-target-workflow.yml) (`workflow_dispatch`).

On an **amd64** PC, ARM64 Dockerfile steps need QEMU binfmt once if builds fail with `exec format error`:

```bash
make -C lab/docker setup-binfmt
```

Architecture selection uses merged Compose files (`docker-compose.platform-amd64.yml`, `docker-compose.platform-arm64.yml`) so older `docker compose` builds work without a `--platform` CLI flag. After `build-images-all-arch`, the Makefile **rebuilds host images** so `cede/*:local` matches this machine again for `compose run` / `smoke`.

**Emulated runtime smoke** (build `orchestration-dev` for the non-native arch, assert `uname -m`, restore host tags):

```bash
make test-emulated-docker
# or: make -C lab/docker test-emulated-target
```

---

## Cross-compilers and key binaries

### `pico-dev` ([`lab/docker/pico-dev/Dockerfile`](../lab/docker/pico-dev/Dockerfile))

| Component | Details |
|-----------|---------|
| **Cross GCC** | `gcc-arm-none-eabi` (ARM Cortex-M), `libnewlib-arm-none-eabi`, `libstdc++-arm-none-eabi-newlib` |
| **SDK** | Raspberry Pi **Pico SDK** at `/opt/pico-sdk`, branch/tag from **`PICO_SDK_VERSION`** in `TOOLCHAIN_VERSIONS` |
| **Build** | cmake, ninja |
| **Utility** | **picotool** (built from source in image) |
| **Smoke** | `arm-none-eabi-gcc --version`, `picotool version`, … |

Firmware outputs (Hello Lab): **`lab/pico/hello_lab/build`** (UF2 / ELF).

```bash
make -C lab/docker pico-build
```

---

### `arduino-dev` ([`lab/docker/arduino-dev/Dockerfile`](../lab/docker/arduino-dev/Dockerfile))

| Component | Details |
|-----------|---------|
| **Cross GCC** | **gcc-avr**, **avr-libc**, **binutils-avr** |
| **Flash** | **avrdude** |
| **CLI** | **arduino-cli** (release **`ARDUINO_CLI_VERSION`** from `TOOLCHAIN_VERSIONS`), core **`arduino:avr`** installed at image build |

Firmware outputs (Hello Lab): **`lab/uno/hello_lab/build`** (HEX).

```bash
make -C lab/docker uno-build
```

---

### `orchestration-dev` ([`lab/docker/orchestration-dev/Dockerfile`](../lab/docker/orchestration-dev/Dockerfile))

| Component | Details |
|-----------|---------|
| **Runtime** | Python **3.12** (see `PYTHON_MINOR` in pins) |
| **Libraries** | `pyserial`, `pyyaml`, `jsonschema`, `pytest` |

Used for **`make -C lab/docker test-config`**, lab orchestration, and gateway-oriented workflows. **ARM64** gateway image: **`make -C lab/docker build-gateway-images`** → save tarball per [`README.md`](../README.md).

---

### `rpi-imager-dev` ([`lab/docker/rpi-imager/Dockerfile`](../lab/docker/rpi-imager/Dockerfile))

Ubuntu-based image with **`rpi-imager`**, **`qemu-system-aarch64`** tooling deps; used for **privileged** SD / loop workflows on the Dev-Host ([`lab/pi/docs/cli-flash.md`](../lab/pi/docs/cli-flash.md)).

---

## Validation gates (local)

| Gate | Command | Notes |
|------|---------|--------|
| **Python / lab config** | `make test-config-local` | `pytest` schema validation (`lab.example.yaml`) |
| **Rendered cloud-init** | `make pi-test-cloud-init` | Hostname in rendered `user-data` |
| **Full pytest** | `make validate` | All tests under `lab/tests/` |
| **Dev-Host vs emulated ARM** | `pytest lab/tests/test_docker_dev_host_matrix.py` | Intel **`linux/amd64`** compose pins vs **`linux/arm64`** emulated stack; markers `dev_host_intel`, `emulated_linux_arm64` |
| **Docker toolchains** | `make -C lab/docker smoke` | Requires images built; checks compilers inside containers |
| **Docker multi-arch** | `make docker-workflow` | Host → emulated `linux/arm64` → `linux/amd64` → restore host; slow (`docker-test-arch` alias) |
| **Emulation envs + tests** | `make emulation-environments-test` | Native toolchain smoke + pytest in `orchestration-dev`, then emulated orchestration + pytest, restore host |

One-shot:

```bash
make validate
```

---

## Related

- [CONTAINER_BOOTSTRAP.md](CONTAINER_BOOTSTRAP.md) — staged pipeline  
- [DESIGN.md](../DESIGN.md) — Dev-Host vs gateway vs MCU roles  
- [lab/docker/Makefile](../lab/docker/Makefile) — targets reference  
