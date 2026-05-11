# Repository root — Python tooling via uv (https://docs.astral.sh/uv/)
REPO_ROOT := $(abspath .)
# hello_lab serial attestation: default digest from dev-host git; override with DIGEST=… (see lab/docs/staged-bootstrap.md).
# FIRMWARE_DIGEST uses = (recursive) so it tracks DIGEST when sub-makes pass a fresh DIGEST= after uno-build
# (:= would freeze a stale shell-exported DIGEST at parse time and mismatch CEDE_TEST_IMAGE_ID in smoke targets).
DIGEST ?=
CEDE_REPO_DIGEST := $(shell git -C $(REPO_ROOT) rev-parse --short=12 HEAD 2>/dev/null)
FIRMWARE_DIGEST = $(if $(strip $(DIGEST)),$(DIGEST),$(CEDE_REPO_DIGEST))

.PHONY: help sync sync-pi-gateway-flash-deps pi-gateway-sync pi-gateway-health pi-gateway-subtarget-check pi-gateway-print-serial pi-gateway-resolve-port-uno pi-gateway-resolve-port-pico pi-gateway-flash-uno pi-gateway-flash-pico pi-gateway-validate-uno pi-gateway-validate-pico pi-gateway-validate-pico-i2c pi-gateway-validate-uno-i2c pi-gateway-validate-i2c-pi-to-pico pi-gateway-validate-i2c-pi-to-uno pi-gateway-validate-i2c-from-lab pi-gateway-validate-i2c-both pi-gateway-diagnose-i2c pi-gateway-ssd1306-dual pi-gateway-ssd1306-dual-bus-speed pi-gateway-ssd1306-eyes pi-gateway-flash-test-uno pi-gateway-flash-test-pico pi-gateway-flash-test-pico-i2c pi-gateway-flash-test-uno-i2c pi-gateway-flash-test-pico-lab-stack pi-gateway-flash-test-uno-lab-stack pi-gateway-build-native-hello pi-gateway-validate-gateway-native pi-gateway-build-test-gateway-native bootstrap-stage-dev-host bootstrap-stage-gateway bootstrap-stage-zero bootstrap-stage-zero-pico bootstrap-stage-zero-uno bootstrap-stage-pico bootstrap-stage-uno bootstrap-pipeline cede-dev-preflight test-config-local validate docker-test-arch docker-workflow docker-workflow-print test-emulated-docker emulation-environments-test container-test-baseline pi-bootstrap-render pi-fetch-expand pi-raw-sd-image pi-raw-sd-image-force pi-gateway-img-patch pi-gateway-verify-boot pi-gateway-sd-ready pi-gateway-sd-ready-force export-raw-dd pi-dd-flash pi-test-cloud-init pi-verify-boot-img lg-test-pico lg-test-uno lg-test-i2c lg-test-all lg-console-pico lg-console-uno

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
	@echo "  make pi-gateway-validate-uno [PORT=…] [DIGEST=…] — Uno serial banner + digest= (default: git rev-parse --short=12 HEAD)"
	@echo "  make pi-gateway-validate-pico [PORT=…] [DIGEST=…] — Pico serial banner + digest= (same default)"
	@echo "  make pi-gateway-build-native-hello — cross-build lab/pi/native/hello_gateway (aarch64) in Docker"
	@echo "  make pi-gateway-validate-gateway-native [GATEWAY_NATIVE_BIN=…] [DIGEST=…] — scp binary, ssh run, check digest= stdout"
	@echo "  make pi-gateway-build-test-gateway-native — build + validate-gateway-native (needs GATEWAY)"
	@echo "  make pi-gateway-flash-test-uno [PORT=…] — flash then validate Uno"
	@echo "  make pi-gateway-flash-test-uno-i2c — flash Uno then serial + I2C reg0 @ UNO_I2C_ADDR (default 0x43)"
	@echo "  make pi-gateway-flash-test-pico [UF2=…] [PICO_BOOTSEL_ONLY=1] — flash then validate cede-rp2"
	@echo "  make pi-gateway-flash-test-pico-i2c — flash Pico then serial + Pi→Pico i2cget (same target)"
	@echo "  make pi-gateway-flash-test-pico-lab-stack / pi-gateway-flash-test-uno-lab-stack — lab_stack app (see lab/docs/deploy-lab-stack-app.md)"
	@echo "  I2C matrix (lab/pi/docs/bus-wiring.md; pair.validation in lab.yaml is source of truth):"
	@echo "    make pi-gateway-validate-i2c-from-lab — run all enabled rows (CEDE_LAB_CONFIG or lab/config/lab.yaml)"
	@echo "    make pi-gateway-validate-i2c-pi-to-pico — Pi i2cget @0x42 then Pico USB banner + digest (alias: pi-gateway-validate-pico-i2c)"
	@echo "    make pi-gateway-validate-i2c-pi-to-uno — Pi i2cget @0x43 then Uno USB banner + digest (alias: pi-gateway-validate-uno-i2c)"
	@echo "  make pi-gateway-validate-i2c-both — Pi i2cget 0x42 + 0x43 then Pico and Uno USB banners + digest"
	@echo "  make pi-gateway-diagnose-i2c — ssh: i2cdetect -y bus"
	@echo "  make pi-gateway-ssd1306-dual [SKIP_SYNC=1] — sync + ssh: dual SSD1306 demo on gateway (Ctrl+C stops)"
	@echo "  make pi-gateway-ssd1306-dual-bus-speed [SSD1306_SPEED_DURATION=15] — dual SSD1306 I2C throughput benchmark on gateway"
	@echo "  make pi-gateway-ssd1306-eyes [SKIP_SYNC=1] [SSD1306_EYES_EXTRA_ARGS='…'] — cartoon eyes on gateway (extra args → Pi make ssd1306-eyes-run)"
	@echo "  Staged bootstrap — see lab/docs/staged-bootstrap.md"
	@echo "  make bootstrap-stage-dev-host — workspace: config pytest + Docker pico-build + uno-build (no device flash)"
	@echo "  make bootstrap-stage-gateway — prerequisite: pi-gateway-health + subtarget-check (needs SSH)"
	@echo "  make bootstrap-stage-zero — Stage 0: flash ONE MCU + unique firmware attestation (ZERO_TARGET=pico|uno)"
	@echo "    BOOTSTRAP_ZERO_I2C=1 — after Pico flash, also i2cget reg 0 @ 0x42"
	@echo "  make bootstrap-stage-pico / bootstrap-stage-uno — alias Pico-first or full Uno flash-test"
	@echo "  make bootstrap-pipeline — workspace + gateway + Stage 0 + second MCU (ZERO_TARGET=pico: then Uno; uno: then Pico)"
	@echo "  make cede-dev-preflight — dev readiness: bootstrap-stage-dev-host + bootstrap-stage-gateway (see lab/docs/dev-preflight.md)"
	@echo "LabGrid (coordinator + exporter must be running; see env/remote.yaml):"
	@echo "  make lg-test-pico      — flash + validate Pico via LabGrid (pytest --lg-env)"
	@echo "  make lg-test-uno       — flash + validate Uno via LabGrid"
	@echo "  make lg-test-i2c       — I2C matrix validation via LabGrid"
	@echo "  make lg-test-all       — all LabGrid hardware tests (Pico + Uno + I2C)"
	@echo "  make lg-console-pico   — interactive serial console to Pico via labgrid-client"
	@echo "  make lg-console-uno    — interactive serial console to Uno via labgrid-client"
	@echo "Legacy (SSH-based, predates LabGrid):"
	@echo "  make pi-gateway-hello-lab-hardware-smoke — Docker rebuild hello_lab with unique digest per run, flash Pico+Uno, validate banners (not CI; needs GATEWAY + devices)"
	@echo "  make pi-gateway-hello-lab-hardware-smoke-uno — same digest flow for Uno only (uno-build + flash-test-uno)"
	@echo "  make pi-gateway-hello-lab-hardware-smoke-pico — same digest flow for Pico only (pico-build + flash-test-pico)"
	@echo "  make sync-pi-gateway-flash-deps / pi-gateway-sync — rsync only lab/pi Makefile + scripts (Pi has no full repo; UF2/HEX/hello_gateway come from Dev-Host scp)"
	@echo "    Uno-only: UNO_ONLY=1 make pi-gateway-sync GATEWAY=…"
	@echo "    Pi repo path: omit GATEWAY_REPO_ROOT for ~/cede on Pi; or quote — GATEWAY_REPO_ROOT='~/src/cede' (unquoted ~/… expands to dev-host home in GNU Make)"

