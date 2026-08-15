"""
main.py — Weed Detection & Removal Robot
Main orchestration loop: Camera → Detect → Zone Check → Strike → Dashboard

Run modes:
    python main.py                    # Use config.py defaults
    python main.py --simulate         # Force simulation mode
    python main.py --no-dashboard     # Disable web dashboard
    python main.py --duration 60      # Run for N seconds then exit (testing)
    python main.py --show-window      # Show OpenCV preview window (desktop only)
"""

import argparse
import logging
import os
import sys
import time
import signal
import threading
import cv2

# ─── Setup logging before local imports ───────────────────────
os.makedirs("logs", exist_ok=True)
# Fix Windows console encoding: use UTF-8 for file, errors='replace' for console
_file_handler = logging.FileHandler("logs/robot.log", encoding="utf-8")
_stream_handler = logging.StreamHandler(sys.stdout)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        _file_handler,
        _stream_handler,
    ]
)
logger = logging.getLogger("main")

# ─── Parse CLI args (before importing config so flags can override) ───
parser = argparse.ArgumentParser(description="Weed Detection & Removal Robot")
parser.add_argument("--simulate", action="store_true", help="Force simulation mode")
parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
parser.add_argument("--duration", type=float, default=0,
                    help="Run for N seconds then exit (0 = run forever)")
parser.add_argument("--show-window", action="store_true",
                    help="Show OpenCV preview window (requires desktop)")
args = parser.parse_args()

# Apply CLI overrides to config before importing modules
import config
if args.simulate:
    config.SIMULATE = True
if args.no_dashboard:
    config.DASHBOARD_ENABLED = False

# ─── Local imports ─────────────────────────────────────────────
from modules import CameraModule, WeedDetector, StrikeZone, ArmController, PestDetector, RatDetector, ServoController

# Shared frame for dashboard streaming
_latest_frame = None
_latest_frame_lock = threading.Lock()
_stats = {
    "total_detections": 0,
    "total_strikes": 0,
    "weeds_in_zone": 0,
    "start_time": time.time(),
    "last_strike": "Never",
    "simulate": config.SIMULATE,
    "total_pest_detections": 0,
    "last_pest_alert": "Never",
    "total_rat_detections": 0,
    "last_rat_alert": "Never",
    "servo_strikes": 0,
}
_running = True

# ── Detection / Capture Control ─────────────────────────────────
_detection_paused      = False
_capture_paused        = False
_frame_delay           = 0.0   # seconds between processed detection frames (0 = every frame)
_last_detect_time      = 0.0
_weed_detect_enabled   = True  # runtime toggle for weed detection
_pest_detect_enabled   = True  # runtime toggle for pest detection
_rat_detect_enabled    = True  # runtime toggle for rat detection
_control_lock          = threading.Lock()


def get_latest_frame():
    with _latest_frame_lock:
        return _latest_frame


def set_latest_frame(frame):
    global _latest_frame
    with _latest_frame_lock:
        _latest_frame = frame.copy() if frame is not None else None


def get_control_state():
    with _control_lock:
        return {
            "detection_paused":    _detection_paused,
            "capture_paused":      _capture_paused,
            "frame_delay":         _frame_delay,
            "weed_detect_enabled": _weed_detect_enabled,
            "pest_detect_enabled": _pest_detect_enabled,
            "rat_detect_enabled":  _rat_detect_enabled,
        }


def set_detection_paused(val: bool):
    global _detection_paused
    with _control_lock:
        _detection_paused = bool(val)
    logger.info("Detection %s", "PAUSED" if val else "RESUMED")


def set_capture_paused(val: bool):
    global _capture_paused
    with _control_lock:
        _capture_paused = bool(val)
    logger.info("Video capture %s", "PAUSED" if val else "RESUMED")


def set_frame_delay(seconds: float):
    global _frame_delay
    seconds = max(0.0, min(float(seconds), 30.0))
    with _control_lock:
        _frame_delay = seconds
    logger.info("Frame delay set to %.2fs", seconds)


def set_weed_detect_enabled(val: bool):
    global _weed_detect_enabled
    with _control_lock:
        _weed_detect_enabled = bool(val)
    logger.info("Weed detection %s", "ENABLED" if val else "DISABLED")


def set_pest_detect_enabled(val: bool):
    global _pest_detect_enabled
    with _control_lock:
        _pest_detect_enabled = bool(val)
    logger.info("Pest detection %s", "ENABLED" if val else "DISABLED")


def set_rat_detect_enabled(val: bool):
    global _rat_detect_enabled
    with _control_lock:
        _rat_detect_enabled = bool(val)
    logger.info("Rat detection %s", "ENABLED" if val else "DISABLED")


# ── Servo control (set by dashboard routes) ─────────────────────
_servo_instance = None   # set once ServoController is initialised in detection_loop


def servo_test():
    """Trigger a manual test strike from the dashboard."""
    if _servo_instance is not None:
        return _servo_instance.test_strike()
    return False


def servo_set_disengaged(val: bool):
    if _servo_instance is not None:
        if val:
            _servo_instance.disengage()
        else:
            _servo_instance.engage()


