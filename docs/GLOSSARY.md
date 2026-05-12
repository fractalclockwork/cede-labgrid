# Glossary

Shared vocabulary for CEDE, LabGrid, and application development.

> **"Target"** is the most overloaded term in this project — see the
> disambiguation entry below.

---

## CEDE Core

| Term | Definition |
|------|------------|
| **CEDE** | **C**ontainerized **E**mbedded **D**evelopment **E**nvironment. Docker-based toolchains, a Raspberry Pi gateway, and LabGrid-based hardware testing for embedded firmware development. |
| **Dev-Host** | The developer's workstation (any OS/architecture). Runs Docker, builds firmware in containers, and drives the Pi gateway over SSH. Tier 0 in the three-tier architecture. |
| **Gateway** | A Raspberry Pi persistently connected to MCU targets via USB. Bridges the Dev-Host and the targets. Runs the LabGrid exporter, handles flash operations, and hosts gateway applications. Tier 1. |
| **Subtarget** | A USB-attached MCU (Pico or Uno) hanging off a gateway. The gateway can enumerate and manage multiple subtargets. |
| **Three-tier architecture** | Dev-Host → Gateway (Pi) → MCU targets (Pico, Uno). |
| **Tier** | One of three levels: Tier 0 (Dev-Host), Tier 1 (Gateway/Pi), Tier 2 (MCU targets). |

## Application Development

| Term | Definition |
|------|------------|
| **Application** | A firmware or software product that runs on a target. Identified by an `application_id`. Can span multiple targets (e.g., `i2c_hello` has Pico and Uno variants). |
| **application_id** | Unique string identifying an application (e.g., `hello_lab`, `i2c_hello`, `ssd1306_eyes`). Join key across config, manifests, and Make targets. |
| **cede_app.yaml** | Per-application manifest declaring `application_id`, target type, required lab paths, and hardware resources. Optional — only present when CEDE integration is added. |
| **Reference firmware** | `hello_lab` — the default firmware built by Docker targets. Serves as both a functional application and the validation/test baseline. |
| **Banner / Serial banner** | The startup message printed over USB serial by CEDE-aware firmware. Format: `CEDE <app_id> [<target>] ok digest=<id> (...)`. Used for automated validation. |
| **banner_prefix** | The fixed part of the banner that validation matches against, e.g., `"CEDE i2c_hello rp2 ok"`. |

## Target (disambiguation)

The word "target" means different things in different contexts:

| Context | Meaning | Example |
|---------|---------|---------|
| **CEDE architecture** | A physical device type (`pico`, `uno`, `pi`) | `lab.example.yaml` → `targets:` section |
| **LabGrid** | A named entity in a labgrid environment YAML binding resources, drivers, and a strategy | `cede-pico`, `cede-uno` in `env/remote.yaml` |
| **Makefile** | A Make rule/recipe | `pi-gateway-flash-test-pico` |
| **I2C** | The responder device on an I2C bus (replaces deprecated "slave") | Pico at 0x42, Uno at 0x43 |

## Build & Toolchain

| Term | Definition |
|------|------------|
| **Toolchain image** | Docker container with pre-configured build tools. `pico-dev` (ARM GCC, CMake, Ninja, Pico SDK, picotool), `arduino-dev` (avr-gcc, avrdude, arduino-cli), `orchestration-dev` (Python, pytest, labgrid), `rpi-imager-dev` (rpi-imager, parted). |
| **Pico SDK** | Raspberry Pi Pico C/C++ SDK. Version-pinned in Docker images. Referenced via `PICO_SDK_PATH`. |
| **PICO_SDK_PATH** | Environment variable pointing to the Pico SDK installation. Set inside `pico-dev`; must be set manually for native builds. |
| **pico_sdk_import.cmake** | Standard Pico SDK helper file that bootstraps the SDK into a CMake project. |
| **arduino-cli** | Official Arduino command-line tool for compiling and uploading sketches. |
| **FQBN** | Fully Qualified Board Name. Arduino board identifier, e.g., `arduino:avr:uno`. |
| **UF2** | USB Flashing Format. Binary firmware format for RP2040. Output of Pico SDK builds. |
| **HEX** | Intel HEX format. Firmware format for AVR/ATmega328P. Output of arduino-cli compile. |
| **Ninja** | Fast build system used as the CMake generator for Pico builds (`cmake -GNinja`). |

## Build Identity & Attestation

| Term | Definition |
|------|------------|
| **CEDE_IMAGE_ID** | Build-time identity token embedded in firmware. Defaults to `git rev-parse --short=12 HEAD`. Appears in serial banner as `digest=<value>`. |
| **cede_build_id.h** | Generated C header containing `#define CEDE_IMAGE_ID "..."`. Included by firmware source to embed the build identity. |
| **Digest / FIRMWARE_DIGEST** | A short hash (typically 12-char git SHA) identifying a specific firmware build. Used for attestation. |
| **Attestation** | Verifying that firmware running on a device matches a specific build. Done by checking the serial banner's `digest=` field against the expected value. |
| **.digest sidecar** | A text file (e.g., `hello_lab.uf2.digest`) generated alongside the firmware binary, containing the embedded CEDE_IMAGE_ID. |

## Flash & Deploy