# Push minimal Pi-gateway files for `make -C lab/pi flash-uno` / subtarget-check (see lab/pi/scripts/sync_gateway_flash_deps.sh).
# Shared cd + GATEWAY env for lab/pi/scripts/devhost_pi_gateway.sh (keep parity across pi-gateway-* targets).
DEVHOST_GATEWAY_BASE = cd "$(REPO_ROOT)" && GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)"
GATEWAY ?= pi@cede-pi.local
# Optional Uno tty when PORT names the Pico (e.g. pi-gateway-hello-lab-hardware-smoke).
UNO_PORT ?=
# Remote checkout on the Pi. Leave empty: sync uses literal ~/cede on the gateway (see sync_gateway_flash_deps.sh).
# Do not use ?= ~/… here — GNU Make expands ~ to this machine's home and breaks ssh/rsync targets.
GATEWAY_REPO_ROOT ?=
sync-pi-gateway-flash-deps:
	cd "$(REPO_ROOT)" && UNO_ONLY="$(UNO_ONLY)" bash lab/pi/scripts/sync_gateway_flash_deps.sh "$(GATEWAY)" $(if $(strip $(GATEWAY_REPO_ROOT)),"$(GATEWAY_REPO_ROOT)",)

pi-gateway-sync: sync-pi-gateway-flash-deps

