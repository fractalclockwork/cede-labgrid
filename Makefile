# Repository root — Python tooling via uv (https://docs.astral.sh/uv/)
REPO_ROOT := $(abspath .)

.PHONY: help sync sync-pi-gateway-flash-deps pi-gateway-sync pi-gateway-health pi-gateway-subtarget-check pi-gateway-print-serial pi-gateway-resolve-port-uno pi-gateway-resolve-port-pico pi-gateway-flash-uno pi-gateway-flash-pico pi-gateway-validate-uno pi-gateway-validate-pico pi-gateway-flash-test-uno pi-gateway-flash-test-pico test-config-local validate docker-test-arch docker-workflow docker-workflow-print test-emulated-docker emulation-environments-test container-test-baseline pi-bootstrap-render pi-fetch-expand pi-raw-sd-image pi-raw-sd-image-force pi-gateway-img-patch pi-gateway-verify-boot pi-gateway-sd-ready pi-gateway-sd-ready-force export-raw-dd pi-dd-flash pi-test-cloud-init pi-verify-boot-img

help:
	@echo "Python (uv):"
	@echo "  make sync              — uv sync (creates .venv, installs deps from uv.lock)"
	@echo "  make validate          — uv sync + full lab/tests pytest (config, cloud-init, toolchain pins)"
	@echo "  make docker-workflow-print — show Docker target order (host → emulated arm64/amd64)"
	@echo "  make docker-workflow   — full Docker target workflow (host + emulated linux/arm64 + linux/amd64 + restore)"
	@echo "  make docker-test-arch  — same as docker-workflow (alias)"
	@echo "  make test-emulated-docker — build orchestration-dev for emulated arch, uname check, restore host images"
	@echo "  make emulation-environments-test — binfmt (best-effort) + native smoke/pytest + emulated-arch orchestration/pytest + restore host"
	@echo "  make container-test-baseline — same as CI: build toolchains, smoke, pico/uno build, test-config, pytest in orchestration-dev"
	@echo "  make test-config-local — pytest lab/config schema without Docker"
	@echo "  make pi-bootstrap-render — uv run pi_bootstrap.py render"
	@echo "  make pi-fetch-expand   — same as pi-raw-sd-image: download + expand official Pi OS to raw .img"
	@echo "  make pi-raw-sd-image  — download + expand to raw block .img (ready for dd; see make pi-dd-flash)"
	@echo "  make export-raw-dd DEVICE=/dev/sdX IMG=path.img — sudo dd raw image / hybrid ISO to disk (Pi SD, x86 USB/HDD; destructive)"
	@echo "    If dd fsync fails: CEDE_DD_NO_FSYNC=1 make export-raw-dd DEVICE=… IMG=… (see BOOT_MEDIA_FLASH.md)"
	@echo "  make pi-dd-flash … — alias of export-raw-dd"
	@echo "  make pi-gateway-sd-ready — fetch/expand + patch boot + verify vs rendered cloud-init (use this for gateway SD; needs sudo)"
	@echo "  make pi-gateway-sd-ready-force — same as pi-gateway-sd-ready with forced re-download/re-expand"
	@echo "  make pi-raw-sd-image / pi-raw-sd-image-force — raw .img only (NOT gateway-ready; run pi-gateway-img-patch + pi-gateway-verify-boot after)"
	@echo "  make pi-gateway-img-patch IMG=path.img — inject cloud-init into .img (sudo)"
	@echo "  make pi-gateway-verify-boot — sudo: verify patched IMG matches lab/pi/cloud-init/rendered/"
	@echo "  make pi-test-cloud-init — pytest offline cloud-init render (hostname in user-data)"
	@echo "  make pi-verify-boot-img IMG=path.img — sudo: verify user-data on .img boot part vs rendered"
	@echo "Example: uv run python lab/pi/bootstrap/pi_bootstrap.py render"
	@echo "Pi emulate / pre-SD: lab/pi/emulate/README.md"
	@echo "Pi SD (needs sudo + terminal): patch-image, flash-file — see lab/pi/docs/cli-flash.md"
	@echo "Pico/Uno flash from Pi (SSH on Pi): make -C lab/pi help — lab/pi/docs/pico-uno-subtargets.md"
	@echo "Pico/Uno from dev-host (SSH into Pi, no shell on Pi):"
	@echo "  make pi-gateway-health | pi-gateway-subtarget-check | pi-gateway-print-serial — remote checks"
	@echo "  make pi-gateway-resolve-port-uno — print cede-uno tty chosen on the gateway"
	@echo "  make pi-gateway-resolve-port-pico — print cede-rp2 (Pico) tty on the gateway"
	@echo "  make pi-gateway-flash-uno [PORT=/dev/tty…] [HEX=path] [SKIP_SYNC=1] — PORT omitted: gateway resolves"
	@echo "  make pi-gateway-flash-pico [UF2=path] [PICO_BOOTSEL_ONLY=1] [PICO_WAIT_MOUNT=…] [SKIP_SYNC=1] — cede-rp2 UF2 (default mount poll ≈3s on Pi; raise if desktop needs automount)"
	@echo "  make pi-gateway-validate-uno [PORT=…] [SKIP_SYNC=1] [UNO_VALIDATE_WAIT=8] — Uno serial banner"
	@echo "  make pi-gateway-validate-pico [PORT=…] [SKIP_SYNC=1] [PICO_VALIDATE_WAIT=3] — cede-rp2 serial banner (override if slow USB)"
	@echo "  make pi-gateway-flash-test-uno [PORT=…] — flash then validate Uno"
	@echo "  make pi-gateway-flash-test-pico [UF2=…] [PICO_BOOTSEL_ONLY=1] — flash then validate cede-rp2"
	@echo "  make sync-pi-gateway-flash-deps / pi-gateway-sync — rsync only lab/pi Makefile + flash scripts (no Docker/firmware tree)"
	@echo "    Uno-only: UNO_ONLY=1 make pi-gateway-sync GATEWAY=…"
	@echo "    Pi repo path: omit GATEWAY_REPO_ROOT for ~/cede on Pi; or quote — GATEWAY_REPO_ROOT='~/src/cede' (unquoted ~/… expands to dev-host home in GNU Make)"

