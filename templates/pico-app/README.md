# {{APP_NAME}}

Raspberry Pi Pico application.

## Prerequisites

- ARM GCC toolchain (`arm-none-eabi-gcc`)
- [Pico SDK](https://github.com/raspberrypi/pico-sdk) — set `PICO_SDK_PATH`
- CMake >= 3.13

Or use the CEDE containerized toolchain (no local install needed):
see *CEDE integration* below.

## Build

```bash
export PICO_SDK_PATH=~/pico-sdk   # adjust to your SDK location
make build
```

The output firmware is `build/{{APP_NAME}}.uf2`.

## Flash

Hold BOOTSEL on the Pico and plug it in (or run `picotool reboot -u`),
then copy the UF2:

```bash
cp build/{{APP_NAME}}.uf2 /media/$USER/RPI-RP2/
```

Or with picotool:

```bash
picotool load -f -v -x build/{{APP_NAME}}.uf2
```

## CEDE integration

If you have the CEDE environment set up, this project can use its
containerized toolchains, gateway flash, and hardware tests.

Add the CEDE overlay from the cede-labgrid repo:

```bash
# From the cede-labgrid repo:
make new-app NAME={{APP_NAME}} TARGET=pico OUTPUT=. CEDE=1
```

This adds `cede/`, `tests/`, and `cede_app.yaml`. See
[APP_DEVELOPMENT.md](https://github.com/your-org/cede-labgrid/blob/main/docs/APP_DEVELOPMENT.md)
for details.