# Drive checks / Uno flash from dev-host via SSH (see lab/pi/scripts/devhost_pi_gateway.sh).
pi-gateway-health:
	@$(DEVHOST_GATEWAY_BASE) bash lab/pi/scripts/devhost_pi_gateway.sh health

pi-gateway-subtarget-check:
	@$(DEVHOST_GATEWAY_BASE) bash lab/pi/scripts/devhost_pi_gateway.sh subtarget-check

pi-gateway-print-serial:
	@$(DEVHOST_GATEWAY_BASE) bash lab/pi/scripts/devhost_pi_gateway.sh print-serial

pi-gateway-resolve-port-uno:
	@$(DEVHOST_GATEWAY_BASE) bash lab/pi/scripts/devhost_pi_gateway.sh resolve-port-uno

# Default HEX path: Arduino CLI output for hello_lab; override HEX=...
HEX ?= $(REPO_ROOT)/lab/uno/hello_lab/build/hello_lab.ino.hex
UNO_VALIDATE_WAIT ?= 8
SKIP_SYNC ?=
pi-gateway-flash-uno:
	@$(DEVHOST_GATEWAY_BASE) UNO_ONLY="$(UNO_ONLY)" bash lab/pi/scripts/devhost_pi_gateway.sh flash-uno --hex "$(HEX)" $(if $(PORT),--port "$(PORT)",) $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

