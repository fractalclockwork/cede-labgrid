# `ssd1306_eyes` — dual cartoon eyes on the Pi

Python app for the **Raspberry Pi gateway**: **cartoon cat** eyes—**sclera uses the full panel height** (e.g. 64px) and is centered, horizontal almond, heavy upper liner, **large dithered iris** (~**90%** of the smaller sclera semi-axis—wide-eyed cat; iris capped by correct inscribed-circle limits, not half-sized caps), **vertical slit pupils** when relaxed, snapping to **large round** pupils when something grabs attention, then **slowly** returning to slits. **Conjugate gaze** (both eyes together), optional **vergence** for near/cross-eyed poses. **Blinks**: normal, **slow**, **double** (pair with short gap), and **winks** (left or right only)—see `EyeAnimatorConfig` in `eyes_anim.py` for timings and mix weights. Uses **PIL** double-buffering per panel and optional **dirty-fraction** telemetry (`--stats-interval`). The right panel is **not** mirrored horizontally (mirroring looked boss-eyed); mount panels so both OLEDs share the same column direction.

Same wiring as [`ssd1306_frame_test`](../ssd1306_frame_test/README.md): **bus 1**, addresses **0x3C** / **0x3D**, **3V3** logic.

> **I2C bus speed:** This application requires the fastest available I2C
> clock rate. The SSD1306 supports up to **400 kHz** (Fast-mode). Set
> `dtparam=i2c_arm_baudrate=400000` in `/boot/firmware/config.txt` on
> the Pi (default is 100 kHz). Full-frame pushes at 100 kHz limit real
> FPS to ~8; at 400 kHz the bus sustains ~30 FPS with two panels.

## Run locally

```bash
make run
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Usual options:

- **`--fps 30`** — target loop rate (sleep cap; full-frame pushes may limit real FPS).
- **`--stats-interval 60`** — every N frames print rolling mean **dirty pixel fraction** (full-frame diff vs previous image; useful for tuning future partial updates).
- **`--seed 42`** — repeatable animation timing.
- **`--contrast-left N`** / **`--contrast-right N`** — per-panel SSD1306 contrast (**0–255**, default **255**). Use when one OLED is brighter than the other: lower the brighter panel's value or raise the dimmer one until they match.

Pass extra flags via Make:

```bash
make run EXTRA_ARGS='--contrast-left 220 --contrast-right 255'
```

## Deploy via CEDE

Set `CEDE_HOME` to your cede-labgrid checkout, then deploy from the app directory:

```bash
export CEDE_HOME=~/src/cede-labgrid
make deploy-run
make deploy-run EXTRA_ARGS='--fps 20'
```

## CEDE integration

See `cede_app.yaml` in this directory for the application manifest.
