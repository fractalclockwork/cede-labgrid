"""Sanity checks for dirty_stats.py (pixel-diff metrics for 1-bit OLED frames).

Run from the ssd1306_eyes directory (requires pillow):
    python ssd1306_dirty_stats.py

Or via pytest (if pillow is installed):
    pytest ssd1306_dirty_stats.py -v
"""

from __future__ import annotations

from PIL import Image

from dirty_stats import (
    RollingDirtyStats,
    changed_pixel_count,
    diff_bbox,
    pixel_change_fraction,
)


def test_diff_bbox_identical() -> None:
    im = Image.new("1", (64, 32), 0)
    assert diff_bbox(im, im) is None


def test_diff_bbox_one_pixel() -> None:
    a = Image.new("1", (64, 32), 0)
    b = a.copy()
    b.putpixel((10, 5), 1)
    bbox = diff_bbox(a, b)
    assert bbox == (10, 5, 11, 6)


def test_pixel_change_fraction_and_count() -> None:
    a = Image.new("1", (10, 10), 0)
    b = Image.new("1", (10, 10), 1)
    assert changed_pixel_count(a, b) == 100
    assert abs(pixel_change_fraction(a, b) - 1.0) < 1e-9


def test_rolling_dirty_stats_mean() -> None:
    roll = RollingDirtyStats(window=3)
    roll.push_fraction(0.1)
    roll.push_fraction(0.3)
    mean = roll.mean_fraction()
    assert mean is not None and abs(mean - 0.2) < 1e-9
    roll.push_fraction(0.5)
    roll.push_fraction(0.0)
    mean = roll.mean_fraction()
    assert mean is not None and abs(mean - (0.3 + 0.5 + 0.0) / 3.0) < 1e-9


def test_diff_bbox_size_mismatch_raises() -> None:
    a = Image.new("1", (8, 8), 0)
    b = Image.new("1", (9, 9), 0)
    try:
        diff_bbox(a, b)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "size mismatch" in str(e)


if __name__ == "__main__":
    test_diff_bbox_identical()
    test_diff_bbox_one_pixel()
    test_pixel_change_fraction_and_count()
    test_rolling_dirty_stats_mean()
    test_diff_bbox_size_mismatch_raises()
    print("All dirty_stats checks passed")
