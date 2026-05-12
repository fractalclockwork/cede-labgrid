# ssd1306_eyes — dual SSD1306 cartoon-eye animation.
#
# Local:   make run
# Deploy:  make deploy-run   (requires CEDE_HOME set to cede-labgrid repo)
#
EXTRA_ARGS ?=
VENV       := $(dir $(abspath $(lastword $(MAKEFILE_LIST)))).venv
APP_DIR    := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: help install run deploy deploy-run clean

help:
	@echo "ssd1306_eyes — dual SSD1306 cartoon eyes (I2C)"
	@echo ""
	@echo "  make install        — create venv + pip install requirements"
	@echo "  make run            — run main.py (Ctrl+C stops)"
	@echo "  make deploy         — sync to target (see cede_app.yaml)"
	@echo "  make deploy-run     — sync + run on target"
	@echo ""
	@echo "Requires CEDE_HOME pointing at cede-labgrid for deploy targets."

install:
	@test -d "$(VENV)" || python3 -m venv "$(VENV)"
	@"$(VENV)/bin/pip" install -q -r "$(APP_DIR)requirements.txt"

run: install
	@"$(VENV)/bin/python" "$(APP_DIR)main.py" $(EXTRA_ARGS)

deploy:
	@test -n "$(CEDE_HOME)" || { echo "error: set CEDE_HOME to your cede-labgrid checkout" >&2; exit 1; }
	@bash "$(CEDE_HOME)/scripts/cede-deploy.sh" "$(APP_DIR)" $(if $(EXTRA_ARGS),--extra-args "$(EXTRA_ARGS)",)

deploy-run:
	@test -n "$(CEDE_HOME)" || { echo "error: set CEDE_HOME to your cede-labgrid checkout" >&2; exit 1; }
	@bash "$(CEDE_HOME)/scripts/cede-deploy.sh" "$(APP_DIR)" --run $(if $(EXTRA_ARGS),--extra-args "$(EXTRA_ARGS)",)

clean:
	rm -rf "$(VENV)"
