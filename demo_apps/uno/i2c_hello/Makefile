# i2c_hello (Uno) — I2C slave + serial banner demo.
#
#   make             — build firmware (Docker arduino-dev container)
#   make deploy      — build + flash via LabGrid
#   make flash       — flash only (skip build, use existing artifact)
#   make console     — LabGrid serial console (Ctrl+] to exit)
#   make clean       — remove build/
#
APP_DIR  := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
CEDE_HOME ?= $(abspath $(APP_DIR)/../../..)

LG_COORDINATOR ?= 192.168.1.111:20408
LG_CLIENT       = $(CEDE_HOME)/.venv/bin/labgrid-client -x $(LG_COORDINATOR)

.PHONY: help build deploy flash console clean

help:
	@echo "i2c_hello (Uno) — I2C slave @0x43 + serial banner demo"
	@echo ""
	@echo "  make             — build firmware (Docker)"
	@echo "  make deploy      — build + flash via LabGrid"
	@echo "  make flash       — flash only (existing build artifact)"
	@echo "  make console     — LabGrid serial console"
	@echo "  make clean       — remove build/"

build:
	@bash "$(CEDE_HOME)/scripts/cede-build.sh" "$(APP_DIR)"

deploy: build flash

flash:
	@bash "$(CEDE_HOME)/scripts/cede-deploy.sh" "$(APP_DIR)" --flash-only

console:
	@$(LG_CLIENT) -p cede-uno acquire 2>/dev/null || true
	$(LG_CLIENT) -p cede-uno console

clean:
	@if [ -d "$(APP_DIR)/build" ]; then \
	  docker run --rm -v "$(CEDE_HOME):/workspace" alpine rm -rf "/workspace/$(shell realpath --relative-to="$(CEDE_HOME)" "$(APP_DIR)/build")" 2>/dev/null \
	  || rm -rf "$(APP_DIR)/build"; \
	fi
