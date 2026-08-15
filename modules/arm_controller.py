"""
modules/arm_controller.py
Controls the linear actuator via GPIO (RPi), Serial (Arduino) or simulation.
"""

import time
import logging
import threading
from config import (
    SIMULATE, ARM_INTERFACE,
    ARM_GPIO_EXTEND_PIN, ARM_GPIO_RETRACT_PIN,
    ARM_EXTEND_DURATION, ARM_RETRACT_DURATION,
    ARM_SERIAL_PORT, ARM_SERIAL_BAUD, ARM_SERIAL_STRIKE_CMD,
    ARM_COOLDOWN
)

logger = logging.getLogger(__name__)


class ArmController:
    """
    Controls the linear actuator (plough arm).

    Modes:
        "gpio"     — Directly drives GPIO pins on Raspberry Pi
        "serial"   — Sends commands to an Arduino over UART/USB
        "simulate" — Logs events only, no hardware interaction

    Usage:
        arm = ArmController()
        arm.setup()
        arm.strike()   # Non-blocking; runs in background thread
        arm.cleanup()
    """

    def __init__(self):
        # Determine effective interface
        if SIMULATE:
            self._interface = "simulate"
        else:
            self._interface = ARM_INTERFACE

        self._gpio = None
        self._serial = None
        self._last_strike_time = 0.0
        self._striking = False
        self._lock = threading.Lock()

        # Statistics
        self.total_strikes = 0

    # ──────────────────────────────────────────────
    def setup(self) -> bool:
        """Initialise hardware. Returns True on success."""
        if self._interface == "gpio":
            return self._setup_gpio()
        elif self._interface == "serial":
            return self._setup_serial()
        else:
            logger.info("[ARM] Simulation mode — no hardware initialised.")
            return True

    def _setup_gpio(self) -> bool:
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(ARM_GPIO_EXTEND_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(ARM_GPIO_RETRACT_PIN, GPIO.OUT, initial=GPIO.LOW)
            logger.info("[ARM] GPIO initialised — extend=%d, retract=%d",
                        ARM_GPIO_EXTEND_PIN, ARM_GPIO_RETRACT_PIN)
            return True
        except ImportError:
            logger.error("[ARM] RPi.GPIO not available. Run on Raspberry Pi or set SIMULATE=True.")
            return False
        except Exception as e:
            logger.error("[ARM] GPIO setup failed: %s", e)
            return False

    def _setup_serial(self) -> bool:
        try:
            import serial
            self._serial = serial.Serial(ARM_SERIAL_PORT, ARM_SERIAL_BAUD, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            logger.info("[ARM] Serial port opened: %s @ %d baud", ARM_SERIAL_PORT, ARM_SERIAL_BAUD)
            return True
        except ImportError:
            logger.error("[ARM] pyserial not installed. Run: pip install pyserial")
            return False
        except Exception as e:
            logger.error("[ARM] Serial setup failed: %s", e)
            return False

    # ──────────────────────────────────────────────
    def can_strike(self) -> bool:
        """Return True if cooldown has elapsed and no strike is in progress."""
        with self._lock:
            elapsed = time.time() - self._last_strike_time
            return not self._striking and elapsed >= ARM_COOLDOWN

    def strike(self, callback=None) -> bool:
        """
        Trigger an arm strike. Non-blocking — runs in a background thread.

        Args:
            callback: Optional callable invoked when strike completes.
        Returns:
            True if strike was started, False if on cooldown.
        """
        if not self.can_strike():
            logger.debug("[ARM] Strike skipped — cooldown active.")
            return False

        with self._lock:
            self._striking = True
            self._last_strike_time = time.time()
            self.total_strikes += 1

        t = threading.Thread(target=self._execute_strike, args=(callback,), daemon=True)
        t.start()
        return True

    def _execute_strike(self, callback):
        try:
            logger.info("[ARM] *** STRIKE #%d - EXTENDING ***", self.total_strikes)
            if self._interface == "gpio":
                self._gpio_extend()
            elif self._interface == "serial":
                self._serial_send()
            else:
                self._sim_strike()
        finally:
            with self._lock:
                self._striking = False
            logger.info("[ARM] Strike #%d complete — arm retracted.", self.total_strikes)
            if callback:
                callback()

    def _gpio_extend(self):
        GPIO = self._gpio
        GPIO.output(ARM_GPIO_EXTEND_PIN, GPIO.HIGH)
        time.sleep(ARM_EXTEND_DURATION)
        GPIO.output(ARM_GPIO_EXTEND_PIN, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(ARM_GPIO_RETRACT_PIN, GPIO.HIGH)
        time.sleep(ARM_RETRACT_DURATION)
        GPIO.output(ARM_GPIO_RETRACT_PIN, GPIO.LOW)

    def _serial_send(self):
        if self._serial and self._serial.is_open:
            self._serial.write(ARM_SERIAL_STRIKE_CMD)
            self._serial.flush()
            # Wait for confirmation or fixed duration
            deadline = time.time() + ARM_EXTEND_DURATION + ARM_RETRACT_DURATION + 1
            while time.time() < deadline:
                if self._serial.in_waiting:
                    resp = self._serial.readline().decode(errors="ignore").strip()
                    if resp == "DONE":
                        break
                time.sleep(0.05)

    def _sim_strike(self):
        logger.info("[ARM][SIM] Extend → hold %.1fs → retract %.1fs",
                    ARM_EXTEND_DURATION, ARM_RETRACT_DURATION)
        time.sleep(ARM_EXTEND_DURATION + ARM_RETRACT_DURATION)

    # ──────────────────────────────────────────────
    def is_striking(self) -> bool:
        with self._lock:
            return self._striking

    def cooldown_remaining(self) -> float:
        """Return seconds remaining in the cooldown (0 if ready)."""
        elapsed = time.time() - self._last_strike_time
        return max(0.0, ARM_COOLDOWN - elapsed)

    # ──────────────────────────────────────────────
    def cleanup(self):
        """Release hardware resources."""
        if self._interface == "gpio" and self._gpio:
            self._gpio.cleanup()
            logger.info("[ARM] GPIO cleaned up.")
        if self._interface == "serial" and self._serial:
            self._serial.close()
            logger.info("[ARM] Serial port closed.")
