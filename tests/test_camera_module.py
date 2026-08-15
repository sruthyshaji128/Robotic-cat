"""
tests/test_camera_module.py
Unit tests for the camera module in simulation mode (no hardware needed).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
config.SIMULATE = True
config.SIM_VIDEO_PATH = "nonexistent_video.mp4"
config.SIM_IMAGE_DIR = "nonexistent_images/"
config.CAMERA_WIDTH = 640
config.CAMERA_HEIGHT = 480

import pytest
import numpy as np
from modules.camera_module import CameraModule


@pytest.fixture
def cam():
    c = CameraModule(simulate=True)
    c.start()
    yield c
    c.release()


def test_start_returns_true():
    c = CameraModule(simulate=True)
    result = c.start()
    assert result is True
    c.release()


def test_read_returns_frame(cam):
    ret, frame = cam.read()
    assert ret is True
    assert frame is not None
    assert isinstance(frame, np.ndarray)


def test_frame_is_correct_shape(cam):
    _, frame = cam.read()
    assert frame.shape == (config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3)


def test_frame_is_bgr(cam):
    _, frame = cam.read()
    assert frame.dtype == np.uint8


def test_multiple_reads_succeed(cam):
    for _ in range(10):
        ret, frame = cam.read()
        assert ret is True
        assert frame is not None


def test_release_twice_no_error(cam):
    cam.release()
    cam.release()  # Should not raise


def test_synthetic_frame_has_text():
    """Synthetic frame should have some non-zero pixels (not pure black)."""
    c = CameraModule(simulate=True)
    c.start()
    _, frame = c.read()
    c.release()
    assert frame.sum() > 0
