# `ssd1306_eyes` — dual cartoon eyes on the Pi

Python app for the **Raspberry Pi gateway**: **cartoon cat** eyes—**sclera uses the full panel height** (e.g. 64px) and is centered, horizontal almond, heavy upper liner, **large dithered iris** (~**90%** of the smaller sclera semi-axis—wide-eyed cat; iris capped by correct inscribed-circle limits, not half-sized caps), **vertical slit pupils** when relaxed, snapping to **large round** pupils when something grabs attention, then **slowly** returning to slits. **Conjugate gaze** (both eyes together), optional **vergence** for near/cross-eyed poses. **Blinks**: normal, **slow**, **double** (pair with short gap), and **winks** (left or right only)—see `EyeAnimatorConfig` in `eyes_anim.py` for timings and mix weights. Uses **PIL** double-buffering per panel and optional **dirty-fraction** telemetry (`--stats-interval`). The right panel is **not** mirrored horizontally (mirroring looked boss-eyed); mount panels so both OLEDs share the same column direction.

Same wiring as [`ssd1306_dual`](../ssd1306_dual/README.md): **bus 1**, addresses **0x3C** / **0x3D**, **3V3** logic.

## Run on the gateway

```bash
cd ~/cede/lab/pi/ssd1306_eyes
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Usual options:

- **`--fps 30`** — target loop rate (sleep cap; full-frame pushes may limit real FPS).
- **`--stats-interval 60`** — every N frames print rolling mean **dirty pixel fraction** (full-frame diff vs previous image; useful for tuning future partial updates).
- **`--seed 42`** — repeatable animation timing.
- **`--contrast-left N`** / **`--contrast-right N`** — per-panel SSD1306 contrast (**0–255**, default **255**). Use when one OLED is brighter than the other: lower the brighter panel’s value or raise the dimmer one until they match.

From `lab/pi` via Make (extra flags forwarded):

```bash
make ssd1306-eyes-run SSD1306_EYES_EXTRA_ARGS='--contrast-left 220 --contrast-right 255'
```

## Dev-host

From repo root:

```bash
make pi-gateway-ssd1306-eyes GATEWAY=pi@cede-pi.local
```

That target **syncs** the sparse Pi tree (including these Python files), runs **`make -C lab/pi ssd1306-eyes-install`**, then **`ssd1306-eyes-run`** on the gateway.

Optional **`SSD1306_EYES_EXTRA_ARGS`** is forwarded to the Pi (same as running `make ssd1306-eyes-run` locally there):

```bash
make pi-gateway-ssd1306-eyes GATEWAY=pi@cede-pi.local \
  SSD1306_EYES_EXTRA_ARGS='--contrast-left 220 --contrast-right 255'
```

### Sync only (push scripts, no run)

On your **development machine**, from the repo root:

```bash
make pi-gateway-sync GATEWAY=pi@cede-pi.local
```

Same thing under the hood:

```bash
bash lab/pi/scripts/sync_gateway_flash_deps.sh pi@cede-pi.local
```

Optional second argument if the Pi checkout is not **`~/cede`**:

```bash
bash lab/pi/scripts/sync_gateway_flash_deps.sh pi@cede-pi.local ~/src/cede
```

Then on the Pi: `cd ~/cede/lab/pi` and `make ssd1306-eyes-install` / `make ssd1306-eyes-run` (or run `main.py` under `ssd1306_eyes/.venv` as above).

To **skip** sync when using `make pi-gateway-ssd1306-eyes`, set **`SKIP_SYNC=1`** (only if the Pi already has current files).

## Lab configuration

Path keys **`ssd1306_eyes_pi_app`** / **`ssd1306_eyes_pi_main_glob`** in `lab/config/lab.example.yaml`, **`applications.ssd1306_eyes.targets.pi`**.