pi-gateway-validate-uno:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" FIRMWARE_DIGEST="$(FIRMWARE_DIGEST)" CEDE_RUN_RECORD="$(CEDE_RUN_RECORD)" CEDE_APPLICATION_ID="$(CEDE_APPLICATION_ID)" CEDE_RUN_TRANSPORT="$(CEDE_RUN_TRANSPORT)" bash lab/pi/scripts/devhost_pi_gateway.sh validate-uno-serial --wait "$(UNO_VALIDATE_WAIT)" $(if $(PORT),--port "$(PORT)",) $(if $(strip $(UNO_SERIAL_EXPECT)),--expect "$(UNO_SERIAL_EXPECT)",) $(if $(strip $(FIRMWARE_DIGEST)),--digest "$(FIRMWARE_DIGEST)",)

pi-gateway-flash-test-uno:
	@$(MAKE) pi-gateway-flash-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" CEDE_RUN_RECORD=1 $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)

pi-gateway-flash-test-uno-i2c:
	@$(MAKE) pi-gateway-flash-test-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)"
	@$(MAKE) pi-gateway-validate-uno-i2c GATEWAY="$(GATEWAY)" I2C_BUS="$(I2C_BUS)" UNO_I2C_ADDR="$(UNO_I2C_ADDR)"

pi-gateway-resolve-port-pico:
	@$(DEVHOST_GATEWAY_BASE) bash lab/pi/scripts/devhost_pi_gateway.sh resolve-port-pico

# Default UF2: Pico SDK build output for hello_lab (cede-rp2).
UF2 ?= $(REPO_ROOT)/lab/pico/hello_lab/build/hello_lab.uf2
PICO_BOOTSEL_ONLY ?=
PICO_VALIDATE_WAIT ?= 3
PICO_WAIT_MOUNT ?=
pi-gateway-flash-pico:
	@$(DEVHOST_GATEWAY_BASE) PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" bash lab/pi/scripts/devhost_pi_gateway.sh flash-pico --uf2 "$(UF2)" $(if $(filter 1,$(PICO_BOOTSEL_ONLY)),--bootsel-only,) $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

pi-gateway-validate-pico:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" FIRMWARE_DIGEST="$(FIRMWARE_DIGEST)" CEDE_RUN_RECORD="$(CEDE_RUN_RECORD)" CEDE_APPLICATION_ID="$(CEDE_APPLICATION_ID)" CEDE_RUN_TRANSPORT="$(CEDE_RUN_TRANSPORT)" bash lab/pi/scripts/devhost_pi_gateway.sh validate-pico-serial $(if $(PORT),--port "$(PORT)",) $(if $(strip $(PICO_SERIAL_EXPECT)),--expect "$(PICO_SERIAL_EXPECT)",) $(if $(strip $(FIRMWARE_DIGEST)),--digest "$(FIRMWARE_DIGEST)",)

pi-gateway-flash-test-pico:
	@$(MAKE) pi-gateway-flash-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" CEDE_RUN_RECORD=1 $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)

pi-gateway-flash-test-pico-i2c:
	@$(MAKE) pi-gateway-flash-test-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)"
	@$(MAKE) pi-gateway-validate-i2c-pi-to-pico GATEWAY="$(GATEWAY)" I2C_BUS="$(I2C_BUS)" PICO_I2C_ADDR="$(PICO_I2C_ADDR)"

# lab_stack application (lab/pico/lab_stack, lab/uno/lab_stack): build with make -C lab/docker pico-build-lab-stack uno-build-lab-stack
pi-gateway-flash-test-pico-lab-stack:
	@$(MAKE) pi-gateway-flash-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(REPO_ROOT)/lab/pico/lab_stack/build/lab_stack.uf2" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" CEDE_RUN_RECORD=1 CEDE_APPLICATION_ID=lab_stack CEDE_RUN_TRANSPORT=usb_serial PICO_SERIAL_EXPECT="CEDE lab_stack rp2 ok" $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)

