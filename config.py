"""
config.py — Central configuration for the Weed Detection & Removal Robot.
Edit this file to tune camera, model, strike zone, and arm settings.
"""

import os

# ──────────────────────────────────────────────────────────────
# SIMULATION FLAG
# Set to True for PC/VM testing (no physical hardware required)
# Set to False on Raspberry Pi with hardware connected
# ──────────────────────────────────────────────────────────────
SIMULATE = False  # Set to True for PC testing; False on Raspberry Pi with USB camera

# ──────────────────────────────────────────────────────────────
# CAMERA SETTINGS
# ──────────────────────────────────────────────────────────────
CAMERA_INDEX = 0            # USB camera index (try 1 or higher if 0 fails)
CAMERA_WIDTH = 640          # Frame width in pixels
CAMERA_HEIGHT = 480         # Frame height in pixels
CAMERA_FPS = 30             # Target FPS

# Path to a video file or image folder for simulation mode
SIM_VIDEO_PATH = "assets/sim_video.mp4"      # Use a video file for simulation
SIM_IMAGE_DIR = "assets/sim_images/"         # Fallback: folder of test images

# ──────────────────────────────────────────────────────────────
# DETECTION MODEL
# ──────────────────────────────────────────────────────────────
MODEL_PATH = "models/yolov8n_weed.onnx"      # YOLOv8n Nano weights
DETECTION_CONFIDENCE = 0.45                  # Minimum confidence threshold (0-1)
WEED_CLASS_NAMES = ["weed", "Weed", "weed_plant"]  # Class names to treat as weeds
# If model is a general COCO model, any detection triggers for demo/simulation
DEMO_MODE = False # In demo mode, any detected object counts as "weed"

# ──────────────────────────────────────────────────────────────
# PEST DETECTION MODEL
# ──────────────────────────────────────────────────────────────
PEST_DETECTION_ENABLED = True
PEST_MODEL_PATH = "yolov8n.onnx"               # YOLOv8n ONNX (shared with weed detector)
PEST_DETECTION_CONFIDENCE = 0.45               # Minimum confidence threshold (0-1)
# Class names the pest model outputs (index order must match model training).
# When using the generic YOLOv8n COCO model, set PEST_DEMO_MODE=True so that
# any detection triggers a pest alert.  Replace with a trained pest model
# (and set PEST_DEMO_MODE=False) for production use.
PEST_CLASS_NAMES = ["aphid", "whitefly", "caterpillar", "beetle", "mite", "thrips", "pest", "bird"]
# Demo mode: treat every COCO detection as a pest (required for generic YOLOv8n)
PEST_DEMO_MODE = True

# ──────────────────────────────────────────────────────────────
# RAT / RODENT DETECTION
# ──────────────────────────────────────────────────────────────
RAT_DETECTION_ENABLED = True
# Path to a custom rat-trained YOLOv8 ONNX model.
# Set RAT_DEMO_MODE=False and point this at your model for production.
# Example: "models/rat_yolov8n.onnx"
RAT_MODEL_PATH = "yolov8n.onnx"
RAT_DETECTION_CONFIDENCE = 0.40
# Class names your custom rat model outputs (must match training labels).
RAT_CLASS_NAMES = ["rat", "mouse", "rodent"]
# Demo mode: uses generic YOLOv8n COCO model; triggers on bird/cat/dog as
# stand-in proxies so the pipeline can be tested without a custom model.
# Set to False when using a real rat-trained model.
RAT_DEMO_MODE = True

# ──────────────────────────────────────────────────────────────
# SERVO MOTOR
# ──────────────────────────────────────────────────────────────
SERVO_ENABLED        = True   # Set False to disable servo entirely
SERVO_PIN            = 18     # BCM GPIO pin for servo PWM signal (hardware PWM)
SERVO_FREQUENCY      = 50     # Hz — standard for hobby servos
SERVO_DUTY_0DEG      = 2.5    # Duty cycle (%) for 0° rest position
SERVO_DUTY_90DEG     = 7.5    # Duty cycle (%) for 90° strike position
SERVO_HOLD_DURATION  = 2.0    # Seconds to hold at 90° before returning to 0°
SERVO_MOVE_DELAY     = 0.3    # Seconds to allow servo to reach position before next command

# ──────────────────────────────────────────────────────────────
# STRIKE ZONE  (as fraction of frame dimensions, 0.0–1.0)
# The zone is a rectangle in the frame where the arm can reach.
# X: left → right (fraction of width)
# Y: top → bottom (fraction of height)
# ──────────────────────────────────────────────────────────────
STRIKE_ZONE = {
    "x_min": 0.35,   # 35% from left
    "x_max": 0.65,   # 65% from left  (30% wide band in centre)
    "y_min": 0.60,   # 60% from top
    "y_max": 0.95,   # 95% from top   (lower 35% of frame = near-ground)
}

# ──────────────────────────────────────────────────────────────
# ARM / ACTUATOR SETTINGS
# ──────────────────────────────────────────────────────────────
ARM_INTERFACE = "gpio"      # "gpio" | "serial" | "simulate"
                            # Overridden to "simulate" when SIMULATE=True

# GPIO mode (Raspberry Pi direct)
ARM_GPIO_EXTEND_PIN = 17    # BCM pin to extend actuator
ARM_GPIO_RETRACT_PIN = 27   # BCM pin to retract actuator
ARM_EXTEND_DURATION = 1.5   # Seconds to hold actuator extended
ARM_RETRACT_DURATION = 1.0  # Seconds for retract move

# Serial mode (Arduino intermediary)
ARM_SERIAL_PORT = "/dev/ttyUSB0"
ARM_SERIAL_BAUD = 9600
ARM_SERIAL_STRIKE_CMD = b"STRIKE\n"

# Cooldown between strikes (seconds) — prevents rapid re-triggering
ARM_COOLDOWN = 3.0

# ──────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
DASHBOARD_ENABLED = True

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "robot.log")
