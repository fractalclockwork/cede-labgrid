# Sub-target flashing on the Raspberry Pi gateway (run SSH'd into Pi).
# Expect a sparse tree synced by sync_gateway_flash_deps.sh (lab/pi/Makefile + lab/pi/scripts/* only).
# Dev-Host stays responsible for toolchain builds (`make -C lab/docker pico-build` / `uno-build`).
#
REPO_ROOT := $(abspath ../..)

.PHONY: help subtarget-check resolve-uno-port resolve-pico-port validate-uno-serial validate-pico-serial flash-pico-uf2 flash-pico-auto flash-pico flash-uno print-serial ssd1306-dual-install ssd1306-dual-run ssd1306-dual-bus-speed ssd1306-eyes-install ssd1306-eyes-run

help:
	@echo "Pi gateway sub-targets (run on Pi; sparse flash-deps root e.g. ~/cede — see sync_gateway_flash_deps.sh):"
	@echo "  make -C lab/pi subtarget-check            — health_check + list /dev/serial/by-id"
	@echo "  make -C lab/pi print-serial               — list ttyACM/ttyUSB"
	@echo "  make -C lab/pi resolve-uno-port           — pick cede-uno tty (by-id / ttyUSB / non-Pico ACM)"
	@echo "  make -C lab/pi resolve-pico-port           — pick cede-rp2 (Pico) tty"
	@echo "  make -C lab/pi validate-uno-serial PORT=/dev/ttyACM0 — expect Uno hello_lab banner"
	@echo "  make -C lab/pi validate-pico-serial PORT=… — expect cede-rp2 hello_lab banner"
	@echo "  make -C lab/pi flash-pico-auto UF2=path [PICO_BOOTSEL_ONLY=1] — picotool reboot -uf then UF2 copy (cede-rp2)"
	@echo "  make -C lab/pi flash-pico UF2=path        — same as flash-pico-auto"
	@echo "  make -C lab/pi flash-pico-uf2 UF2=path   — copy UF2 only (BOOTSEL RPI-RP2 already mounted)"
	@echo "  make -C lab/pi flash-uno HEX=path PORT=/dev/ttyACM0 — avrdude flash"
	@echo "  make -C lab/pi ssd1306-dual-install — pip install luma.oled for dual OLED demo"
	@echo "  make -C lab/pi ssd1306-dual-run — run lab/pi/ssd1306_dual/main.py (Ctrl+C stops)"
	@echo "  make -C lab/pi ssd1306-dual-bus-speed [SSD1306_SPEED_DURATION=15] — dual-panel I2C throughput benchmark"
	@echo "  make -C lab/pi ssd1306-eyes-install / ssd1306-eyes-run — dual cartoon-eye animation (lab/pi/ssd1306_eyes)"
	@echo "See lab/pi/docs/pico-uno-subtargets.md, lab/pi/ssd1306_dual/README.md, lab/pi/ssd1306_eyes/README.md"

subtarget-check:
	cd "$(REPO_ROOT)" && python3 lab/pi/scripts/health_check.py
	@ls -l /dev/serial/by-id/ 2>/dev/null || echo "(no /dev/serial/by-id entries)"

print-serial:
	@bash -lc 'shopt -s nullglob; d=(/dev/ttyACM* /dev/ttyUSB*); (($${#d[@]})) && printf "%s\n" "$${d[@]}" || echo "(no ttyACM/ttyUSB)"'

resolve-uno-port:
	@python3 "$(REPO_ROOT)/lab/pi/scripts/pi_resolve_gateway_uno.py"

validate-uno-serial:
	@test -n "$(PORT)" || (echo "Set PORT=/dev/ttyACM0 or run make resolve-uno-port then pass it" >&2; exit 1)
	@python3 "$(REPO_ROOT)/lab/pi/scripts/pi_validate_uno_serial.py" "$(PORT)"

validate-pico-serial:
	@test -n "$(PORT)" || (echo "Set PORT=… or run make resolve-pico-port" >&2; exit 1)
	@python3 "$(REPO_ROOT)/lab/pi/scripts/pi_validate_pico_serial.py" "$(PORT)"