| Term | Definition |
|------|------------|
| **picotool** | Official Raspberry Pi tool for loading firmware onto RP2040. `picotool load -f -v -x <file.uf2>`. |
| **avrdude** | AVR programming utility. Flashes HEX files to the ATmega328P. |
| **BOOTSEL** | Boot Select mode on the RP2040. The Pico appears as USB mass-storage (`RPI-RP2`) for firmware upload. Entered by holding the button during power-on or via `picotool reboot -u`. |
| **DTR** | Data Terminal Ready. RS-232 signal used to reset the Arduino Uno by toggling the ATmega16U2 USB bridge. |
| **Gateway flash** | Flashing firmware to an MCU via the Pi gateway over SSH. Dev-Host SCPs the binary to the Pi, then the Pi runs picotool or avrdude. |

## LabGrid

| Term | Definition |
|------|------------|
| **LabGrid** | Open-source embedded board farm framework for automated testing. Provides resource management, driver abstraction, and remote hardware access. |
| **Coordinator** | Central LabGrid service managing places, resources, and access control. Default: `192.168.1.111:20408`. |
| **Exporter** | LabGrid service running on a gateway that exports local hardware resources (USB serial ports) to the coordinator. Runs as a systemd user service. |
| **Place** | A named, lockable slot managed by the coordinator, representing a device that can be acquired/released. E.g., `cede-pico`, `cede-uno`. |
| **Resource** | A hardware interface exported by the exporter. Types: `USBSerialPort`, `NetworkSerialPort`, `RemotePlace`, `NetworkService`. |
| **Driver** | A LabGrid component providing functionality on top of a resource. Custom CEDE drivers: `PicotoolFlashDriver`, `AvrdudeFlashDriver`, `CedeValidationDriver`, `CedeResetDriver`, `CedeI2CDriver`. |
| **Strategy / CedeStrategy** | A `GraphStrategy` defining the device lifecycle. Three states: `off` → `flashed` → `validated`. |
| **state_off** | Root state: drivers deactivated, MCU optionally reset. |
| **state_flashed** | Firmware written to the device. |
| **state_validated** | Serial banner + digest attestation passed. Terminal success state. |
| **ManagedFile** | LabGrid utility for content-addressed file transfer from test host to exporter. |
| **ConsoleExpectMixin** | LabGrid mixin providing pexpect-style serial matching. Used by `CedeValidationDriver`. |
| **target_factory** | LabGrid's global registry for driver/strategy classes. Custom classes register via `@target_factory.reg_driver`. |
| **Environment YAML** | A YAML file defining LabGrid targets, resources, drivers, and strategies. Passed to pytest via `--lg-env`. |
| **FlashProtocol** | CEDE-defined abstract protocol with a single `flash()` method. Lets the strategy bind to any flash driver generically. |

## Hardware & Bus

| Term | Definition |
|------|------------|
| **I2C** | Inter-Integrated Circuit serial bus. Pi (controller) communicates with Pico (0x42) and Uno (0x43). |
| **I2C controller / initiator** | The device initiating I2C transactions (the Pi). Replaces deprecated term "master." |
| **I2C target / responder** | The device responding to I2C transactions (Pico, Uno). Replaces deprecated term "slave." |
| **I2C matrix** | Configuration table defining all I2C controller-target pairs, bus addresses, and validation rules. |
| **Level shifter / TXS0108E** | Bidirectional voltage translator between 3.3V (Pi, Pico) and 5V (Uno) I2C buses. |
| **Register map** | The I2C slave register layout. `reg0 = 0xCE` (magic byte), `reg1 = 0x01` (rev). |
| **Heartbeat LED** | LED blinking at ~250ms confirming firmware is running. Pin 13 (Uno) or `PICO_DEFAULT_LED_PIN` (Pico). |
| **USB CDC** | USB Communications Device Class for serial communication. Used by Pico for stdio output. |
| **ID_SERIAL_SHORT** | udev property uniquely identifying a USB serial device. Used for reliable device matching in LabGrid exporters. |

## Test & Validation

| Term | Definition |
|------|------------|
| **Smoke test** | Quick sanity check that toolchains are functional. Runs version commands inside Docker containers. |
| **Flash-test** | Combined flash + validate cycle: upload firmware, then verify serial banner and digest. |
| **Staged bootstrap** | Ordered bring-up sequence: dev-host → gateway → Stage 0 (first MCU) → Stage 1 (second MCU). |
| **Stage 0** | First hardware gate: flash one MCU and prove the specific image is running via digest attestation. |
| **Preflight / dev-preflight** | Daily readiness check: toolchain builds + gateway health + subtarget enumeration. |
| **Run record** | JSON file recording a flash-test-validate cycle (target, digest, timestamp, application_id). |

## Infrastructure

| Term | Definition |
|------|------------|
| **lab.yaml** | Machine-specific lab configuration (gitignored). Copied from `lab.example.yaml`. |
| **lab.schema.json** | JSON Schema validating `lab.yaml` structure. |
| **Cloud-init** | First-boot provisioning for the Pi gateway: hostname, SSH keys, packages, LabGrid exporter. |
| **pi_bootstrap.py** | Python CLI for gateway management: render cloud-init, fetch/expand OS images, patch boot partitions. |
| **uv** | Fast Python package manager. `uv sync` installs dependencies from `pyproject.toml` / `uv.lock`. |
| **binfmt / QEMU** | Linux feature for transparent binary format handling. Runs ARM64 Docker containers on AMD64 hosts. |