# Push minimal Pi-gateway files for `make -C lab/pi flash-uno` / subtarget-check (see lab/pi/scripts/sync_gateway_flash_deps.sh).
GATEWAY ?= pi@cede-pi.local
# Remote checkout on the Pi. Leave empty: sync uses literal ~/cede on the gateway (see sync_gateway_flash_deps.sh).
# Do not use ?= ~/… here — GNU Make expands ~ to this machine's home and breaks ssh/rsync targets.
GATEWAY_REPO_ROOT ?=
sync-pi-gateway-flash-deps:
	cd "$(REPO_ROOT)" && UNO_ONLY="$(UNO_ONLY)" bash lab/pi/scripts/sync_gateway_flash_deps.sh "$(GATEWAY)" $(if $(strip $(GATEWAY_REPO_ROOT)),"$(GATEWAY_REPO_ROOT)",)

pi-gateway-sync: sync-pi-gateway-flash-deps

# Drive checks / Uno flash from dev-host via SSH (see lab/pi/scripts/devhost_pi_gateway.sh).
pi-gateway-health:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" bash lab/pi/scripts/devhost_pi_gateway.sh health

pi-gateway-subtarget-check:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" bash lab/pi/scripts/devhost_pi_gateway.sh subtarget-check

pi-gateway-print-serial:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" bash lab/pi/scripts/devhost_pi_gateway.sh print-serial

pi-gateway-resolve-port-uno:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" bash lab/pi/scripts/devhost_pi_gateway.sh resolve-port-uno

