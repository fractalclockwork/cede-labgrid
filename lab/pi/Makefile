# Sub-target flashing on the Raspberry Pi gateway (run SSH'd into Pi with repo checked out).
# Dev-Host stays responsible for toolchain builds (`make -C lab/docker pico-build` / `uno-build`).
#
REPO_ROOT := $(abspath ../..)

.PHONY: help subtarget-check resolve-uno-port validate-uno-serial flash-pico-uf2 flash-uno print-serial

help:
	@echo "Pi gateway sub-targets (run on Pi, repo at e.g. ~/cede):"
	@echo "  make -C lab/pi subtarget-check            — health_check + list /dev/serial/by-id"
	@echo "  make -C lab/pi print-serial               — list ttyACM/ttyUSB"
	@echo "  make -C lab/pi resolve-uno-port           — pick Uno tty (by-id / ttyUSB / non-Pico ACM)"
	@echo "  make -C lab/pi validate-uno-serial PORT=/dev/ttyACM0 — expect hello_lab serial banner"
	@echo "  make -C lab/pi flash-pico-uf2 UF2=path   — copy UF2 to BOOTSEL RPI-RP2 (optional MOUNT=)"
	@echo "  make -C lab/pi flash-uno HEX=path PORT=/dev/ttyACM0 — avrdude flash"
	@echo "See lab/pi/docs/pico-uno-subtargets.md"

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

# Pico in BOOTSEL: hold BOOTSEL, plug USB, then run (example UF2 from scp to /tmp).
flash-pico-uf2:
	@test -n "$(UF2)" || (echo "Set UF2=/path/to/file.uf2" >&2; exit 1)
	@bash "$(REPO_ROOT)/lab/pi/scripts/pi_flash_pico_uf2.sh" --uf2 "$(UF2)" \
		$(if $(MOUNT),--mount "$(MOUNT)",) --yes

flash-uno:
	@test -n "$(HEX)" || (echo "Set HEX=/path/to/file.hex" >&2; exit 1)
	@test -n "$(PORT)" || (echo "Set PORT=/dev/ttyACM0 (or correct Uno port)" >&2; exit 1)
	@bash "$(REPO_ROOT)/lab/pi/scripts/pi_flash_uno_avrdude.sh" --hex "$(HEX)" --port "$(PORT)" --yes
