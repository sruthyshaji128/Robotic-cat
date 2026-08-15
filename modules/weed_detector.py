"""
modules/weed_detector.py
Weed detection using OpenCV DNN module — works natively on Raspberry Pi 4 ARM64.

Backend priority:
  1. OpenCV DNN (cv2.dnn)  — reads ONNX model, pure C++/ARM, no PyTorch/onnxruntime
  2. ultralytics (PyTorch)  — used on PC/GPU where AVX2 is available
"""

import os
import logging
import urllib.request
import numpy as np
import cv2
from config import MODEL_PATH, DETECTION_CONFIDENCE, WEED_CLASS_NAMES, DEMO_MODE

logger = logging.getLogger(__name__)

# COCO class names (YOLOv8n default, 80 classes)
COCO_NAMES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack",
    "umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball",
    "kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket",
    "bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair",
    "couch","potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator",
    "book","clock","vase","scissors","teddy bear","hair drier","toothbrush"
]

YOLOV8N_ONNX_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx"
INPUT_SIZE = 640   # YOLOv8n default input size


class Detection:
    """Represents a single weed detection."""
    def __init__(self, bbox, confidence, class_name):
        self.bbox = tuple(int(v) for v in bbox)
        self.confidence = float(confidence)
        self.class_name = class_name

    @property
    def centroid(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    def __repr__(self):
        return (f"Detection(class={self.class_name}, conf={self.confidence:.2f}, "
                f"centroid={self.centroid})")


class WeedDetector:
    """
    YOLOv8 weed detector — uses OpenCV DNN on RPi, ultralytics on PC.

    Usage:
        detector = WeedDetector()
        detector.load()
        detections = detector.detect(frame)
    """

    def __init__(self, model_path: str = None, confidence: float = None):
        self.model_path = model_path or MODEL_PATH
        self.confidence = confidence or DETECTION_CONFIDENCE
        self._net = None          # OpenCV DNN net
        self._yolo = None         # ultralytics YOLO model
        self._use_ort = False
        self._loaded = False

    # ──────────────────────────────────────────────────────────
    def load(self) -> bool:
        """
        Load the model. 
        Tries OpenCV DNN (ONNX) first — works on all platforms including RPi.
        Falls back to ultralytics (PyTorch) on PC.
        """
        onnx_path = self.model_path.replace(".pt", ".onnx")
        if not onnx_path.endswith(".onnx"):
            onnx_path = os.path.splitext(self.model_path)[0] + ".onnx"

        # 1. Try onnxruntime (ARM-safe)
        if not os.path.isfile(onnx_path):
            logger.info("ONNX model not found at '%s'. Downloading...", onnx_path)
            self._download_onnx(onnx_path)

        if os.path.isfile(onnx_path):
            if self._load_onnxruntime(onnx_path):
                return True

        # 2. Fallback: ultralytics (PyTorch) — only works on PC with AVX2
        logger.warning("Falling back to ultralytics/PyTorch backend.")
        return self._load_ultralytics()

    def _download_onnx(self, dest: str) -> bool:
        """Download YOLOv8n ONNX weights from Ultralytics GitHub."""
        try:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            logger.info("Downloading ONNX from %s ...", YOLOV8N_ONNX_URL)

            def progress(b, bs, total):
                if total > 0:
                    pct = min(100, b * bs * 100 // total)
                    print(f"\r  Downloading... {pct}%", end="", flush=True)

            urllib.request.urlretrieve(YOLOV8N_ONNX_URL, dest, reporthook=progress)
            print()
            logger.info("Downloaded: %s (%.1f MB)", dest, os.path.getsize(dest) / 1e6)
            return True
        except Exception as e:
            logger.error("ONNX download failed: %s", e)
            if os.path.isfile(dest):
                os.remove(dest)
            return False

    def _load_onnxruntime(self, onnx_path: str) -> bool:
        """Load ONNX model using onnxruntime (Supports both YOLO and RT-DETR)"""
        try:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._ort_session = ort.InferenceSession(onnx_path, sess_options=options, providers=['CPUExecutionProvider'])
            self._use_ort = True
            self._loaded = True
            logger.info("[ONNXRuntime] Model loaded: %s", onnx_path)
            return True
        except ImportError:
            logger.warning("onnxruntime not installed. Please pip install onnxruntime")
            return False
        except Exception as e:
            logger.warning("ONNXRuntime load failed: %s", e)
            return False

    def _load_ultralytics(self) -> bool:
        """Load via ultralytics (PyTorch) — PC only."""
        try:
            from ultralytics import YOLO
            pt = self.model_path if os.path.isfile(self.model_path) else "yolov8n.pt"
            self._yolo = YOLO(pt)
            self._use_ort = False
            self._loaded = True
            logger.info("[ultralytics] Model loaded: %s", pt)
            return True
        except ImportError:
            logger.error("No inference backend available. Install onnxruntime or ultralytics.")
            return False
        except Exception as e:
            logger.error("ultralytics load failed: %s", e)
            return False

    # ──────────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray) -> list:
        """Run detection on a BGR frame. Returns list of Detection objects."""
        if not self._loaded:
            logger.error("Model not loaded. Call detector.load() first.")
            return []
        try:
            if self._use_ort:
                return self._detect_onnxruntime(frame)
            else:
                return self._detect_ultralytics(frame)
        except Exception as e:
            logger.error("Detection error: %s", e)
            return []

    def _detect_onnxruntime(self, frame: np.ndarray) -> list:
        """onnxruntime inference for both YOLOv8 and RT-DETR schemas."""
        import time
        t0 = time.time()
        
        h, w = frame.shape[:2]

        # Use 320x320 since we trained the Nano model for fast RPi inference
        INFERENCE_SIZE = 320

        # Preprocess: resize to INFERENCE_SIZE, convert to blob (RGB)
        blob = cv2.dnn.blobFromImage(
            frame, scalefactor=1.0 / 255.0,
            size=(INFERENCE_SIZE, INFERENCE_SIZE),
            swapRB=True, crop=False
        )
        
        input_name = self._ort_session.get_inputs()[0].name
        output_name = self._ort_session.get_outputs()[0].name
        
        t1 = time.time()
        output = self._ort_session.run([output_name], {input_name: blob})
        t2 = time.time()
        
        preds = output[0][0]  # Get batch 0. Shape: (84, 8400) for YOLO, or (300, 6) for RT-DETR
        logger.info("[ONNXRuntime] Inference took %.2fs (Prep: %.2fs)", t2-t1, t1-t0)
        
        detections = []
        
        # 1. Handle YOLOv8 formats: (84, 8400) or (6, 2100) or any where classes+coords < anchors
        if len(preds.shape) == 2 and preds.shape[0] < preds.shape[1]:
            preds = preds.T    # (anchors, coords+classes)
            for pred in preds:
                class_scores = pred[4:]
                cls_id = int(np.argmax(class_scores))
                conf = float(class_scores[cls_id])
                if conf < self.confidence:
                    continue

                if cls_id == 1:
                    cls_name = "weed"
                elif cls_id == 0:
                    cls_name = "crop"
                else:
                    cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id)

                # Convert normalized cx,cy,w,h → pixel coords for original frame size
                cx, cy, bw, bh = pred[:4]
                scale_x = w / INFERENCE_SIZE
                scale_y = h / INFERENCE_SIZE
                cx *= scale_x; cy *= scale_y
                bw *= scale_x; bh *= scale_y
                x1, y1 = cx - bw / 2, cy - bh / 2
                x2, y2 = cx + bw / 2, cy + bh / 2

                detections.append(Detection(
                    bbox=(max(0, x1), max(0, y1), min(w, x2), min(h, y2)),
                    confidence=conf,
                    class_name=cls_name
                ))

        # 2. Handle RT-DETR format: (300, 6) -> [cx, cy, w, h, conf, cls_id]
        elif len(preds.shape) == 2 and preds.shape[1] == 6:
            for pred in preds:
                conf = float(pred[4])
                cls_id = int(pred[5])
                if conf < self.confidence:
                    continue

                # Assume 2 classes (crop=0, weed=1) for RT-DETR based on data.yaml
                # But fallback to COCO if there's more
                if cls_id == 1:
                    cls_name = "weed"
                elif cls_id == 0:
                    cls_name = "crop"
                else:
                    cls_name = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id)

                # RT-DETR outputs normalized (0-1) coordinates [cx, cy, w, h] from Ultralytics export
                cx, cy, bw, bh = pred[:4]
                cx *= w
                cy *= h
                bw *= w
                bh *= h
                x1, y1 = cx - bw / 2, cy - bh / 2
                x2, y2 = cx + bw / 2, cy + bh / 2

                detections.append(Detection(
                    bbox=(max(0, x1), max(0, y1), min(w, x2), min(h, y2)),
                    confidence=conf,
                    class_name=cls_name
                ))

        # Sort by confidence
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[:10]

    def _detect_ultralytics(self, frame: np.ndarray) -> list:
        results = self._yolo(frame, conf=self.confidence, verbose=False)
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = result.names.get(cls_id, str(cls_id))
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(Detection(
                    bbox=(x1, y1, x2, y2), confidence=conf,
                    class_name=cls_name
                ))
        return detections

    # ──────────────────────────────────────────────────────────
    def annotate_frame(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw detection boxes on a copy of the frame."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = (0, 60, 220)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.0%}"
            label_y = max(y1 - 8, 15)
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, label_y - lh - 4), (x1 + lw, label_y + 2), color, -1)
            cv2.putText(annotated, label, (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cx, cy = det.centroid
            cv2.circle(annotated, (cx, cy), 5, (0, 255, 255), -1)
        return annotated
