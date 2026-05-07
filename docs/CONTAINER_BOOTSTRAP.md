# Unified containerized embedded bootstrap

CEDE’s **base operation** is a **repeatable pipeline**: **build container artifacts on the Dev-Host → validate each layer → deploy an image or bundle to hardware → run container workloads on the device**, with **explicit checks at every step**. Board vendors (Raspberry Pi, BeagleBone, future targets) are **profiles** over this pipeline—not separate silos.

---

## Goals

1. **Single mental model** — Same stages for any supported embedded gateway: configurable OS/bootstrap injection + container runtime + workload images.
2. **Containers as the unit of deployment** — Toolchains and orchestration ship as OCI images; the device runs a small host OS plus **Docker/Podman** (or equivalent), not ad-hoc installs scattered across READMEs.
3. **Validation at each step** — Nothing relies on “it booted once”; gates are automated or scripted where possible, with documented manual fallbacks (serial, shell on device).
4. **CI/Dev-Host parity** — The same images and checks run locally (`make`, `uv`, Docker) and in automation.

---

## Pipeline stages and validation gates

| Stage | What happens | Validation (examples) |
|-------|----------------|------------------------|
| **A — Toolchain & orchestration images** | Build Dev-Host/CI images from Dockerfiles (`lab/docker/…`): Pico, Arduino, orchestration, optional imaging helpers. | `make -C lab/docker smoke`, CI workflow builds images. |
| **B — Lab contract** | Machine and topology described in **`lab/config/lab.yaml`** (schema-validated). | `make test-config-local` / `make -C lab/docker test-config`. |
| **C — Bootstrap payload** | Profile-specific first-boot config (e.g. **cloud-init** `user-data`/`meta-data`) + hostname, network, SSH keys. Render from YAML; inject into boot partition or image. | `make pi-test-cloud-init`, `make pi-bootstrap-render`, `sudo lab/pi/scripts/verify_boot_image.sh … [--compare-rendered]` (RPi profile today). |
| **D — Deployable disk image** | Base OS image + injected bootstrap (optional golden `.img` patch, then flash SD/eMMC). | Offline image inspection; optional QEMU serial smoke (`lab/pi/scripts/qemu_smoke_rpi_img.sh`); flash/prepare scripts exit non-zero on failure. |
| **E — Hardware bring-up** | Device boots, network reachable, SSH or serial shell available. | `ssh … exit`, orchestration container starts on gateway (existing Pi bootstrap path). |
| **F — Runtime workloads** | Pull/load workload images on device; orchestration, MCU tooling, tests. | `make -C lab/docker` gateway saves; on-device `docker load` / compose; **Hello Lab** / pytest tiers with hardware skips. |

Stages **C–D** are where **profile plugins** live (RPi vs BeagleBone vs generic ARM): same contract, different OS image URL, injector, and validation hooks.

---

## Profiles (conceptual)

| Profile | Host OS source | Bootstrap injector | Notes |
|---------|----------------|---------------------|--------|
| **`rpi64`** (current reference) | Raspberry Pi OS Lite arm64 `.img` | cloud-init on FAT bootfs | Scripts under `lab/pi/bootstrap/`, `lab/pi/scripts/`. |
| **`beaglebone`** (future) | Debian/armhf or TI image | cloud-init / **Connman** / board-specific first-boot | Map into same render→verify→flash stages with a different YAML block. |
| **`generic-aarch64`** (future) | Minimal Debian/Ubuntu cloud image | cloud-init / ignition | QEMU or hardware; same validation ladder. |

The **`lab/config/lab.schema.json`** namespace can grow an optional **`embedded_profile`** (or similar) when a second board is implemented—without renaming existing **`hosts.pi`** fields used by current tests.

---

## What “containerized” means here

- **Dev-Host / CI**: Everything reproducible runs in **Docker** (or **`uv`** for lightweight Python gates).
- **Device**: The gateway runs **containerized orchestration** (e.g. `orchestration-dev` image on ARM64) alongside host services—**not** running the full dev GUI stack on the MCU.

MCU targets (Pico, Uno) remain **firmware + USB serial**; the **gateway** is where containers execute.

---

## Current repository mapping

| Stage | Location today |
|-------|----------------|
| A | `lab/docker/Makefile`, `docker-compose.yml`, Dockerfiles |
| B | `lab/config/lab.yaml`, `lab.schema.json`, `lab/tests/test_config_schema.py` |
| C–D (RPi) | `lab/pi/bootstrap/pi_bootstrap.py`, `lab/pi/scripts/*.sh`, `lab/pi/emulate/README.md` |
| E–F | `lab/pi/bootstrap/bootstrap_pi.sh`, `lab/docker/docker-compose.gateway.yml`, `lab/tests/` |

---

## Roadmap (incremental)

1. Factor **`embedded_profile`** (or parallel **`hosts.gateway`**) in lab config when adding BeagleBone—keep RPi path stable.
2. Extract **generic** “render bootstrap → verify boot partition → flash” interfaces from Pi-specific paths where practical (shared `lab/bootstrap/lib/` shell helpers).
3. Add **CI job** that runs **offline** stages A–C on every PR (no hardware).
4. Document **on-device validation checklist** (Docker daemon, compose up, single orchestration health probe).

---

## Related

- [BOOT_IMAGES.md](BOOT_IMAGES.md) — **PC Dev-Host vs Raspberry Pi disk image** — what boots bare metal vs what is Docker/OCI  
- [BOOT_MEDIA_FLASH.md](BOOT_MEDIA_FLASH.md) — **`dd`** raw/hybrid images to SD, USB, HDD/NVMe (`make export-raw-dd`)  
- [TOOLCHAINS.md](TOOLCHAINS.md) — **built tools & cross-compilers** (Docker images, pins, `make validate`)  
- [DESIGN.md](../DESIGN.md) — roles, three-tier lab, philosophy  
- [README.md](../README.md) — quick start and Docker/uv commands  
- [lab/pi/emulate/README.md](../lab/pi/emulate/README.md) — pre-flash image verification & QEMU smoke  
