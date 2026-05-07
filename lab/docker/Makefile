# Run from repo root: make -C lab/docker <target>
# Or from lab/docker: make <target>

REPO_ROOT := $(abspath ../..)
DOCKER_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
COMPOSE := docker compose -f $(DOCKER_DIR)docker-compose.yml
# Merge base compose + platform locks (when PLATFORM_TAG is amd64 or arm64).
COMPOSE_PLATFORM = docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-$(PLATFORM_TAG).yml
COMPOSE_ARM64 := docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-arm64.yml
COMPOSE_AMD64 := docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-amd64.yml

# Orchestration-only pytest bundle (no GNU make required inside image).
EMULATION_ORCH_PYTEST := lab/tests/test_ssh_key_sharing_e2e.py lab/tests/test_pi_cloud_init_render.py lab/tests/test_config_schema.py lab/tests/test_toolchain_versions.py lab/tests/test_docker_dev_host_matrix.py

# Docker platform matching this machine (linux/amd64 vs linux/arm64). Used for explicit native builds.
UNAME_M := $(shell uname -m)
ifeq ($(UNAME_M),x86_64)
  HOST_PLATFORM := linux/amd64
else ifeq ($(UNAME_M),aarch64)
  HOST_PLATFORM := linux/arm64
else ifeq ($(UNAME_M),arm64)
  HOST_PLATFORM := linux/arm64
else
  HOST_PLATFORM := linux/$(UNAME_M)
endif

# Override compose fragment per arch (docker-compose.platform-{amd64,arm64}.yml).
ifeq ($(HOST_PLATFORM),linux/amd64)
  PLATFORM_TAG := amd64
else ifeq ($(HOST_PLATFORM),linux/arm64)
  PLATFORM_TAG := arm64
else
  PLATFORM_TAG :=
endif

# Cross-build order after native: Raspberry Pi gateway (arm64) before amd64 when both are needed.
CROSS_PLATFORMS :=
ifneq ($(HOST_PLATFORM),linux/arm64)
  CROSS_PLATFORMS += linux/arm64
endif
ifneq ($(HOST_PLATFORM),linux/amd64)
  CROSS_PLATFORMS += linux/amd64
endif

# ---------------------------------------------------------------------------
# Target workflow: native host first, then emulated/cross OCI targets.
#   • linux/arm64 — aarch64 (Raspberry Pi gateway / Apple Silicon class)
#   • linux/amd64 — x86_64 (typical CI / PC Dev-Host)
# On an amd64 host, arm64 Dockerfile RUN steps use QEMU via binfmt — run setup-binfmt once if builds fail.
# ---------------------------------------------------------------------------

.PHONY: print-host-platform workflow-docker-print workflow-docker-host workflow-emulated-arm64 workflow-emulated-amd64 workflow-emulated-targets workflow-docker-all test-emulated-target emulation-native-test emulation-cross-test emulation-envs-standup-test build-images build-images-host build-images-arm64 build-images-amd64 build-images-cross build-images-all-arch build-rpi-imager build-gateway-images save-gateway-orchestration setup-binfmt smoke pico-build uno-build test-config shell-pico shell-arduino shell-orch shell-rpi-imager pi-bootstrap-render

workflow-docker-print:
	@echo "CEDE Docker target workflow (compose images)"
	@echo "  Step 1 — host (native):     $(HOST_PLATFORM)"
	@echo "  Step 2 — emulated/cross:    $(strip $(CROSS_PLATFORMS))  (order: arm64 then amd64 when both)"
	@echo "  Step 3 — after cross-build: restore :local for host (workflow-docker-all only)"

workflow-docker-host: build-images-host

# aarch64 / ARM64 — primary emulated path from x86_64 Dev-Hosts (RPi deployment smoke).
workflow-emulated-arm64: build-images-arm64

# x86_64 — emulated path from aarch64 Dev-Hosts (CI/desktop parity).
workflow-emulated-amd64: build-images-amd64

# Emulated targets only (no host bookend): arm64 first, then amd64 when applicable.
workflow-emulated-targets: build-images-cross

# Full matrix: host → emulated targets → restore host images for compose run/smoke.
workflow-docker-all: build-images-all-arch