pi-gateway-flash-test-uno-lab-stack:
	@$(MAKE) pi-gateway-flash-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(REPO_ROOT)/lab/uno/lab_stack/build/lab_stack.ino.hex" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)"
	@$(MAKE) pi-gateway-validate-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" PORT="$(PORT)" SKIP_SYNC=1 UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" CEDE_RUN_RECORD=1 CEDE_APPLICATION_ID=lab_stack CEDE_RUN_TRANSPORT=usb_serial UNO_SERIAL_EXPECT="CEDE lab_stack ok" $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)

# aarch64 hello_gateway for Raspberry Pi OS 64-bit (see lab/pi/native/hello_gateway; lab/docker/Makefile gateway-native-hello-build).
# Embed id must match FIRMWARE_DIGEST (git short on host by default). orchestration-dev has no git unless we pass -e CEDE_IMAGE_ID.
GATEWAY_NATIVE_BIN ?= $(REPO_ROOT)/lab/pi/native/hello_gateway/build/hello_gateway
# CEDE_IMAGE_ID overrides embed when set; else same token as DIGEST / git short (FIRMWARE_DIGEST).
GATEWAY_NATIVE_CEDE_IMAGE_ID = $(if $(strip $(CEDE_IMAGE_ID)),$(CEDE_IMAGE_ID),$(FIRMWARE_DIGEST))
pi-gateway-build-native-hello:
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" gateway-native-hello-build CEDE_IMAGE_ID="$(GATEWAY_NATIVE_CEDE_IMAGE_ID)"

pi-gateway-validate-gateway-native:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" bash lab/pi/scripts/devhost_pi_gateway.sh validate-gateway-native --binary "$(GATEWAY_NATIVE_BIN)" $(if $(strip $(FIRMWARE_DIGEST)),--digest "$(FIRMWARE_DIGEST)",)

pi-gateway-build-test-gateway-native:
	@$(MAKE) pi-gateway-build-native-hello $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)
	@$(MAKE) pi-gateway-validate-gateway-native GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC="$(SKIP_SYNC)" GATEWAY_NATIVE_BIN="$(GATEWAY_NATIVE_BIN)" $(if $(strip $(DIGEST)),DIGEST="$(DIGEST)",)

# Optional I2C smoke (hello_lab): Pico @ 0x42, Uno @ 0x43 — both may coexist on bus 1 (lab/docs/staged-bootstrap.md).
I2C_BUS ?= 1
PICO_I2C_ADDR ?= 0x42
UNO_I2C_ADDR ?= 0x43
pi-gateway-validate-pico-i2c: pi-gateway-validate-i2c-pi-to-pico
pi-gateway-validate-uno-i2c: pi-gateway-validate-i2c-pi-to-uno

pi-gateway-validate-i2c-pi-to-pico:
	cd "$(REPO_ROOT)" && ssh "$(GATEWAY)" "sudo i2cget -y $(I2C_BUS) $(PICO_I2C_ADDR) 0 b"
	@$(MAKE) pi-gateway-validate-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC=1 PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" $(if $(PORT),PORT="$(PORT)",)

pi-gateway-validate-i2c-pi-to-uno:
	cd "$(REPO_ROOT)" && ssh "$(GATEWAY)" "sudo i2cget -y $(I2C_BUS) $(UNO_I2C_ADDR) 0 b"
	@$(MAKE) pi-gateway-validate-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC=1 UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" $(if $(PORT),PORT="$(PORT)",)

# Single bring-up path: reads i2c_matrix.pairs[].validation (controller + mode) from lab config.
ONLY_I2C_PAIR ?=
pi-gateway-validate-i2c-from-lab:
	cd "$(REPO_ROOT)" && \
	GATEWAY="$(GATEWAY)" \
	GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" \
	CEDE_LAB_CONFIG="$(CEDE_LAB_CONFIG)" \
	CEDE_EXPECT_DIGEST="$(FIRMWARE_DIGEST)" \
	uv run python lab/pi/scripts/lab_i2c_matrix_validate.py \
	  --gateway "$(GATEWAY)" \
	  $(if $(strip $(GATEWAY_REPO_ROOT)),--gateway-repo "$(GATEWAY_REPO_ROOT)",) \
	  $(if $(strip $(CEDE_LAB_CONFIG)),--config "$(CEDE_LAB_CONFIG)",) \
	  $(if $(strip $(ONLY_I2C_PAIR)),--only "$(ONLY_I2C_PAIR)",) \
	  $(if $(filter 1,$(I2C_VALIDATE_DRY_RUN)),--dry-run,)

