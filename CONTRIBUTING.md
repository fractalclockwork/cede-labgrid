# Contributing to CEDE

Thanks for your interest in CEDE! This guide covers the basics of setting up a development environment, running tests, and submitting changes.

## Dev Environment Setup

### Prerequisites

- **Docker** (for building firmware and running toolchain containers)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager for local validation)
- **GNU Make**

### Local Setup

```bash
uv sync                    # install Python deps (main + dev groups)
make validate              # run the full offline test suite
```

For Docker toolchains:

```bash
make -C lab/docker build-images   # build pico-dev, arduino-dev, orchestration-dev
make -C lab/docker smoke          # toolchain smoke checks
```

### Lab Configuration

Copy `lab/config/lab.example.yaml` to `lab/config/lab.yaml` and fill in your machine-specific values (SSH hosts, serial device globs). The real `lab.yaml` is gitignored.

## Running Tests

| Command | Scope |
|---------|-------|
| `make validate` | Full pytest suite (offline tests) |
| `make test-config-local` | Schema validation only |
| `make pi-test-cloud-init` | Cloud-init render test |
| `make container-test-baseline` | CI-equivalent: Docker build + smoke + firmware + pytest |

### Hardware-Gated Tests

Some tests need physical hardware (Pi, Pico, Uno). These use pytest markers and environment variables:

- `@pytest.mark.hardware` -- needs attached MCUs
- `@pytest.mark.pico` / `@pytest.mark.uno` -- specific target
- `@pytest.mark.pi_gateway` -- must run on the Pi itself

Set `CEDE_RUN_HARDWARE_FULL=1`, `CEDE_RUN_HARDWARE_PICO=1`, or `CEDE_RUN_HARDWARE_UNO=1` to enable them. Without these variables, hardware tests are skipped automatically.

### LabGrid Tests

LabGrid tests use the coordinator/exporter infrastructure instead of direct SSH. They require a running coordinator and exporter (see [lab/pi/docs/labgrid-manual-flash.md](lab/pi/docs/labgrid-manual-flash.md) for setup).

| Command | Scope |
|---------|-------|
| `make lg-test-pico` | Flash + validate Pico via LabGrid |
| `make lg-test-uno` | Flash + validate Uno via LabGrid |
| `make lg-test-i2c` | I2C matrix tests via LabGrid |
| `make lg-test-all` | All LabGrid hardware tests |
| `make lg-release-all` | Release all acquired places |

These targets run from the host `.venv` using per-target env files (`env/uno.yaml`, `env/pico.yaml`) with `--lg-coordinator`. Each target auto-acquires the required place on the coordinator before running. Tests are marked with `@pytest.mark.labgrid` (registered in `lab/tests/conftest.py`). The test files are `test_pico_labgrid.py`, `test_uno_labgrid.py`, and `test_i2c_labgrid.py` under `lab/tests/`.

Override the coordinator address with `LG_COORDINATOR=host:port` (default: `192.168.1.111:20408`). To capture serial console logs for debugging, set `LG_LOG=<dir>` on any target (e.g. `make lg-test-pico LG_LOG=tmp/lg-logs`). See [lab/pi/docs/labgrid-manual-flash.md](lab/pi/docs/labgrid-manual-flash.md) for details.

#### Suppressed upstream warnings

Three upstream warnings are filtered in `pyproject.toml` `[tool.pytest.ini_options]`:

| Warning | Source | Reason |
|---------|--------|--------|
| `setDaemon()/setName() is deprecated` | pyserial 3.5 `rfc2217.py` | Uses threading APIs deprecated in Python 3.10. Fixed in pyserial main but not yet released. |
| `__del__ called before step was done` | labgrid 25.x `step.py` | `Step` objects are GC'd before `done()` when strategy transitions deactivate drivers mid-step. Harmless; the driver operation completed. |

These filters are intentional and should be revisited when pyserial >3.5 or labgrid >25.0.1 are released.

#### Always-up target philosophy

Unlike LabGrid's standard model (which assumes targets are power-cycled between tests), CEDE targets are always connected and running. The custom drivers handle this by:

- **Deactivating the serial console** before flashing (avoids port contention with the RFC2217 proxy).
- **Cooperative BOOTSEL entry** via `picotool reboot -uf` / `picotool load -f` instead of physical power cycling.
- **Two-step flash fallback** for Pi 3B's `dwc_otg` USB controller, which can't reliably re-enumerate after a Pico USB disconnect.

## Code Style

### Python

- Use `from __future__ import annotations` at the top of every module.
- Add type hints to all function signatures.
- Include a module-level docstring describing the file's purpose.
- Exit with `SystemExit` and a descriptive message, not bare exceptions.

### C / Arduino

- Keep firmware focused and well-commented at the top of each file.
- Use `cede_build_id.h` (generated) for build identity -- don't edit it by hand.

### General

- No TODO/FIXME/HACK comments in committed code -- open an issue instead.
- Makefile targets should appear in `make help` output.

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes and ensure `make validate` passes.
3. If you touched Docker images, run `make -C lab/docker smoke`.
4. Open a pull request with a clear description of what changed and why.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