# Proof that non-native arch runs (QEMU/binfmt): build orchestration-dev only, check uname -m, restore host :local.
test-emulated-target:
ifeq ($(HOST_PLATFORM),linux/amd64)
	@echo "=== emulated target: linux/arm64 (orchestration-dev) ==="
	$(COMPOSE_ARM64) build orchestration-dev
	$(COMPOSE_ARM64) run --rm orchestration-dev bash -lc 'test "$$(uname -m)" = aarch64'
	@echo "emulated aarch64 userspace in container: ok"
	@$(MAKE) build-images-host
else ifeq ($(HOST_PLATFORM),linux/arm64)
	@echo "=== emulated target: linux/amd64 (orchestration-dev) ==="
	$(COMPOSE_AMD64) build orchestration-dev
	$(COMPOSE_AMD64) run --rm orchestration-dev bash -lc 'test "$$(uname -m)" = x86_64'
	@echo "emulated x86_64 userspace in container: ok"
	@$(MAKE) build-images-host
else
	@echo "test-emulated-target: unsupported host $(HOST_PLATFORM) (need linux/amd64 or linux/arm64)" >&2
	@exit 1
endif

# Native Dev-Host stack + toolchain smoke + pytest in orchestration (no `make` required for chosen tests).
emulation-native-test:
	$(MAKE) build-images-host
	$(MAKE) smoke
ifeq ($(PLATFORM_TAG),)
	$(COMPOSE) run --rm orchestration-dev bash -lc 'cd /workspace && pytest -q $(EMULATION_ORCH_PYTEST)'
else
	$(COMPOSE_PLATFORM) run --rm orchestration-dev bash -lc 'cd /workspace && pytest -q $(EMULATION_ORCH_PYTEST)'
endif

# Emulated opposite arch: orchestration image only + same pytest bundle + uname assertion (QEMU userspace).
emulation-cross-test:
ifeq ($(HOST_PLATFORM),linux/amd64)
	@echo "=== emulated environment: linux/arm64 orchestration-dev ==="
	$(COMPOSE_ARM64) build orchestration-dev
	$(COMPOSE_ARM64) run --rm orchestration-dev bash -lc 'cd /workspace && pytest -q $(EMULATION_ORCH_PYTEST) && test "$$(uname -m)" = aarch64'
else ifeq ($(HOST_PLATFORM),linux/arm64)
	@echo "=== emulated environment: linux/amd64 orchestration-dev ==="
	$(COMPOSE_AMD64) build orchestration-dev
	$(COMPOSE_AMD64) run --rm orchestration-dev bash -lc 'cd /workspace && pytest -q $(EMULATION_ORCH_PYTEST) && test "$$(uname -m)" = x86_64'
else
	@echo "emulation-cross-test: unsupported host $(HOST_PLATFORM)" >&2
	@exit 1
endif

# Binfmt (best-effort) → native env test → emulated-arch orchestration test → restore host :local.
emulation-envs-standup-test:
	-$(MAKE) setup-binfmt
	@echo "=== Environment 1: native $(HOST_PLATFORM) (all toolchain images + smoke + pytest) ==="
	$(MAKE) emulation-native-test
	@echo "=== Environment 2: emulated cross-arch orchestration + pytest ==="
	$(MAKE) emulation-cross-test
	@echo "=== Restore host images for daily compose use ==="
	$(MAKE) build-images-host

print-host-platform:
	@echo $(HOST_PLATFORM)

# Default: all compose services for this machine’s architecture (explicit platform via compose merge).
build-images: build-images-host

build-images-host:
ifeq ($(PLATFORM_TAG),)
	@echo "=== docker compose build (host: $(HOST_PLATFORM); no amd64/arm64 override file) ==="
	$(COMPOSE) build
else
	@echo "=== docker compose build (host: $(HOST_PLATFORM)) ==="
	$(COMPOSE_PLATFORM) build
endif

# Raspberry Pi OS 64-bit gateway / Apple Silicon–class hosts (explicit arch).
build-images-arm64:
	@echo "=== docker compose build (linux/arm64) ==="
	docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-arm64.yml build