# Default HEX path: Arduino CLI output for hello_lab; override HEX=...
HEX ?= $(REPO_ROOT)/lab/uno/hello_lab/build/hello_lab.ino.hex
UNO_VALIDATE_WAIT ?= 8
SKIP_SYNC ?=
pi-gateway-flash-uno:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UNO_ONLY="$(UNO_ONLY)" bash lab/pi/scripts/devhost_pi_gateway.sh flash-uno --hex "$(HEX)" $(if $(PORT),--port "$(PORT)",) $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

pi-gateway-validate-uno:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC="$(SKIP_SYNC)" bash lab/pi/scripts/devhost_pi_gateway.sh validate-uno-serial --wait "$(UNO_VALIDATE_WAIT)" $(if $(PORT),--port "$(PORT)",)

pi-gateway-flash-test-uno:
	@$(MAKE) pi-gateway-flash-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)"

pi-gateway-resolve-port-pico:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" bash lab/pi/scripts/devhost_pi_gateway.sh resolve-port-pico

# Default UF2: Pico SDK build output for hello_lab (cede-rp2).
UF2 ?= $(REPO_ROOT)/lab/pico/hello_lab/build/hello_lab.uf2
PICO_BOOTSEL_ONLY ?=
PICO_VALIDATE_WAIT ?= 3
PICO_WAIT_MOUNT ?=
pi-gateway-flash-pico:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" bash lab/pi/scripts/devhost_pi_gateway.sh flash-pico --uf2 "$(UF2)" $(if $(filter 1,$(PICO_BOOTSEL_ONLY)),--bootsel-only,) $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

pi-gateway-validate-pico:
	cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" bash lab/pi/scripts/devhost_pi_gateway.sh validate-pico-serial $(if $(PORT),--port "$(PORT)",)

pi-gateway-flash-test-pico:
	@$(MAKE) pi-gateway-flash-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)"

sync:
	cd "$(REPO_ROOT)" && uv sync

test-config-local:
	cd "$(REPO_ROOT)" && uv run pytest -q lab/tests/test_config_schema.py

validate:
	cd "$(REPO_ROOT)" && uv sync && uv run pytest -q lab/tests/

# Requires Docker. Host images first, then emulated targets (linux/arm64 then linux/amd64), then restore :local for host. On amd64 hosts: make -C lab/docker setup-binfmt once if arm64 fails.
docker-workflow:
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" workflow-docker-all

docker-workflow-print:
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" workflow-docker-print

docker-test-arch: docker-workflow

test-emulated-docker:
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" test-emulated-target

emulation-environments-test:
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" emulation-envs-standup-test

# Parity with .github/workflows/cede-smoke.yml — baseline Tier-0 container operation + full pytest inside orchestration-dev.
container-test-baseline:
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" build-images
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" smoke
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" pico-build
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" uno-build
	$(MAKE) -C "$(REPO_ROOT)/lab/docker" test-config
	cd "$(REPO_ROOT)" && docker compose -f lab/docker/docker-compose.yml run --rm orchestration-dev bash -lc 'cd /workspace && pytest -q lab/tests/'

pi-bootstrap-render:
	cd "$(REPO_ROOT)" && uv run python lab/pi/bootstrap/pi_bootstrap.py render

pi-fetch-expand: pi-raw-sd-image

# Default expanded OS image path (override: make pi-gateway-img-patch IMG=other.img).
IMG ?= lab/pi/dist/raspios_trixie_arm64_latest.img

