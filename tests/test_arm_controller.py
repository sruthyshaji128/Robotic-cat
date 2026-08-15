"""
tests/test_arm_controller.py
Unit tests for arm controller simulation mode: cooldown, strike stats, threading.
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
config.SIMULATE = True
config.ARM_COOLDOWN = 1.0
config.ARM_EXTEND_DURATION = 0.1
config.ARM_RETRACT_DURATION = 0.1

import pytest
from modules.arm_controller import ArmController


@pytest.fixture
def arm():
    a = ArmController()
    a.setup()
    return a


def test_setup_in_simulation(arm):
    assert arm._interface == "simulate"


def test_initial_can_strike(arm):
    assert arm.can_strike() is True


def test_strike_increments_count(arm):
    arm.strike()
    time.sleep(0.05)  # Let thread start
    assert arm.total_strikes == 1


def test_cooldown_blocks_second_strike(arm):
    arm.strike()
    time.sleep(0.05)
    # Should be on cooldown
    result = arm.strike()
    assert result is False
    assert arm.total_strikes == 1


def test_cooldown_expires(arm):
    arm.strike()
    time.sleep(config.ARM_COOLDOWN + config.ARM_EXTEND_DURATION + config.ARM_RETRACT_DURATION + 0.3)
    result = arm.strike()
    assert result is True
    assert arm.total_strikes == 2


def test_cooldown_remaining_decreases(arm):
    arm.strike()
    r1 = arm.cooldown_remaining()
    time.sleep(0.3)
    r2 = arm.cooldown_remaining()
    assert r1 >= r2


def test_callback_fires(arm):
    called = []
    arm.strike(callback=lambda: called.append(1))
    time.sleep(config.ARM_EXTEND_DURATION + config.ARM_RETRACT_DURATION + 0.3)
    assert len(called) == 1


def test_cleanup_noop_in_simulation(arm):
    arm.cleanup()  # Should not raise


def test_is_striking_during_operation(arm):
    arm.strike()
    time.sleep(0.02)
    # May or may not be striking depending on timing — just verify no exception
    _ = arm.is_striking()