# Small gap between probes avoids some slaves missing the second START; Uno must run current hello_lab (I2C @ 0x43).
pi-gateway-validate-i2c-both:
	@cd "$(REPO_ROOT)" && ssh "$(GATEWAY)" "set -e; printf 'Pico %s reg0: ' '$(PICO_I2C_ADDR)'; sudo i2cget -y $(I2C_BUS) $(PICO_I2C_ADDR) 0 b; sleep 0.25; printf 'Uno %s reg0: ' '$(UNO_I2C_ADDR)'; sudo i2cget -y $(I2C_BUS) $(UNO_I2C_ADDR) 0 b" \
		|| { printf '%s\n' "Uno did not ACK at $(UNO_I2C_ADDR). Reflash Uno hello_lab (I2C moved from 0x42 to 0x43): make pi-gateway-flash-test-uno-i2c GATEWAY=$(GATEWAY)" >&2; exit 1; }
	@$(MAKE) pi-gateway-validate-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC=1 PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" $(if $(PORT),PORT="$(PORT)",)
	@$(MAKE) pi-gateway-validate-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" SKIP_SYNC=1 UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" $(if $(PORT),PORT="$(PORT)",)

pi-gateway-diagnose-i2c:
	cd "$(REPO_ROOT)" && ssh "$(GATEWAY)" "sudo i2cdetect -y $(I2C_BUS) 2>/dev/null || { echo 'i2cdetect failed (install i2c-tools? i2c enabled in raspi-config?)' >&2; exit 1; }"

# Dual SSD1306 on gateway I2C — sync flash deps (includes lab/pi/ssd1306_dual), then venv + run on Pi.
pi-gateway-ssd1306-dual:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" bash lab/pi/scripts/devhost_pi_gateway.sh ssd1306-dual-run $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

SSD1306_SPEED_DURATION ?= 10
pi-gateway-ssd1306-dual-bus-speed:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" SSD1306_SPEED_DURATION="$(SSD1306_SPEED_DURATION)" bash lab/pi/scripts/devhost_pi_gateway.sh ssd1306-dual-bus-speed $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

SSD1306_EYES_EXTRA_ARGS ?=
pi-gateway-ssd1306-eyes:
	@$(DEVHOST_GATEWAY_BASE) SKIP_SYNC="$(SKIP_SYNC)" SSD1306_EYES_EXTRA_ARGS="$(SSD1306_EYES_EXTRA_ARGS)" bash lab/pi/scripts/devhost_pi_gateway.sh ssd1306-eyes-run $(if $(filter 1,$(SKIP_SYNC)),--no-sync,)

# --- Staged bootstrap (lab/docs/staged-bootstrap.md) ---
# Stage 0 = first hardware gate: flash one device + unique firmware response (serial; optional I2C for Pico).
ZERO_TARGET ?= pico
BOOTSTRAP_ZERO_I2C ?=

bootstrap-stage-dev-host:
	@$(MAKE) test-config-local
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" pico-build
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" uno-build
	@$(MAKE) pi-gateway-build-native-hello

bootstrap-stage-gateway:
	@$(MAKE) pi-gateway-health GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)"
	@$(MAKE) pi-gateway-subtarget-check GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)"

# Goal-driven preflight: toolchains + gateway health + subtarget enumeration (lab/docs/dev-preflight.md).
cede-dev-preflight:
	@$(MAKE) bootstrap-stage-dev-host
	@$(MAKE) bootstrap-stage-gateway GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)"