build-images-amd64:
	@echo "=== docker compose build (linux/amd64) ==="
	docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-amd64.yml build

# Each supported platform except host, in order: arm64 (RPi) first, then amd64.
build-images-cross:
	@for p in $(CROSS_PLATFORMS); do \
		tag=$${p#linux/}; \
		echo "=== docker compose build ($$p) ==="; \
		docker compose -f $(DOCKER_DIR)docker-compose.yml -f $(DOCKER_DIR)docker-compose.platform-$$tag.yml build || exit $$?; \
	done

# Validation gate: native images first, then each other supported architecture (RPi arm64 before amd64).
# Cross-builds overwrite :local tags; rebuild host last so compose run/smoke match this machine.
build-images-all-arch: build-images-host build-images-cross
ifneq ($(strip $(CROSS_PLATFORMS)),)
	@echo "=== restoring :local images for host ($(HOST_PLATFORM)) after cross-builds ==="
	@$(MAKE) build-images-host
endif

build-rpi-imager:
	$(COMPOSE) build rpi-imager-dev

# One-time on many amd64 Dev-Hosts: enable QEMU binfmt so ARM64 Dockerfile steps run.
setup-binfmt:
	docker run --privileged --rm tonistiigi/binfmt --install all

# ARM64 images for Raspberry Pi gateway (Pi 3 / Pi 4 / Pi 5 with 64-bit OS).
# Requires Docker Buildx. On amd64, run `make setup-binfmt` once if builds fail with "exec format error".
build-gateway-images:
	docker buildx build --platform linux/arm64 --load \
		-t cede/orchestration-dev:arm64 \
		-f $(DOCKER_DIR)orchestration-dev/Dockerfile \
		$(DOCKER_DIR)orchestration-dev

# Save orchestration image for USB transfer to a Pi (gzip tarball).
save-gateway-orchestration:
	mkdir -p $(REPO_ROOT)/lab/pi/dist
	docker save cede/orchestration-dev:arm64 | gzip > $(REPO_ROOT)/lab/pi/dist/orchestration-dev_arm64.tar.gz
	@echo "Wrote $(REPO_ROOT)/lab/pi/dist/orchestration-dev_arm64.tar.gz"

smoke: build-images
	$(COMPOSE) run --rm pico-dev bash -lc 'arm-none-eabi-gcc --version && cmake --version && ninja --version && picotool version'
	$(COMPOSE) run --rm arduino-dev bash -lc 'avr-gcc --version && avrdude -v 2>&1 | head -n 1 && arduino-cli version'
	$(COMPOSE) run --rm orchestration-dev bash -lc 'python -c "import serial, yaml, jsonschema; import pytest"'

pico-build:
	$(COMPOSE) run --rm pico-dev bash -lc '\
		set -e; \
		cd /workspace/lab/pico/hello_lab && \
		rm -rf build && mkdir build && cd build && \
		cmake -GNinja -DCMAKE_BUILD_TYPE=Release .. && \
		ninja \
	'

uno-build:
	$(COMPOSE) run --rm arduino-dev bash -lc '\
		set -e; \
		cd /workspace/lab/uno/hello_lab && \
		mkdir -p build && \
		arduino-cli compile --fqbn arduino:avr:uno --output-dir build . \
	'

test-config:
	$(COMPOSE) run --rm orchestration-dev bash -lc '\
		cd /workspace && pytest -q lab/tests/test_config_schema.py \
	'

shell-pico:
	$(COMPOSE) run --rm -it pico-dev bash

shell-arduino:
	$(COMPOSE) run --rm -it arduino-dev bash

shell-orch:
	$(COMPOSE) run --rm -it orchestration-dev bash

# Privileged: needed for /dev/sd*, loop devices when flashing or patching .img files.
shell-rpi-imager:
	$(COMPOSE) run --rm --privileged -it rpi-imager-dev bash

# Render cloud-init from lab.yaml without host PyYAML (uses orchestration-dev image).
# Alternative on Dev-Host: uv sync && make pi-bootstrap-render from repo root Makefile.
pi-bootstrap-render:
	$(COMPOSE) run --rm orchestration-dev bash -lc 'python /workspace/lab/pi/bootstrap/pi_bootstrap.py render'
