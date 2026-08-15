"""
modules/camera_module.py
Handles frame capture from USB camera or simulation source.
"""

import cv2
import os
import glob
import logging
import numpy as np
from config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
    SIMULATE, SIM_VIDEO_PATH, SIM_IMAGE_DIR
)

logger = logging.getLogger(__name__)


class CameraModule:
    """
    Abstracts over a real USB camera (OpenCV) or a simulation source.

    Usage:
        cam = CameraModule()
        cam.start()
        while True:
            ret, frame = cam.read()
            if not ret:
                break
        cam.release()
    """

    def __init__(self, simulate: bool = None):
        self.simulate = SIMULATE if simulate is None else simulate
        self._cap = None
        self._sim_images = []
        self._sim_idx = 0
        self._blank = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)

    # ──────────────────────────────────────────────
    def start(self) -> bool:
        """Open the camera or simulation source. Returns True on success."""
        if self.simulate:
            return self._start_simulation()
        return self._start_camera()

    def _start_camera(self) -> bool:
        self._cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if not self._cap.isOpened():
            logger.error("Could not open camera index %d", CAMERA_INDEX)
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        logger.info("Camera opened: %dx%d @ %d FPS", CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS)
        return True

    def _start_simulation(self) -> bool:
        # Try video file first
        if os.path.isfile(SIM_VIDEO_PATH):
            self._cap = cv2.VideoCapture(SIM_VIDEO_PATH)
            logger.info("[SIM] Using video file: %s", SIM_VIDEO_PATH)
            return self._cap.isOpened()

        # Fallback: image folder
        exts = ["*.jpg", "*.jpeg", "*.png", "*.bmp"]
        for ext in exts:
            self._sim_images.extend(glob.glob(os.path.join(SIM_IMAGE_DIR, ext)))
        self._sim_images.sort()

        if self._sim_images:
            logger.info("[SIM] Using %d images from %s", len(self._sim_images), SIM_IMAGE_DIR)
            return True

        # Final fallback: generate synthetic frames
        logger.warning("[SIM] No video/images found — using generated synthetic frames")
        return True  # Will generate frames on the fly

    # ──────────────────────────────────────────────
    def read(self):
        """
        Returns (ret: bool, frame: np.ndarray).
        Frame is always CAMERA_WIDTH × CAMERA_HEIGHT BGR.
        """
        if self._cap is not None:
            ret, frame = self._cap.read()
            if self.simulate and not ret:
                # Loop video
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
            if ret:
                frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
            return ret, frame

        if self._sim_images:
            path = self._sim_images[self._sim_idx % len(self._sim_images)]
            self._sim_idx += 1
            frame = cv2.imread(path)
            if frame is not None:
                frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
                return True, frame

        # Synthetic animated frame
        return True, self._generate_synthetic_frame()

    def _generate_synthetic_frame(self) -> np.ndarray:
        """Generate a green-tinted ground frame with random brown weed blobs."""
        frame = self._blank.copy()
        # Ground colour
        frame[:] = (30, 80, 20)   # dark green (BGR)
        # Animate a brown oval at a moving position
        t = cv2.getTickCount() / cv2.getTickFrequency()
        cx = int(CAMERA_WIDTH * (0.3 + 0.4 * abs(np.sin(t * 0.3))))
        cy = int(CAMERA_HEIGHT * (0.7 + 0.1 * np.sin(t * 0.5)))
        cv2.ellipse(frame, (cx, cy), (40, 25), 0, 0, 360, (30, 60, 100), -1)
        # Timestamp overlay
        ts = f"[SIM] t={t:.1f}s"
        cv2.putText(frame, ts, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return frame

    # ──────────────────────────────────────────────
    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("Camera released.")