bootstrap-stage-zero-pico:
	@$(MAKE) pi-gateway-flash-test-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)"
	@if [ "$(BOOTSTRAP_ZERO_I2C)" = "1" ]; then $(MAKE) pi-gateway-validate-pico-i2c GATEWAY="$(GATEWAY)" I2C_BUS="$(I2C_BUS)" PICO_I2C_ADDR="$(PICO_I2C_ADDR)"; fi

bootstrap-stage-zero-uno:
	@$(MAKE) pi-gateway-flash-test-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)"

bootstrap-stage-zero:
	@$(MAKE) bootstrap-stage-zero-$(ZERO_TARGET) GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" HEX="$(HEX)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" BOOTSTRAP_ZERO_I2C="$(BOOTSTRAP_ZERO_I2C)" I2C_BUS="$(I2C_BUS)"

bootstrap-stage-pico: bootstrap-stage-zero-pico

bootstrap-stage-uno:
	@$(MAKE) pi-gateway-flash-test-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)"

# Second MCU after Stage 0: if Stage 0 was Pico → Uno; if Uno → Pico.
bootstrap-pipeline:
	@$(MAKE) bootstrap-stage-dev-host
	@$(MAKE) bootstrap-stage-gateway GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)"
	@$(MAKE) bootstrap-stage-zero GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" ZERO_TARGET="$(ZERO_TARGET)" UF2="$(UF2)" HEX="$(HEX)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" BOOTSTRAP_ZERO_I2C="$(BOOTSTRAP_ZERO_I2C)" I2C_BUS="$(I2C_BUS)"
	@if [ "$(ZERO_TARGET)" = "pico" ]; then $(MAKE) bootstrap-stage-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)"; \
	elif [ "$(ZERO_TARGET)" = "uno" ]; then $(MAKE) pi-gateway-flash-test-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)"; \
	else echo "ZERO_TARGET must be pico or uno" >&2; exit 1; fi

sync:
	cd "$(REPO_ROOT)" && uv sync

test-config-local:
	cd "$(REPO_ROOT)" && uv run pytest -q lab/tests/test_config_schema.py

# Introspection for tests (lab/tests/test_firmware_digest.py): DIGEST= overrides FIRMWARE_DIGEST.
.PHONY: print-firmware-digest print-cede-repo-digest
print-firmware-digest:
	@printf '%s\n' '$(FIRMWARE_DIGEST)'

print-cede-repo-digest:
	@printf '%s\n' '$(CEDE_REPO_DIGEST)'

# Rebuild hello_lab with a unique digest, flash Pico + Uno on the gateway, validate USB banners (rejects stale images).
# Requires: Docker (lab/docker), SSH to GATEWAY, Pico + Uno on the Pi. Optional UNO_PORT when PORT names the Pico.
# Pytest: CEDE_RUN_HARDWARE_FULL=1 uv run pytest -q lab/tests/test_hello_lab_hardware_full.py
# Must use := when generating: `?=` + `$(shell …)` is recursive, so every $(CEDE_TEST_IMAGE_ID) expansion
# re-ran cede_test_image_id.py and produced a different suffix for echo vs docker vs DIGEST=.
ifeq ($(origin CEDE_TEST_IMAGE_ID),undefined)
CEDE_TEST_IMAGE_ID := $(shell python3 "$(REPO_ROOT)/lab/pi/scripts/cede_test_image_id.py")
endif
.PHONY: pi-gateway-hello-lab-hardware-smoke
pi-gateway-hello-lab-hardware-smoke:
	@echo ""
	@echo "=== hello_lab digest smoke: build (Docker) + flash + serial validate ==="
	@echo "embedded-digest (must appear on USB as digest=<this>): $(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" pico-build uno-build CEDE_IMAGE_ID="$(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) pi-gateway-flash-test-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" DIGEST="$(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) pi-gateway-flash-test-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(UNO_PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" DIGEST="$(CEDE_TEST_IMAGE_ID)"

