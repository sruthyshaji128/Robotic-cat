"""
modules/servo_controller.py
Servo motor control via GPIO PWM (Raspberry Pi).

Strike sequence:
    0° (rest) → 90° (strike) → hold SERVO_HOLD_DURATION seconds → 0° (rest)

Modes:
    GPIO  — drives hardware PWM on SERVO_PIN (BCM numbering)
    Simulate — logs timing only, no hardware interaction

Usage:
    servo = ServoController()
    servo.setup()
    servo.strike()        # triggered on weed detection (respects disengage)
    servo.test_strike()   # manual test from dashboard (ignores disengage)
    servo.disengage()     # stop PWM signal (servo relaxes)
    servo.engage()        # restart PWM, servo ready
    servo.cleanup()
"""

import time
import logging
import threading
from config import (
    SIMULATE,
    SERVO_PIN,
    SERVO_FREQUENCY,
    SERVO_DUTY_0DEG,
    SERVO_DUTY_90DEG,
    SERVO_HOLD_DURATION,
    SERVO_MOVE_DELAY,
)

logger = logging.getLogger(__name__)


class ServoController:
    """
    Controls a hobby servo motor via RPi.GPIO hardware PWM.

    The servo performs a strike sequence:
        0° → 90° (hold SERVO_HOLD_DURATION s) → 0°

    Thread-safe: strike() and test_strike() run in background threads.
    Only one strike can run at a time.
    """

    def __init__(self):
        self._pwm        = None
        self._gpio       = None
        self._striking   = False
        self._disengaged = False
        self._simulate   = SIMULATE
        self._lock       = threading.Lock()
        self.total_strikes = 0

    # ── Setup / teardown ──────────────────────────────────────
    def setup(self) -> bool:
        """Initialise GPIO PWM. Returns True on success."""
        if self._simulate:
            logger.info("[SERVO] Simulation mode — no hardware initialised.")
            return True
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(SERVO_PIN, GPIO.OUT)
            self._pwm = GPIO.PWM(SERVO_PIN, SERVO_FREQUENCY)
            self._pwm.start(SERVO_DUTY_0DEG)   # start at rest position
            logger.info("[SERVO] GPIO PWM started — pin=%d, freq=%dHz, 0°=%.1f%%, 90°=%.1f%%",
                        SERVO_PIN, SERVO_FREQUENCY, SERVO_DUTY_0DEG, SERVO_DUTY_90DEG)
            return True
        except ImportError:
            logger.error("[SERVO] RPi.GPIO not available. Run on Raspberry Pi or set SIMULATE=True.")
            self._simulate = True
            return False
        except Exception as e:
            logger.error("[SERVO] GPIO setup failed: %s", e)
            self._simulate = True
            return False

    def cleanup(self):
        """Stop PWM and release GPIO resources."""
        try:
            if self._pwm:
                self._pwm.stop()
            if self._gpio and not self._simulate:
                # Only cleanup the servo pin to avoid conflicting with arm GPIO
                self._gpio.setup(SERVO_PIN, self._gpio.IN)
            logger.info("[SERVO] Cleaned up.")
        except Exception as e:
            logger.warning("[SERVO] Cleanup error: %s", e)

    # ── Public control ────────────────────────────────────────
    def strike(self) -> bool:
        """
        Trigger the strike sequence if not disengaged and not already striking.
        Returns True if strike was started, False otherwise.
        """
        with self._lock:
            if self._disengaged:
                logger.debug("[SERVO] Strike skipped — servo disengaged.")
                return False
            if self._striking:
                logger.debug("[SERVO] Strike skipped — already striking.")
                return False
        return self._launch_strike(is_test=False)

    def test_strike(self) -> bool:
        """
        Trigger the strike sequence from dashboard test button.
        Ignores the disengaged flag — always executes so the user can verify hardware.
        Returns True if started, False if already striking.
        """
        with self._lock:
            if self._striking:
                logger.debug("[SERVO] Test skipped — already striking.")
                return False
        return self._launch_strike(is_test=True)

    def disengage(self):
        """Stop the PWM signal — servo goes limp / relaxes. Blocks new auto-strikes."""
        with self._lock:
            self._disengaged = True
        if self._pwm and not self._simulate:
            self._pwm.ChangeDutyCycle(0)   # 0% = no signal → servo relaxes
        logger.info("[SERVO] Disengaged.")

    def engage(self):
        """Re-enable the servo and return to rest position."""
        with self._lock:
            self._disengaged = False
        if self._pwm and not self._simulate:
            self._pwm.ChangeDutyCycle(SERVO_DUTY_0DEG)
            time.sleep(SERVO_MOVE_DELAY)
        logger.info("[SERVO] Engaged — at rest (0°).")

    # ── State queries ─────────────────────────────────────────
    def is_striking(self) -> bool:
        with self._lock:
            return self._striking

    def is_disengaged(self) -> bool:
        with self._lock:
            return self._disengaged

    # ── Internal ──────────────────────────────────────────────
    def _launch_strike(self, is_test: bool) -> bool:
        with self._lock:
            self._striking = True
            self.total_strikes += 1
            strike_num = self.total_strikes
        tag = "TEST" if is_test else "AUTO"
        t = threading.Thread(
            target=self._execute_strike,
            args=(strike_num, tag),
            daemon=True,
        )
        t.start()
        return True

    def _execute_strike(self, strike_num: int, tag: str):
        logger.info("[SERVO][%s] Strike #%d — 0° → 90°", tag, strike_num)
        try:
            self._move_to(SERVO_DUTY_90DEG)          # swing to 90°
            logger.info("[SERVO][%s] Holding at 90° for %.1fs", tag, SERVO_HOLD_DURATION)
            time.sleep(SERVO_HOLD_DURATION)          # hold
            self._move_to(SERVO_DUTY_0DEG)           # return to 0°
            logger.info("[SERVO][%s] Strike #%d complete — back to 0°", tag, strike_num)
        except Exception as e:
            logger.error("[SERVO] Strike error: %s", e)
        finally:
            with self._lock:
                self._striking = False

    def _move_to(self, duty: float):
        """Set servo duty cycle and wait for it to reach position."""
        if self._simulate:
            logger.info("[SERVO][SIM] → duty %.1f%% (%.0f°)",
                        duty,
                        0 if duty == SERVO_DUTY_0DEG else 90)
            time.sleep(SERVO_MOVE_DELAY)
            return
        if self._pwm:
            self._pwm.ChangeDutyCycle(duty)
            time.sleep(SERVO_MOVE_DELAY)
