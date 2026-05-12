FQBN      ?= arduino:avr:uno
PORT      ?= /dev/ttyUSB0
BUILD_DIR := build

.PHONY: build upload clean

build:
	arduino-cli compile --fqbn $(FQBN) --output-dir $(BUILD_DIR) .

upload: build
	arduino-cli upload --fqbn $(FQBN) --port $(PORT) .

clean:
	rm -rf $(BUILD_DIR)

# Include CEDE integration targets when present.
-include cede/Makefile.cede
