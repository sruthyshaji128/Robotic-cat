
from ultralytics import YOLO
import cv2
import numpy as np
import os
import random

class Detector:
    def __init__(self, model_path="yolov8n.pt", demo_mode=True):
        self.demo_mode = demo_mode
        self.model = None
        try:
            if not demo_mode and os.path.exists(model_path):
                self.model = YOLO(model_path)
            elif not demo_mode:
                print(f"Model not found at {model_path}, downloading YOLOv8n...")
                self.model = YOLO("yolov8n.pt") # Auto download
        except Exception as e:
            print(f"Failed to load YOLO model: {e}. Switching to DEMO MODE.")
            self.demo_mode = True

    def detect(self, frame):
        if self.demo_mode or self.model is None:
            return self._mock_detect(frame)
        
        results = self.model(frame)
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0]) * 100 # Convert to 0-100 scale
                label = self.model.names[cls_id]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Filter for simulation "weeds" (e.g., replace 'potted plant' or similar with 'weed')
                # For demo purposes, let's treat 'potted plant', 'vase', 'bottle' as valid targets
                if label in ['potted plant', 'vase', 'bottle', 'cup']:
                    label = 'Weed'
                elif label in ['person', 'chair', 'cell phone', 'laptop']: # Mocking Paddy for simulation
                    label = 'Paddy'

                detections.append({
                    "class": label,
                    "confidence": conf,
                    "box": [x1, y1, x2, y2]
                })
        return detections

    def _mock_detect(self, frame):
        # Simulate occasional detection
        if random.random() < 0.15: # 15% chance per frame
             h, w, _ = frame.shape
             x1 = random.randint(0, w - 100)
             y1 = random.randint(0, h - 100)
             
             # Randomly choose between Paddy and Weed
             is_paddy = random.random() < 0.6
             label = "Paddy" if is_paddy else "Weed"
             
             return [{
                 "class": label,
                 "confidence": (0.85 + (random.random() * 0.1)) * 100,
                 "box": [x1, y1, x1+100, y1+100]
             }]
        return []

    def draw_boxes(self, frame, detections):
        for d in detections:
            x1, y1, x2, y2 = map(int, d['box'])
            label = f"{d['class']} {d['confidence']:.2f}"
            color = (0, 0, 255) if d['class'] == 'weed' else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        return frame
