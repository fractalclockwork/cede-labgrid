# Application Development

How to create firmware applications for Pico and Uno, with or without the
CEDE environment.

See [GLOSSARY.md](GLOSSARY.md) for term definitions.

---

## 1. Standalone development

Applications build with standard toolchains and have **no CEDE dependency**.
You can develop on any machine with the right compiler installed.

### Create a new application

From the cede-labgrid repo:

```bash
# Pico application
make new-app NAME=my_sensor TARGET=pico OUTPUT=~/src/my_sensor

# Uno application
make new-app NAME=my_display TARGET=uno OUTPUT=~/src/my_display
```

Or call the script directly:

```bash
scripts/new-app.sh --name my_sensor --target pico --output ~/src/my_sensor
```

This creates a standalone project with its own git repo.

### Pico project structure

```
my_sensor/
├── CMakeLists.txt          # Standard pico-sdk CMake project
├── pico_sdk_import.cmake   # Pico SDK bootstrap helper
├── src/main.c              # Application source
├── Makefile                # build, clean
├── .gitignore
└── README.md
```

### Build (Pico)

```bash
export PICO_SDK_PATH=~/pico-sdk
make build
```

Output: `build/my_sensor.uf2`

### Flash (Pico)

Hold BOOTSEL and plug in the Pico, then:

```bash
cp build/my_sensor.uf2 /media/$USER/RPI-RP2/
```

Or with picotool:

```bash
picotool load -f -v -x build/my_sensor.uf2
```

### Uno project structure

```
my_display/
├── my_display.ino          # Arduino sketch
├── Makefile                # build, upload, clean
├── .gitignore
└── README.md
```

### Build & upload (Uno)

```bash
make build
make upload PORT=/dev/ttyUSB0
```

---

## 2. Using the CEDE environment

CEDE provides three capabilities for applications:

1. **Build** — containerized toolchains (no local install needed)
2. **Deploy** — gateway flash over SSH to real hardware
3. **Test** — LabGrid-based hardware tests with digest attestation

### Add CEDE integration to a new app

Pass `CEDE=1` when scaffolding:

```bash
make new-app NAME=my_sensor TARGET=pico OUTPUT=~/src/my_sensor CEDE=1
```

### Add CEDE integration to an existing app

Run the scaffolding script with `--cede` against the existing project
directory (the script requires the output directory not to exist, so copy
the overlay files manually):

```bash
cp -r templates/cede-overlay/cede   ~/src/my_sensor/cede
cp -r templates/cede-overlay/tests  ~/src/my_sensor/tests
cp    templates/cede-overlay/cede_app.yaml ~/src/my_sensor/

# Edit cede_app.yaml: set application_id and target
# Edit tests/test_*.py: adjust to your app
# Replace {{APP_NAME}} and {{CEDE_TARGET}} placeholders
```

### Project structure with CEDE

```
my_sensor/
├── CMakeLists.txt              # Standalone (unchanged)
├── pico_sdk_import.cmake
├── src/main.c
├── Makefile                    # -include cede/Makefile.cede
├── .gitignore
├── README.md
│
├── cede_app.yaml               # CEDE manifest
├── cede/                       # CEDE integration helpers
│   ├── Makefile.cede           # docker-build, gateway-flash, test targets
│   └── gen_build_id.sh         # Digest generation for attestation
└── tests/                      # Hardware tests
    ├── conftest.py             # LabGrid fixtures
    └── test_my_sensor.py       # Flash + validate test
```

The base `Makefile` includes `cede/Makefile.cede` via `-include`, so CEDE
targets appear automatically when the overlay is present but the project
still builds standalone when it is absent.

### Containerized build

No ARM GCC or Pico SDK install needed — uses the CEDE Docker images:

```bash
make docker-build
```

Requires Docker and the CEDE toolchain images built once from cede-labgrid:

```bash
# In cede-labgrid repo:
make -C lab/docker build-images
```

### Deploy to gateway

For Pi gateway apps (Python), set `CEDE_HOME` and deploy from the app directory:

```bash
export CEDE_HOME=~/src/cede-labgrid
cd /path/to/my_app
make deploy-run    # sync + run on target
make deploy        # sync only
```

The app's Makefile calls `$CEDE_HOME/scripts/cede-deploy.sh`, which reads
`cede_app.yaml` for the target type and gateway address. The app itself
contains no CEDE deployment logic — just `install`, `run`, and `clean`.

You can also call the script directly:

```bash
$CEDE_HOME/scripts/cede-deploy.sh /path/to/my_app --run
```

### Deploy MCU firmware via LabGrid

Flash firmware directly to hardware attached to the Pi gateway. This uses
LabGrid's `PicotoolFlashDriver` / `AvrdudeFlashDriver` with content-addressed
`ManagedFile` transfer — no raw SSH/scp needed:

```bash
# From the app directory (requires CEDE_HOME set)
export CEDE_HOME=~/src/cede-labgrid
make deploy         # flash only
make deploy-run     # flash + serial validation

# Or from the cede-labgrid repo root
make cede-deploy APP=/path/to/my_sensor
```

The `cede-deploy.sh` script reads `cede_app.yaml` to determine:
- **Pi apps**: rsync + SSH (lightweight, no LabGrid needed)
- **Pico/Uno apps**: LabGrid flash via coordinator + exporter

### Hardware tests

Run LabGrid-based tests that flash, validate serial output, and check
digest attestation:

```bash
# LabGrid tests (preferred)
make lg-test-pico    # Pico flash + validate
make lg-test-uno     # Uno flash + validate
make lg-test-i2c     # I2C bus validation
make lg-test-all     # all of the above
```

Requires the LabGrid coordinator and exporter to be running.

SSH escape hatch (when LabGrid coordinator/exporter not running):

```bash
make pi-gateway-flash-pico UF2=build/my_sensor.uf2
make pi-gateway-flash-uno HEX=build/my_display.ino.hex
```

### Digest attestation

When using CEDE, firmware can embed a build identity for test verification:

1. Run `cede/gen_build_id.sh` before building — this generates
   `cede_build_id.h` with a `CEDE_IMAGE_ID` from the git commit hash
2. Include `cede_build_id.h` in your firmware source
3. Print the digest in your serial banner: `printf("my_sensor ok digest=%s\n", CEDE_IMAGE_ID);`
4. The `CedeValidationDriver` checks that the running firmware reports
   the expected digest

### No registration needed

Applications do **not** need to be registered in `lab/config/lab.example.yaml`.
The `cede_app.yaml` manifest is the single interface between an application
and cede-labgrid — it contains everything CEDE needs to know.

---

## Reference implementations

These in-repo applications demonstrate the full CEDE integration:

- **`lab/pico/hello_lab/`** + **`lab/uno/hello_lab/`** — reference firmware
  with USB serial banner, digest attestation, I2C slave, and LED heartbeat
- **`demo_apps/pico/i2c_hello/`** + **`demo_apps/uno/i2c_hello/`** — I2C
  demo app demonstrating multi-target applications with `cede_app.yaml`
- **`demo_apps/`** — Pi gateway demo applications (each has its own
  `cede_app.yaml`, Makefile, and README)
