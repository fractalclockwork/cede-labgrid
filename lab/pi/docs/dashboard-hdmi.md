# HDMI dashboard (future)

For a wall-mounted or bench monitor driven by the Pi **HDMI** output:

- Run a metrics stack (e.g. Grafana, or a simple static page) reachable at `http://127.0.0.1:...` on the Pi.
- Install **`chromium`** or **`chromium-browser`** (package names differ by OS variant) and use **Openbox** or **`matchbox-window-manager`** with **autostart** to launch fullscreen Chromium to that URL on login.
- Prefer **read-only** or **kiosk** flags (`--kiosk`, `--app=URL`) and disable screen blanking (`xset s off`, `xset -dpms`).
- On **Pi 3**, keep dashboards lightweight (1 GiB RAM); offload heavy databases to another host if needed.

No automation for this ships in CEDE yet; this file records the intended direction from the architecture doc.
