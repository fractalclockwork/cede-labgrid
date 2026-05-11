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
