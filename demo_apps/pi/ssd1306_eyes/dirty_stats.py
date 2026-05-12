"""Diff metrics for 1-bit PIL frames (telemetry / future partial updates)."""

from __future__ import annotations

from PIL import Image, ImageChops


def diff_bbox(prev: Image.Image, cur: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of differing pixels, or None if identical."""
    if prev.mode != "1" or cur.mode != "1":
        raise ValueError("dirty_stats expects mode '1' images")
    if prev.size != cur.size:
        raise ValueError("size mismatch")
    d = ImageChops.difference(prev, cur)
    return d.getbbox()


def changed_pixel_count(prev: Image.Image, cur: Image.Image) -> int:
    """Count of pixels that differ (same semantics as bbox area of difference mask)."""
    if prev.mode != "1" or cur.mode != "1":
        raise ValueError("dirty_stats expects mode '1' images")
    if prev.size != cur.size:
        raise ValueError("size mismatch")
    d = ImageChops.difference(prev, cur)
    bbox = d.getbbox()
    if bbox is None:
        return 0
    x0, y0, x1, y1 = bbox
    # Count set bits in cropped difference — difference for binary is XOR-ish; count nonzero
    crop = d.crop(bbox)
    hist = crop.histogram()
    # mode 1: index 0 = black, index 1 = white (changed pixels are white in diff)
    return hist[1] if len(hist) > 1 else 0


def pixel_change_fraction(prev: Image.Image, cur: Image.Image) -> float:
    """Fraction of pixels that differ, 0.0 .. 1.0."""
    w, h = prev.size
    total = float(w * h)
    if total <= 0:
        return 0.0
    return changed_pixel_count(prev, cur) / total


class RollingDirtyStats:
    """Rolling average of change fraction (optional use from main loop)."""

    def __init__(self, window: int = 60) -> None:
        self._window = max(1, window)
        self._buf: list[float] = []

    def push(self, prev: Image.Image | None, cur: Image.Image) -> float | None:
        if prev is None:
            return None
        return self.push_fraction(pixel_change_fraction(prev, cur))

    def push_fraction(self, frac: float) -> float:
        self._buf.append(frac)
        if len(self._buf) > self._window:
            self._buf.pop(0)
        return frac

    def mean_fraction(self) -> float | None:
        if not self._buf:
            return None
        return sum(self._buf) / len(self._buf)