# Inject rendered cloud-init into raw .img (loop mount). Uses lab/config/lab.yaml or CEDE_LAB_CONFIG — set hostname + authorized_keys_file for SSH.
pi-gateway-img-patch:
	@case "$(IMG)" in /*) _img="$(IMG)" ;; *) _img="$(REPO_ROOT)/$(IMG)" ;; esac; \
	cd "$(REPO_ROOT)" && uv sync && uv run python lab/pi/bootstrap/pi_bootstrap.py patch-image --image "$$_img" --yes

# Loop-mount IMG boot partition vs rendered files (needs sudo interactive terminal typically).
pi-gateway-verify-boot:
	@case "$(IMG)" in /*) _img="$(IMG)" ;; *) _img="$(REPO_ROOT)/$(IMG)" ;; esac; \
	sudo "$(REPO_ROOT)/lab/pi/scripts/verify_boot_image.sh" "$$_img" --compare-rendered

# Download + expand OS, then patch boot partition for DHCP + SSH gateway bring-up (Pi 3 B ref.).
pi-gateway-sd-ready: pi-raw-sd-image pi-gateway-img-patch pi-gateway-verify-boot

# Raw disk image for SD / USB writer (from lab YAML os_image.url / cache_path). Default example: Pi OS lite arm64 (Debian Trixie+ cloud-init).
pi-raw-sd-image:
	cd "$(REPO_ROOT)" && uv sync && uv run python lab/pi/bootstrap/pi_bootstrap.py fetch-image
	cd "$(REPO_ROOT)" && uv run python lab/pi/bootstrap/pi_bootstrap.py expand-image
	@echo "Raw block image (sector-for-sector disk dump) ready under lab/pi/dist/*.img (gitignored)."
	@echo "NOTE: unpatched upstream image — for gateway SD run: make pi-gateway-img-patch && make pi-gateway-verify-boot (or make pi-gateway-sd-ready)."
	@echo "Flash with: make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/<file>.img   OR  Raspberry Pi Imager / pi_bootstrap flash-file"

# Re-download official image and decompress again (ignores cached .xz / .img — network heavy).
pi-raw-sd-image-force:
	cd "$(REPO_ROOT)" && uv sync && uv run python lab/pi/bootstrap/pi_bootstrap.py fetch-image --force
	cd "$(REPO_ROOT)" && uv run python lab/pi/bootstrap/pi_bootstrap.py expand-image --force
	@echo "Raw block image rebuilt under lab/pi/dist/*.img (gitignored)."
	@echo "NOTE: unpatched upstream image — gateway path: make pi-gateway-img-patch && make pi-gateway-verify-boot (or pi-gateway-sd-ready-force)."
	@echo "Flash with: make export-raw-dd DEVICE=/dev/sdX IMG=lab/pi/dist/<file>.img"

# Clean rebuild: forced fetch/expand + cloud-init patch + verify (sudo).
pi-gateway-sd-ready-force: pi-raw-sd-image-force pi-gateway-img-patch pi-gateway-verify-boot

# Export any raw / hybrid-dd image to a whole block device (SD, USB stick, SATA/NVMe disk, etc.).
export-raw-dd pi-dd-flash:
	@test -n "$(DEVICE)" || (echo "Set DEVICE=/dev/sdX or /dev/nvme0n1 (whole disk, not a partition)" >&2; exit 1)
	@test -n "$(IMG)" || (echo "Set IMG=… e.g. lab/pi/dist/raspios_trixie_arm64_latest.img or ~/Downloads/debian-live-amd64.iso" >&2; exit 1)
	@case "$(IMG)" in /*) _img="$(IMG)" ;; *) _img="$(REPO_ROOT)/$(IMG)" ;; esac; \
	sudo "$(REPO_ROOT)/lab/pi/scripts/flash_raw_to_device.sh" --device "$(DEVICE)" --image "$$_img" --yes

pi-test-cloud-init:
	cd "$(REPO_ROOT)" && uv run pytest -q lab/tests/test_pi_cloud_init_render.py

# Usage: make pi-verify-boot-img IMG=lab/pi/dist/foo.img
pi-verify-boot-img:
	@test -n "$(IMG)" || (echo "Set IMG=lab/pi/dist/your.img" >&2; exit 1)
	sudo "$(REPO_ROOT)/lab/pi/scripts/verify_boot_image.sh" "$(IMG)"