resolve-pico-port:
	@python3 "$(REPO_ROOT)/lab/pi/scripts/pi_resolve_gateway_pico.py"

# cede-rp2: try picotool reboot -uf then copy UF2 (PICO_BOOTSEL_ONLY=1 skips picotool).
flash-pico-auto:
	@test -n "$(UF2)" || (echo "Set UF2=/path/to/hello_lab.uf2" >&2; exit 1)
	@bash "$(REPO_ROOT)/lab/pi/scripts/pi_flash_pico_auto.sh" --uf2 "$(UF2)" --yes \
		$(if $(filter 1,$(PICO_BOOTSEL_ONLY)),--bootsel-only,) \
		$(if $(PICO_WAIT_MOUNT),--wait-mount "$(PICO_WAIT_MOUNT)",)

flash-pico: flash-pico-auto

# Pico in BOOTSEL: hold BOOTSEL, plug USB, then run (example UF2 from scp to /tmp).
flash-pico-uf2:
	@test -n "$(UF2)" || (echo "Set UF2=/path/to/file.uf2" >&2; exit 1)
	@bash "$(REPO_ROOT)/lab/pi/scripts/pi_flash_pico_uf2.sh" --uf2 "$(UF2)" \
		$(if $(MOUNT),--mount "$(MOUNT)",) --yes

flash-uno:
	@test -n "$(HEX)" || (echo "Set HEX=/path/to/file.hex" >&2; exit 1)
	@test -n "$(PORT)" || (echo "Set PORT=/dev/ttyACM0 (or correct Uno port)" >&2; exit 1)
	@bash "$(REPO_ROOT)/lab/pi/scripts/pi_flash_uno_avrdude.sh" --hex "$(HEX)" --port "$(PORT)" --yes

ssd1306-dual-install:
	@test -d "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv" || python3 -m venv "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv"
	@"$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv/bin/pip" install -r "$(REPO_ROOT)/lab/pi/ssd1306_dual/requirements.txt"

ssd1306-dual-run:
	@if test -x "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv/bin/python"; then \
	  "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv/bin/python" "$(REPO_ROOT)/lab/pi/ssd1306_dual/main.py"; \
	else \
	  python3 "$(REPO_ROOT)/lab/pi/ssd1306_dual/main.py"; \
	fi

# Throughput benchmark (full-frame updates on both SSD1306). Override duration: SSD1306_SPEED_DURATION=20
SSD1306_SPEED_DURATION ?= 10
ssd1306-dual-bus-speed:
	@if test -x "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv/bin/python"; then \
	  "$(REPO_ROOT)/lab/pi/ssd1306_dual/.venv/bin/python" "$(REPO_ROOT)/lab/pi/ssd1306_dual/bus_speed_test.py" --duration "$(SSD1306_SPEED_DURATION)"; \
	else \
	  python3 "$(REPO_ROOT)/lab/pi/ssd1306_dual/bus_speed_test.py" --duration "$(SSD1306_SPEED_DURATION)"; \
	fi

ssd1306-eyes-install:
	@test -d "$(REPO_ROOT)/lab/pi/ssd1306_eyes/.venv" || python3 -m venv "$(REPO_ROOT)/lab/pi/ssd1306_eyes/.venv"
	@"$(REPO_ROOT)/lab/pi/ssd1306_eyes/.venv/bin/pip" install -r "$(REPO_ROOT)/lab/pi/ssd1306_eyes/requirements.txt"

# Optional extra CLI flags, e.g. SSD1306_EYES_EXTRA_ARGS='--contrast-left 220 --contrast-right 255'
SSD1306_EYES_EXTRA_ARGS ?=

ssd1306-eyes-run:
	@if test -x "$(REPO_ROOT)/lab/pi/ssd1306_eyes/.venv/bin/python"; then \
	  "$(REPO_ROOT)/lab/pi/ssd1306_eyes/.venv/bin/python" "$(REPO_ROOT)/lab/pi/ssd1306_eyes/main.py" $(SSD1306_EYES_EXTRA_ARGS); \
	else \
	  python3 "$(REPO_ROOT)/lab/pi/ssd1306_eyes/main.py" $(SSD1306_EYES_EXTRA_ARGS); \
	fi
