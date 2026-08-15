"""
tests/test_strike_zone.py
Unit tests for strike zone geometry and trigger logic.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np

# Override config before importing modules
import config
config.CAMERA_WIDTH = 640
config.CAMERA_HEIGHT = 480
config.STRIKE_ZONE = {"x_min": 0.35, "x_max": 0.65, "y_min": 0.60, "y_max": 0.95}
config.SIMULATE = True

from modules.strike_zone import StrikeZone, get_zone_pixels
from modules.weed_detector import Detection


# ─── Fixtures ─────────────────────────────────────────────────
@pytest.fixture
def zone():
    return StrikeZone()


def make_det(cx, cy, w=60, h=40):
    """Helper to create a Detection with a known centroid."""
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = cx + w // 2, cy + h // 2
    return Detection(bbox=(x1, y1, x2, y2), confidence=0.9, class_name="weed")


# ─── Zone pixel calculation ────────────────────────────────────
def test_zone_pixel_coords():
    x1, y1, x2, y2 = get_zone_pixels()
    assert x1 == int(0.35 * 640)  # 224
    assert y1 == int(0.60 * 480)  # 288
    assert x2 == int(0.65 * 640)  # 416
    assert y2 == int(0.95 * 480)  # 456


# ─── Weed-in-zone detection ────────────────────────────────────
def test_centroid_inside_zone(zone):
    # Centroid at exact centre of frame (should be inside default zone)
    det = make_det(cx=320, cy=360)
    in_zone, triggered = zone.weed_in_zone([det])
    assert in_zone is True
    assert triggered is det


def test_centroid_outside_zone_top(zone):
    det = make_det(cx=320, cy=50)   # Top of frame, above zone
    in_zone, triggered = zone.weed_in_zone([det])
    assert in_zone is False
    assert triggered is None


def test_centroid_outside_zone_left(zone):
    det = make_det(cx=50, cy=360)   # Far left, outside zone
    in_zone, triggered = zone.weed_in_zone([det])
    assert in_zone is False


def test_centroid_outside_zone_right(zone):
    det = make_det(cx=600, cy=360)  # Far right
    in_zone, triggered = zone.weed_in_zone([det])
    assert in_zone is False


def test_centroid_on_border(zone):
    # Exactly on zone boundary — should be inside (inclusive check)
    x1, y1, x2, y2 = get_zone_pixels()
    det = make_det(cx=x1, cy=y1)
    in_zone, _ = zone.weed_in_zone([det])
    assert in_zone is True


def test_empty_detections(zone):
    in_zone, triggered = zone.weed_in_zone([])
    assert in_zone is False
    assert triggered is None


def test_multiple_detections_first_match_wins(zone):
    det_out = make_det(cx=50, cy=50)    # Outside
    det_in  = make_det(cx=320, cy=360)  # Inside
    in_zone, triggered = zone.weed_in_zone([det_out, det_in])
    assert in_zone is True
    assert triggered is det_in


# ─── Frame annotation ─────────────────────────────────────────
def test_draw_returns_same_shape(zone):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = zone.draw(frame, active=False)
    assert result.shape == frame.shape


def test_draw_active_returns_same_shape(zone):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = zone.draw(frame, active=True)
    assert result.shape == frame.shape
