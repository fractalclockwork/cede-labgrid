# Development preflight (before feature work)

Use this checklist so **toolchains**, **gateway SSH**, and **MCU discovery** are known-good before you iterate on firmware or lab automation.

## One-command gate (dev-host + gateway)

From the repository root (full checkout on the dev-host):

```bash
make cede-dev-preflight GATEWAY=pi@cede-pi.local
```

This runs:

1. **`bootstrap-stage-dev-host`** — config schema pytest (`test-config-local`), Docker **`pico-build`** + **`uno-build`**, and **`pi-gateway-build-native-hello`** (gateway native hello binary in Docker).
2. **`bootstrap-stage-gateway`** — **`pi-gateway-health`** (remote `health_check.py`) and **`pi-gateway-subtarget-check`** (remote `make -C lab/pi subtarget-check`).

Requires: **`uv`**, Docker, SSH to **`GATEWAY`** (default `pi@cede-pi.local`), and the sparse flash-deps layout documented in [lab/pi/docs/pico-uno-subtargets.md](../pi/docs/pico-uno-subtargets.md).

Override the Pi-side flash-deps root if needed (quoted so `~` expands on the gateway):

```bash
make cede-dev-preflight GATEWAY=pi@my-pi.local GATEWAY_REPO_ROOT='~/cede'
```

## Optional: dual MCU flash + serial smoke

After preflight passes, to prove **both** Pico and Uno paths end-to-end with a fresh digest (hardware on the Pi):

```bash
make pi-gateway-hello-lab-hardware-smoke GATEWAY=pi@cede-pi.local
```

See [staged-bootstrap.md](staged-bootstrap.md) for how this fits the wider bootstrap pipeline.

## Full E2E bench validation (copy-paste)

To repeat **build → health → flash both MCUs → USB serial digest check → I2C matrix** with **`hello_lab`**, use the **Copy-paste: end-to-end bench validation** section in [staged-bootstrap.md](staged-bootstrap.md). It documents **`CEDE_IMAGE_ID`**, **`GATEWAY_REPO_ROOT`**, and **`CEDE_LAB_CONFIG`** for a reproducible run.

## See also

- [staged-bootstrap.md](staged-bootstrap.md) — operator checklist and full E2E script.
- [lab/pi/docs/pico-uno-subtargets.md](../pi/docs/pico-uno-subtargets.md) — sparse sync, flash, validate, I2C matrix.
- [DESIGN.md](../../DESIGN.md) — roles (dev-host, gateway, targets).