# Same unique digest idea as pi-gateway-hello-lab-hardware-smoke, but Uno only (Docker uno-build + flash + serial digest).
# Pytest: CEDE_RUN_HARDWARE_UNO=1 uv run pytest -q lab/tests/test_hello_lab_hardware_uno_digest.py
.PHONY: pi-gateway-hello-lab-hardware-smoke-uno
pi-gateway-hello-lab-hardware-smoke-uno:
	@echo ""
	@echo "=== hello_lab Uno digest smoke: docker uno-build + avrdude flash + serial validate ==="
	@echo "embedded-digest (must appear on USB as digest=<this>): $(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" uno-build CEDE_IMAGE_ID="$(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) pi-gateway-flash-test-uno GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" HEX="$(HEX)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" UNO_VALIDATE_WAIT="$(UNO_VALIDATE_WAIT)" DIGEST="$(CEDE_TEST_IMAGE_ID)"

# Same unique digest idea as pi-gateway-hello-lab-hardware-smoke, but Pico only (Docker pico-build + flash + serial digest).
# Pytest: CEDE_RUN_HARDWARE_PICO=1 uv run pytest -q lab/tests/test_hello_lab_hardware_pico_digest.py
.PHONY: pi-gateway-hello-lab-hardware-smoke-pico
pi-gateway-hello-lab-hardware-smoke-pico:
	@echo ""
	@echo "=== hello_lab Pico digest smoke: docker pico-build + UF2 flash + serial validate ==="
	@echo "embedded-digest (must appear on USB as digest=<this>): $(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) -C "$(REPO_ROOT)/lab/docker" pico-build CEDE_IMAGE_ID="$(CEDE_TEST_IMAGE_ID)"
	@$(MAKE) pi-gateway-flash-test-pico GATEWAY="$(GATEWAY)" GATEWAY_REPO_ROOT="$(GATEWAY_REPO_ROOT)" UF2="$(UF2)" PICO_BOOTSEL_ONLY="$(PICO_BOOTSEL_ONLY)" PICO_WAIT_MOUNT="$(PICO_WAIT_MOUNT)" PORT="$(PORT)" SKIP_SYNC="$(SKIP_SYNC)" PICO_VALIDATE_WAIT="$(PICO_VALIDATE_WAIT)" DIGEST="$(CEDE_TEST_IMAGE_ID)"

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
	$(MAKE) pi-gateway-build-native-hello
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

# --- LabGrid targets (requires coordinator + exporter; see env/remote.yaml) ---
LG_ENV ?= env/remote.yaml
LG_COORDINATOR ?= localhost
LG_COMPOSE = docker compose -f lab/docker/docker-compose.yml

lg-test-pico:
	cd "$(REPO_ROOT)" && $(LG_COMPOSE) run --rm orchestration-dev \
		pytest --lg-env $(LG_ENV) -v lab/tests/test_pico_labgrid.py

lg-test-uno:
	cd "$(REPO_ROOT)" && $(LG_COMPOSE) run --rm orchestration-dev \
		pytest --lg-env $(LG_ENV) -v lab/tests/test_uno_labgrid.py

lg-test-i2c:
	cd "$(REPO_ROOT)" && $(LG_COMPOSE) run --rm orchestration-dev \
		pytest --lg-env $(LG_ENV) -v lab/tests/test_i2c_labgrid.py

lg-test-all:
	cd "$(REPO_ROOT)" && $(LG_COMPOSE) run --rm orchestration-dev \
		pytest --lg-env $(LG_ENV) -v lab/tests/test_pico_labgrid.py lab/tests/test_uno_labgrid.py lab/tests/test_i2c_labgrid.py

lg-console-pico:
	labgrid-client -x $(LG_COORDINATOR) -p cede-pico console

lg-console-uno:
	labgrid-client -x $(LG_COORDINATOR) -p cede-uno console