def servo_get_status():
    if _servo_instance is not None:
        return {
            "is_striking":   _servo_instance.is_striking(),
            "is_disengaged": _servo_instance.is_disengaged(),
            "total_strikes": _servo_instance.total_strikes,
        }
    return {"is_striking": False, "is_disengaged": False, "total_strikes": 0}


# ──────────────────────────────────────────────────────────────
def detection_loop():
    """Main camera-detect-strike loop. Runs in its own thread."""
    global _running, _stats, _servo_instance

    cam = CameraModule()
    detector = WeedDetector()
    zone = StrikeZone()
    arm = ArmController()
    pest_detector = PestDetector() if config.PEST_DETECTION_ENABLED else None
    rat_detector = RatDetector() if config.RAT_DETECTION_ENABLED else None

    # Servo controller
    servo = None
    if getattr(config, "SERVO_ENABLED", False):
        servo = ServoController()
        if servo.setup():
            _servo_instance = servo
            logger.info("[SERVO] Servo controller ready on pin %d.", config.SERVO_PIN)
        else:
            logger.warning("[SERVO] Servo setup failed — servo disabled.")

    logger.info("Initialising camera...")
    if not cam.start():
        logger.critical("Camera failed to start. Exiting.")
        _running = False
        return

    logger.info("Loading weed detection model...")
    if not detector.load():
        logger.critical("Detector failed to load. Exiting.")
        _running = False
        cam.release()
        return

    if pest_detector is not None:
        logger.info("Loading pest detection model...")
        if not pest_detector.load():
            logger.warning("Pest detector failed to load — pest detection disabled.")
            pest_detector = None

    if rat_detector is not None:
        logger.info("Loading rat detection model...")
        if not rat_detector.load():
            logger.warning("Rat detector failed to load — rat detection disabled.")
            rat_detector = None

    logger.info("Setting up arm controller...")
    if not arm.setup():
        logger.warning("Arm setup failed — continuing in log-only mode.")

    logger.info("=" * 55)
    logger.info("  WEED ROBOT STARTED  |  Simulate=%s  |  Dashboard=%s",
                config.SIMULATE, config.DASHBOARD_ENABLED)
    logger.info("=" * 55)

    start_time = time.time()

    global _last_detect_time

    try:
        while _running:
            # ── Stop after duration if set ──────────────────────
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                logger.info("Duration %.0fs elapsed — stopping.", args.duration)
                break

            ret, frame = cam.read()
            if not ret:
                logger.warning("Camera read failed — retrying...")
                time.sleep(0.1)
                continue

            # ── Read current control state once per iteration ────
            with _control_lock:
                det_paused        = _detection_paused
                cap_paused        = _capture_paused
                frame_delay       = _frame_delay
                weed_enabled      = _weed_detect_enabled
                pest_enabled      = _pest_detect_enabled
                rat_enabled       = _rat_detect_enabled

            # ── Frame-delay throttle ─────────────────────────────
            now = time.time()
            if frame_delay > 0 and (now - _last_detect_time) < frame_delay:
                # Still publish the raw frame so the stream stays alive
                if not cap_paused:
                    set_latest_frame(frame)
                time.sleep(0.033)
                continue
            _last_detect_time = now

            if det_paused:
                # Detection suspended — just show the raw camera frame
                if not cap_paused:
                    overlay = frame.copy()
                    cv2.putText(overlay, "DETECTION PAUSED", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2, cv2.LINE_AA)
                    set_latest_frame(overlay)
                time.sleep(0.033)
                continue

            # ── Weed Detection ───────────────────────────────────
            detections = detector.detect(frame) if weed_enabled else []
            if detections:
                _stats["total_detections"] += len(detections)

            # ── Zone Check ───────────────────────────────────────
            in_zone, triggered_det = zone.weed_in_zone(detections)

            if in_zone:
                _stats["weeds_in_zone"] += 1
                fired = arm.strike()
                if fired:
                    _stats["total_strikes"] += 1
                    _stats["last_strike"] = time.strftime("%H:%M:%S")
                    logger.info("[STRIKE] Strike fired! Weed: %s at %s",
                                triggered_det.class_name, triggered_det.centroid)
                # ── Servo strike ─────────────────────────────────
                if servo is not None:
                    servo_fired = servo.strike()
                    if servo_fired:
                        _stats["servo_strikes"] += 1

            # ── Pest Detection ───────────────────────────────────
            pest_detections = []
            if pest_detector is not None and pest_enabled:
                pest_detections = pest_detector.detect(frame)
                if pest_detections:
                    _stats["total_pest_detections"] += len(pest_detections)
                    _stats["last_pest_alert"] = time.strftime("%H:%M:%S")
                    for pd in pest_detections:
                        logger.info("[PEST] Detected: %s (%.0f%%) at %s",
                                    pd.class_name, pd.confidence * 100, pd.centroid)

            # ── Rat Detection ────────────────────────────────────
            rat_detections = []
            if rat_detector is not None and rat_enabled:
                rat_detections = rat_detector.detect(frame)
                if rat_detections:
                    _stats["total_rat_detections"] += len(rat_detections)
                    _stats["last_rat_alert"] = time.strftime("%H:%M:%S")
                    for rd in rat_detections:
                        logger.info("[RAT] Detected: %s (%.0f%%) at %s",
                                    rd.class_name, rd.confidence * 100, rd.centroid)

            # ── Annotate Frame ───────────────────────────────────
            frame = detector.annotate_frame(frame, detections)
            if pest_detector is not None:
                frame = pest_detector.annotate_frame(frame, pest_detections)
            if rat_detector is not None:
                frame = rat_detector.annotate_frame(frame, rat_detections)
            frame = zone.draw(frame, active=in_zone)
            frame = zone.draw_crosshair(frame)
            frame = _draw_hud(frame, arm, servo)

            # ── STRIKING overlay ─────────────────────────────────
            if servo is not None and servo.is_striking():
                frame = _draw_striking_overlay(frame)

            # ── Publish frame (skip if capture paused) ───────────
            if not cap_paused:
                set_latest_frame(frame)

            # ── Optional window preview ──────────────────────────
            if args.show_window:
                cv2.imshow("Weed Robot", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        cam.release()
        arm.cleanup()
        if servo is not None:
            servo.cleanup()
        if args.show_window:
            cv2.destroyAllWindows()
        logger.info("Detection loop stopped.")
        _running = False


def _draw_striking_overlay(frame):
    """Draw big flashing red STRIKING text over the frame."""
    h, w = frame.shape[:2]
    # Flash: visible every other half-second
    if int(time.time() * 2) % 2 == 0:
        text = "STRIKING"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = min(w, h) / 200.0       # scale relative to frame size
        thickness = max(3, int(scale * 4))
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (w - tw) // 2
        y = (h + th) // 2
        # Dark shadow for readability
        cv2.putText(frame, text, (x + 3, y + 3), font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        # Bright red text
        cv2.putText(frame, text, (x, y), font, scale, (0, 0, 255), thickness, cv2.LINE_AA)
    return frame


def _draw_hud(frame, arm: ArmController, servo=None):
    """Overlay HUD stats on the annotated frame."""
    h, w = frame.shape[:2]
    uptime = int(time.time() - _stats["start_time"])
    mode_tag = "[SIM]" if config.SIMULATE else "[LIVE]"

    lines = [
        f"{mode_tag} Uptime: {uptime}s",
        f"Weeds: {_stats['total_detections']}",
        f"Strikes: {_stats['total_strikes']}",
        f"Last Strike: {_stats['last_strike']}",
        f"Pests: {_stats['total_pest_detections']}",
        f"Rats:  {_stats['total_rat_detections']}",
    ]
    if arm.is_striking():
        lines.append("ARM: STRIKING!")
    elif arm.cooldown_remaining() > 0:
        lines.append(f"ARM: cooldown {arm.cooldown_remaining():.1f}s")
    else:
        lines.append("ARM: READY")

    if servo is not None:
        if servo.is_disengaged():
            lines.append("SERVO: DISENGAGED")
        elif servo.is_striking():
            lines.append("SERVO: STRIKING!")
        else:
            lines.append(f"SERVO: READY (#{servo.total_strikes})")

    # Dark panel top-left
    panel_h = len(lines) * 20 + 10
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (230, panel_h), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for i, line in enumerate(lines):
        color = (0, 255, 128) if "STRIKING" in line else (200, 255, 200)
        cv2.putText(frame, line, (8, 18 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.47, color, 1, cv2.LINE_AA)
    return frame


# ──────────────────────────────────────────────────────────────
def start_dashboard():
    """Start the Flask dashboard in a daemon thread."""
    from dashboard.app import create_app
    app = create_app(
        get_frame_fn=get_latest_frame,
        stats_fn=lambda: _stats,
        get_control_fn=get_control_state,
        set_detection_paused_fn=set_detection_paused,
        set_capture_paused_fn=set_capture_paused,
        set_frame_delay_fn=set_frame_delay,
        set_weed_enabled_fn=set_weed_detect_enabled,
        set_pest_enabled_fn=set_pest_detect_enabled,
        set_rat_enabled_fn=set_rat_detect_enabled,
        servo_test_fn=servo_test,
        servo_set_disengaged_fn=servo_set_disengaged,
        servo_status_fn=servo_get_status,
    )
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT,
            debug=False, use_reloader=False, threaded=True)


# ──────────────────────────────────────────────────────────────
def main():
    global _running

    def _sig_handler(sig, frame):
        global _running
        logger.info("Shutdown signal received.")
        _running = False
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    # Start dashboard in background thread
    if config.DASHBOARD_ENABLED:
        dash_thread = threading.Thread(target=start_dashboard, daemon=True)
        dash_thread.start()
        logger.info("Dashboard starting at http://%s:%d",
                    config.DASHBOARD_HOST, config.DASHBOARD_PORT)

    # Run detection loop (blocks until done)
    detection_loop()


if __name__ == "__main__":
    main()
