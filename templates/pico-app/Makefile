PICO_BOARD ?= pico
BUILD_DIR  := build

.PHONY: build clean

build:
	@mkdir -p $(BUILD_DIR)
	cd $(BUILD_DIR) && cmake -DPICO_BOARD=$(PICO_BOARD) .. && $(MAKE)

clean:
	rm -rf $(BUILD_DIR)

# Include CEDE integration targets when present.
-include cede/Makefile.cede
