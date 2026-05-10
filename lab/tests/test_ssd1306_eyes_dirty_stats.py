"""Tests for lab/pi/ssd1306_eyes/dirty_stats.py (no OLED hardware)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def dirty_stats(repo_root: Path):
    path = repo_root / "lab/pi/ssd1306_eyes/dirty_stats.py"
    spec = importlib.util.spec_from_file_location("ssd1306_eyes_dirty_stats", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_diff_bbox_identical(dirty_stats) -> None:
    im = Image.new("1", (64, 32), 0)
    assert dirty_stats.diff_bbox(im, im) is None


def test_diff_bbox_one_pixel(dirty_stats) -> None:
    a = Image.new("1", (64, 32), 0)
    b = a.copy()
    b.putpixel((10, 5), 1)
    bbox = dirty_stats.diff_bbox(a, b)
    assert bbox == (10, 5, 11, 6)


def test_pixel_change_fraction_and_count(dirty_stats) -> None:
    a = Image.new("1", (10, 10), 0)
    b = Image.new("1", (10, 10), 1)
    assert dirty_stats.changed_pixel_count(a, b) == 100
    assert abs(dirty_stats.pixel_change_fraction(a, b) - 1.0) < 1e-9


def test_rolling_dirty_stats_mean(dirty_stats) -> None:
    roll = dirty_stats.RollingDirtyStats(window=3)
    roll.push_fraction(0.1)
    roll.push_fraction(0.3)
    assert roll.mean_fraction() == pytest.approx(0.2)
    roll.push_fraction(0.5)
    roll.push_fraction(0.0)
    assert roll.mean_fraction() == pytest.approx((0.3 + 0.5 + 0.0) / 3.0)


def test_diff_bbox_size_mismatch_raises(dirty_stats) -> None:
    a = Image.new("1", (8, 8), 0)
    b = Image.new("1", (9, 9), 0)
    with pytest.raises(ValueError, match="size mismatch"):
        dirty_stats.diff_bbox(a, b)
