"""
modules/strike_zone.py
Defines the arm's strike zone and checks if a weed is within reach.
"""

import cv2
import numpy as np
import logging
from config import CAMERA_WIDTH, CAMERA_HEIGHT, STRIKE_ZONE, WEED_CLASS_NAMES, DEMO_MODE

logger = logging.getLogger(__name__)


def get_zone_pixels() -> tuple[int, int, int, int]:
    """
    Convert fraction-based strike zone config to pixel coordinates.
    Returns (x1, y1, x2, y2).
    """
    x1 = int(STRIKE_ZONE["x_min"] * CAMERA_WIDTH)
    y1 = int(STRIKE_ZONE["y_min"] * CAMERA_HEIGHT)
    x2 = int(STRIKE_ZONE["x_max"] * CAMERA_WIDTH)
    y2 = int(STRIKE_ZONE["y_max"] * CAMERA_HEIGHT)
    return x1, y1, x2, y2


class StrikeZone:
    """
    Manages strike zone geometry and trigger logic.

    Usage:
        zone = StrikeZone()
        in_zone, triggered = zone.check(detections)
    """

    def __init__(self):
        self.x1, self.y1, self.x2, self.y2 = get_zone_pixels()
        logger.info(
            "Strike zone set: (%d,%d) → (%d,%d) [%.0f×%.0f px]",
            self.x1, self.y1, self.x2, self.y2,
            self.x2 - self.x1, self.y2 - self.y1
        )

    def weed_in_zone(self, detections: list) -> tuple:
        """
        Check if any detection's centroid lies inside the strike zone.

        Returns:
            (in_zone: bool, triggering_detection: Detection | None)
        """
        for det in detections:
            is_weed = det.class_name in WEED_CLASS_NAMES
            if not is_weed and not DEMO_MODE:
                continue

            cx, cy = det.centroid
            if self.x1 <= cx <= self.x2 and self.y1 <= cy <= self.y2:
                logger.debug("Weed in zone: %s centroid=%s", det.class_name, det.centroid)
                return True, det
        return False, None

    def draw(self, frame: np.ndarray, active: bool = False) -> np.ndarray:
        """
        Draw the strike zone rectangle on the frame.

        Args:
            frame: BGR image
            active: If True, zone flashes red (weed detected inside)
        """
        overlay = frame.copy()

        if active:
            # Semi-transparent red fill when active
            cv2.rectangle(overlay, (self.x1, self.y1), (self.x2, self.y2),
                          (0, 0, 220), -1)
            alpha = 0.3
        else:
            # Semi-transparent green fill when idle
            cv2.rectangle(overlay, (self.x1, self.y1), (self.x2, self.y2),
                          (0, 180, 0), -1)
            alpha = 0.15

        frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

        # Border
        border_color = (0, 0, 255) if active else (0, 220, 0)
        cv2.rectangle(frame, (self.x1, self.y1), (self.x2, self.y2), border_color, 2)

        # Label
        label = "STRIKE ZONE [ACTIVE]" if active else "STRIKE ZONE"
        label_color = (0, 0, 255) if active else (0, 220, 0)
        cv2.putText(frame, label,
                    (self.x1 + 4, self.y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, label_color, 1, cv2.LINE_AA)

        return frame

    def draw_crosshair(self, frame: np.ndarray) -> np.ndarray:
        """Draw the zone centre crosshair for calibration."""
        cx = (self.x1 + self.x2) // 2
        cy = (self.y1 + self.y2) // 2
        cv2.drawMarker(frame, (cx, cy), (0, 255, 255),
                       markerType=cv2.MARKER_CROSS, markerSize=20, thickness=1)
        return frame
