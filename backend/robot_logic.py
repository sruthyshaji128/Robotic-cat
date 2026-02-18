
import time
from enum import Enum

class RobotState(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DETECTING = "DETECTING"
    ACTION_TRIGGERED = "ACTION_TRIGGERED"

class RobotLogic:
    def __init__(self):
        self.state = RobotState.IDLE
        self.last_action_time = 0
        self.action_duration = 3.0  # seconds to stay in ACTION state
        
        # Statistics
        self.total_detections = 0
        self.weeds_found = 0
        self.other_objects = 0
        
        # System control
        self.is_active = False

    def start(self):
        self.is_active = True
        self.state = RobotState.RUNNING

    def stop(self):
        self.is_active = False
        self.state = RobotState.STOPPED

    def update(self, detections: list):
        if not self.is_active:
            return

        # Update statistics based on new detections (only when active)
        self.total_detections += len(detections)
        for d in detections:
            if d['class'] == 'Weed':
                self.weeds_found += 1
            else:
                self.other_objects += 1

        current_time = time.time()

        if self.state == RobotState.ACTION_TRIGGERED:
            if current_time - self.last_action_time > self.action_duration:
                self.state = RobotState.RUNNING
            return

        # Check for weeds in detections
        has_weed = any(d['class'] == 'Weed' for d in detections)

        if has_weed:
            self.trigger_action()
        elif len(detections) > 0:
             self.state = RobotState.DETECTING
        else:
            self.state = RobotState.RUNNING

    def trigger_action(self):
        self.state = RobotState.ACTION_TRIGGERED
        self.last_action_time = time.time()

    def get_status(self):
        # Generate mock power data
        solar_v = 18.5 + (time.time() % 10) * 0.1
        solar_a = 2.1 + (time.time() % 5) * 0.05
        battery_pct = 85.0 - (time.time() % 3600) / 600.0 # Slow drain
        
        return {
            "state": self.state.value,
            "stats": {
                "total_detections": self.total_detections,
                "weeds_found": self.weeds_found,
                "other_objects": self.other_objects
            },
            "power": {
                "solar": {
                    "v": round(solar_v, 2),
                    "a": round(solar_a, 2),
                    "w": round(solar_v * solar_a, 2),
                    "charging": solar_a > 0.5
                },
                "battery": {
                    "percentage": round(battery_pct, 1),
                    "v": 12.4,
                    "status": "GOOD" if battery_pct > 20 else "LOW"
                }
            }
        }
