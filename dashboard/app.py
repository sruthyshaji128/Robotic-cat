"""
dashboard/app.py
Flask web dashboard: live MJPEG stream + stats panel.
"""

import os
import signal
import time
import logging
import threading
import cv2
import numpy as np
from flask import Flask, Response, render_template, jsonify, request

logger = logging.getLogger(__name__)


def create_app(get_frame_fn, stats_fn,
               get_control_fn=None,
               set_detection_paused_fn=None,
               set_capture_paused_fn=None,
               set_frame_delay_fn=None,
               set_weed_enabled_fn=None,
               set_pest_enabled_fn=None,
               set_rat_enabled_fn=None,
               servo_test_fn=None,
               servo_set_disengaged_fn=None,
               servo_status_fn=None):
    """
    Factory that creates the Flask app with injected frame/stats providers.

    Args:
        get_frame_fn:             callable returning the latest BGR frame or None
        stats_fn:                 callable returning a stats dict
        get_control_fn:           callable returning current control state dict
        set_detection_paused_fn:  callable(bool) to pause/resume all detection
        set_capture_paused_fn:    callable(bool) to pause/resume capture
        set_frame_delay_fn:       callable(float) to set frame delay in seconds
        set_weed_enabled_fn:      callable(bool) to enable/disable weed detection
        set_pest_enabled_fn:      callable(bool) to enable/disable pest detection
        set_rat_enabled_fn:       callable(bool) to enable/disable rat detection
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = "weed-robot-secret"

    # ── Routes ────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/video_feed")
    def video_feed():
        return Response(
            _frame_generator(get_frame_fn),
            mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    @app.route("/stats")
    def stats():
        data = stats_fn()
        uptime = int(time.time() - data.get("start_time", time.time()))
        return jsonify({
            "total_detections":      data.get("total_detections", 0),
            "total_strikes":         data.get("total_strikes", 0),
            "weeds_in_zone":         data.get("weeds_in_zone", 0),
            "uptime_seconds":        uptime,
            "uptime_formatted":      _fmt_uptime(uptime),
            "last_strike":           data.get("last_strike", "Never"),
            "simulate":              data.get("simulate", True),
            "total_pest_detections": data.get("total_pest_detections", 0),
            "last_pest_alert":       data.get("last_pest_alert", "Never"),
            "total_rat_detections":  data.get("total_rat_detections", 0),
            "last_rat_alert":        data.get("last_rat_alert", "Never"),
        })

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "ts": time.time()})

    # ── Control Routes ─────────────────────────────────────────
    @app.route("/control/status")
    def control_status():
        if get_control_fn:
            return jsonify(get_control_fn())
        return jsonify({"detection_paused": False, "capture_paused": False, "frame_delay": 0.0})

    @app.route("/control/detection", methods=["POST"])
    def control_detection():
        if set_detection_paused_fn is None:
            return jsonify({"error": "not supported"}), 501
        data = request.get_json(silent=True) or {}
        paused = bool(data.get("paused", False))
        set_detection_paused_fn(paused)
        return jsonify({"detection_paused": paused})

    @app.route("/control/capture", methods=["POST"])
    def control_capture():
        if set_capture_paused_fn is None:
            return jsonify({"error": "not supported"}), 501
        data = request.get_json(silent=True) or {}
        paused = bool(data.get("paused", False))
        set_capture_paused_fn(paused)
        return jsonify({"capture_paused": paused})

    @app.route("/control/delay", methods=["POST"])
    def control_delay():
        if set_frame_delay_fn is None:
            return jsonify({"error": "not supported"}), 501
        data = request.get_json(silent=True) or {}
        try:
            seconds = float(data.get("seconds", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid value"}), 400
        set_frame_delay_fn(seconds)
        # Return the actual stored (clamped) value, not the raw input
        actual = get_control_fn()["frame_delay"] if get_control_fn else seconds
        return jsonify({"frame_delay": actual})

    # ── Per-Detector Toggle Routes ─────────────────────────────
    def _toggle_route(name, setter_fn, key):
        """Helper that builds a generic enable/disable route."""
        if setter_fn is None:
            return jsonify({"error": "not supported"}), 501
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("enabled", True))
        setter_fn(enabled)
        return jsonify({key: enabled})

    @app.route("/control/weed", methods=["POST"])
    def control_weed():
        return _toggle_route("weed", set_weed_enabled_fn, "weed_detect_enabled")

    @app.route("/control/pest", methods=["POST"])
    def control_pest():
        return _toggle_route("pest", set_pest_enabled_fn, "pest_detect_enabled")

    @app.route("/control/rat", methods=["POST"])
    def control_rat():
        return _toggle_route("rat", set_rat_enabled_fn, "rat_detect_enabled")

    # ── Servo Routes ───────────────────────────────────────────
    @app.route("/servo/status")
    def servo_status():
        if servo_status_fn:
            return jsonify(servo_status_fn())
        return jsonify({"is_striking": False, "is_disengaged": False, "total_strikes": 0})

    @app.route("/servo/test", methods=["POST"])
    def servo_test():
        if servo_test_fn is None:
            return jsonify({"error": "not supported"}), 501
        started = servo_test_fn()
        return jsonify({"started": started})

    @app.route("/servo/disengage", methods=["POST"])
    def servo_disengage():
        if servo_set_disengaged_fn is None:
            return jsonify({"error": "not supported"}), 501
        data = request.get_json(silent=True) or {}
        disengaged = bool(data.get("disengaged", True))
        servo_set_disengaged_fn(disengaged)
        return jsonify({"disengaged": disengaged})

    # ── System restart ─────────────────────────────────────────
    @app.route("/system/restart", methods=["POST"])
    def system_restart():
        """
        Send SIGTERM to the main process.
        systemd Restart=always brings it back up automatically.
        Returns immediately so the browser gets a response before the process exits.
        """
        def _do_restart():
            time.sleep(0.4)           # let the HTTP response reach the browser first
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=_do_restart, daemon=True).start()
        return jsonify({"status": "restarting"})

    return app


# ──────────────────────────────────────────────────────────────
def _frame_generator(get_frame_fn):
    """Yield MJPEG frames for the /video_feed endpoint."""
    _placeholder = _make_placeholder()
    while True:
        frame = get_frame_fn()
        if frame is None:
            frame = _placeholder

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        jpg_bytes = buf.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n")
        time.sleep(0.033)  # ~30 FPS cap


def _make_placeholder():
    """Return a dark 'Waiting for camera...' placeholder image."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (20, 20, 30)
    cv2.putText(img, "Waiting for camera...", (140, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 180, 80), 2, cv2.LINE_AA)
    return img


def _fmt_uptime(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
