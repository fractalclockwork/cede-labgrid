# {{APP_NAME}}

Arduino Uno application.

## Prerequisites

- [arduino-cli](https://arduino.github.io/arduino-cli/)
- Arduino AVR core: `arduino-cli core install arduino:avr`

Or use the CEDE containerized toolchain (no local install needed):
see *CEDE integration* below.

## Build

```bash
make build
```

The output firmware is `build/{{APP_NAME}}.ino.hex`.

## Upload

```bash
make upload PORT=/dev/ttyUSB0
```

## CEDE integration

If you have the CEDE environment set up, this project can use its
containerized toolchains, gateway flash, and hardware tests.

Add the CEDE overlay from the cede-labgrid repo:

```bash
# From the cede-labgrid repo:
make new-app NAME={{APP_NAME}} TARGET=uno OUTPUT=. CEDE=1
```

This adds `cede/`, `tests/`, and `cede_app.yaml`. See
[APP_DEVELOPMENT.md](https://github.com/your-org/cede-labgrid/blob/main/docs/APP_DEVELOPMENT.md)
for details.
