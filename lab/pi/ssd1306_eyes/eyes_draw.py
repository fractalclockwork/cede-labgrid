"""PIL rendering for cartoon **cat** eyes (1-bit buffer for SSD1306).

Geometry is **cat-first**: sclera almond → iris annulus → pupil morphs between **vertical slit**
(relaxed) and **dilated round** (engaged). Slit and dilated sizes are defined independently
(slender slit vs large round pupil), not derived from a single ``pr_max`` like a human model.

``pupil_focus``: **0** relaxed slit; **1** engaged — **large** round pupil (dilated), not the same
diameter as the slit. **Iris** outer diameter is fixed for a given panel (sclera geometry); only the
pupil morphs with focus — gaze moves the **whole** iris + pupil, not the iris size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageChops, ImageDraw

EyeSide = Literal["left", "right"]

# Almond tilt (degrees) applies **only to the sclera layer** (and liner on it). Iris + pupil stay
# screen-aligned so vertical slit pupils remain vertical (real cats: slit axis stays vertical).
# Pillow ``+angle`` = CCW. Right panel CCW, left CW.
CAT_SCLERA_TILT_DEGREES = 8.0

# Iris fills ~this fraction of the smaller sclera semi-axis (minus margin), wide-eyed cat.
IRIS_FRAC_OF_SCLERA_SEMI = 0.92
# Relaxed vertical slit: horizontal semi-axis ~this divisor of iris radius (very narrow).
SLIT_RX_DIVISOR = 20
# Relaxed slit vertical semi-axis as fraction of iris radius (tall).
SLIT_RY_FRAC = 0.84
# Engaged: dilated round pupil radius as fraction of **iris** radius (cat-open, much wider than slit).
PUPIL_DILATED_R_FRAC = 0.58


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


@dataclass(frozen=True)
class EyePose:
    """Cyclopean gaze + binocular extras."""

    blink_close_left: float  # 0 open .. 1 closed
    blink_close_right: float  # 0 open .. 1 closed
    gaze_x: float  # -1 .. 1 cyclopean horizontal
    gaze_y: float  # -1 .. 1 vertical (positive = look up)
    convergence: float  # 0 .. 1 inward vergence
    pupil_focus: float  # 0 relaxed slit .. 1 engaged dilated round


def render_eye(
    width: int,
    height: int,
    pose: EyePose,
    *,
    eye_side: EyeSide,
) -> Image.Image:
    cx = width // 2
    cy = height // 2
    mx = max(4, width // 14)
    y0, y1 = 0, height - 1
    sclera_box = (mx, y0, width - mx, y1)

    # Sclera + eyeliner on their own layer, then rotate — iris/pupil drawn after, not rotated.
    sclera_layer = Image.new("1", (width, height), 0)
    ds = ImageDraw.Draw(sclera_layer)
    ds.ellipse(sclera_box, outline=1, fill=1)
    _draw_cat_upper_liner(ds, sclera_box, eye_side, width, height)
    _draw_cat_outer_flick(ds, sclera_box, eye_side)

    tilt = CAT_SCLERA_TILT_DEGREES if eye_side == "right" else -CAT_SCLERA_TILT_DEGREES
    if tilt != 0:
        sclera_layer = sclera_layer.rotate(
            tilt,
            resample=Image.Resampling.NEAREST,
            expand=False,
            fillcolor=0,
        )

    img = Image.new("1", (width, height), 0)
    img = ImageChops.lighter(img, sclera_layer)
    draw = ImageDraw.Draw(img)

    sw = (width - 2 * mx) // 2
    sh = max(1, (y1 - y0 + 1) // 2)
    max_dx = sw // 4
    max_dy = sh // 4
    conv_dx = max_dx // 3

    off_x = int(pose.gaze_x * max_dx)
    off_y = -int(pose.gaze_y * max_dy)

    inward = int(pose.convergence * conv_dx)
    if eye_side == "left":
        off_x += inward
    else:
        off_x -= inward

    px = cx + off_x
    py = cy + off_y

    sclera_margin = 2
    cap_geom = max(1, min(sw, sh) - sclera_margin)

    # Iris diameter from sclera geometry only — **not** gaze-dependent (no edge clamp).
    iris_outer_r = min(
        cap_geom,
        max(4, int(min(sw, sh) * IRIS_FRAC_OF_SCLERA_SEMI + 0.5)),
    )

    # --- Pupil: two endpoint shapes (slit vs dilated circle), then morph ---
    f_raw = max(0.0, min(1.0, pose.pupil_focus))
    f = _smoothstep(f_raw)

    rx_slit = max(1, iris_outer_r // SLIT_RX_DIVISOR)
    rx_slit = min(rx_slit, max(1, iris_outer_r // 8))
    ry_slit = max(rx_slit + 2, int(iris_outer_r * SLIT_RY_FRAC + 0.5))
    ry_slit = min(ry_slit, iris_outer_r - 1)

    # Dilated round: large circle inside iris — size follows **pupil_focus** only, not gaze.
    r_dilated = max(4, int(iris_outer_r * PUPIL_DILATED_R_FRAC + 0.5))
    r_dilated = min(r_dilated, iris_outer_r - 3)

    rx = rx_slit + (r_dilated - rx_slit) * f
    ry = ry_slit + (r_dilated - ry_slit) * f

    rx = min(rx, iris_outer_r - 1)
    ry = min(ry, iris_outer_r - 1)

    _fill_iris_annulus(img, px, py, rx, ry, iris_outer_r)

    draw.ellipse(
        (px - iris_outer_r, py - iris_outer_r, px + iris_outer_r, py + iris_outer_r),
        outline=0,
        width=1,
    )

    draw.ellipse(
        (int(px - rx), int(py - ry), int(px + rx), int(py + ry)),
        outline=0,
        fill=0,
    )

    b = max(
        0.0,
        min(1.0, pose.blink_close_left if eye_side == "left" else pose.blink_close_right),
    )
    if b > 0.0:
        top_h = int(b * cy)
        bottom_h = int(b * (height - cy))
        if top_h > 0:
            draw.rectangle((0, 0, width, top_h), fill=0)
        if bottom_h > 0:
            draw.rectangle((0, height - bottom_h, width, height), fill=0)

    return img


def _fill_iris_annulus(
    img: Image.Image,
    px: int,
    py: int,
    pupil_rx: float,
    pupil_ry: float,
    iris_r: int,
) -> None:
    """Dither between circular iris outer and elliptical pupil hole."""
    if iris_r <= 1:
        return
    w, h = img.size
    pix = img.load()
    prx2 = max(pupil_rx * pupil_rx, 0.25)
    pry2 = max(pupil_ry * pupil_ry, 0.25)
    x0 = max(0, px - iris_r)
    x1 = min(w - 1, px + iris_r)
    y0 = max(0, py - iris_r)
    y1 = min(h - 1, py + iris_r)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dx = x - px
            dy = y - py
            if dx * dx + dy * dy > iris_r * iris_r:
                continue
            el = (dx * dx) / prx2 + (dy * dy) / pry2
            if el <= 1.0:
                continue
            if (x + y) % 2 == 0:
                pix[x, y] = 0


def _draw_cat_upper_liner(
    draw: ImageDraw.ImageDraw,
    sclera_box: tuple[int, int, int, int],
    eye_side: EyeSide,
    width: int,
    height: int,
) -> None:
    """Heavy upper lid / liner strokes (cartoon cat)."""
    x0, y0, x1, y1 = sclera_box
    span = x1 - x0
    n = 11
    tilt_out = -5 if eye_side == "left" else 5
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.5
        bx = int(x0 + t * span)
        arch = int(6 * (1.0 - abs(2.0 * t - 1.0)))
        y_base = y0 + 1 + arch // 3
        ya = max(0, min(height - 1, y_base))
        yb = max(0, min(height - 1, y_base - 6 - arch // 4))
        xa = max(0, min(width - 1, bx))
        xb = max(0, min(width - 1, bx + tilt_out // 2))
        draw.line((xa, ya, xb, yb), fill=0, width=1)


def _draw_cat_outer_flick(
    draw: ImageDraw.ImageDraw,
    sclera_box: tuple[int, int, int, int],
    eye_side: EyeSide,
) -> None:
    """Tiny upturn at outer corner (classic cartoon cat)."""
    x0, y0, x1, y1 = sclera_box
    if eye_side == "left":
        ox = x1 - 1
        draw.line((ox, y0 + 3, ox - 4, y0 - 2), fill=0, width=1)
    else:
        ox = x0 + 1
        draw.line((ox, y0 + 3, ox + 4, y0 - 2), fill=0, width=1)
