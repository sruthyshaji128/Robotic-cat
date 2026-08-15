"""
modules/rat_detector.py
Rat / rodent detection using a YOLOv8 ONNX model.

Production use:
    Train or download a rat-specific YOLOv8 model (e.g. from Roboflow Universe
    "rat-detection" dataset), export to ONNX, and point RAT_MODEL_PATH at it.
    Set RAT_DEMO_MODE = False and RAT_CLASS_NAMES = ["rat"] in config.py.

Demo / testing use (RAT_DEMO_MODE = True):
    Falls back to the generic YOLOv8n COCO model.  COCO contains small-animal
    classes (bird, cat, dog) that serve as stand-in triggers so the full
    detection → alert → dashboard pipeline can be exercised without a custom
    model.  Any COCO animal detection is labelled "RAT(demo)".

Usage:
    detector = RatDetector()
    detector.load()
    detections = detector.detect(frame)
    frame = detector.annotate_frame(frame, detections)
"""

import os
import logging
import urllib.request
import numpy as np
import cv2
from config import (
    RAT_MODEL_PATH,
    RAT_DETECTION_CONFIDENCE,
    RAT_CLASS_NAMES,
    RAT_DEMO_MODE,
)
from .weed_detector import COCO_NAMES, YOLOV8N_ONNX_URL

logger = logging.getLogger(__name__)

INFERENCE_SIZE = 320

# COCO classes used as rat proxies in demo mode (small/medium animals visible
# through a webcam that stand in for rodents during development)
_DEMO_PROXY_CLASSES = {"bird", "cat", "dog", "mouse"}


class RatDetection:
    """Represents a single rat / rodent detection result."""

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
        return (f"RatDetection(class={self.class_name}, conf={self.confidence:.2f}, "
                f"centroid={self.centroid})")


class RatDetector:
    """
    YOLOv8 rat / rodent detector.

    With RAT_DEMO_MODE=True (default): uses the generic YOLOv8n COCO model and
    treats bird/cat/dog detections as rat proxy triggers so the pipeline can be
    tested without a custom dataset.

    With RAT_DEMO_MODE=False: loads RAT_MODEL_PATH (a custom rat-trained ONNX)
    and filters detections against RAT_CLASS_NAMES.
    """

    def __init__(self, model_path: str = None, confidence: float = None):
        self.model_path = model_path or RAT_MODEL_PATH
        self.confidence = confidence or RAT_DETECTION_CONFIDENCE
        self._ort_session = None
        self._yolo = None
        self._use_ort = False
        self._loaded = False

    # ──────────────────────────────────────────────────────────────
    def load(self) -> bool:
        """
        Load the ONNX model.
        In demo mode, auto-downloads yolov8n.onnx if absent.
        In production mode, expects RAT_MODEL_PATH to already exist.
        """
        onnx_path = self.model_path
        if not onnx_path.endswith(".onnx"):
            onnx_path = os.path.splitext(onnx_path)[0] + ".onnx"

        if not os.path.isfile(onnx_path):
            if RAT_DEMO_MODE:
                logger.info("[RatDetector] Model not found at '%s'. Downloading YOLOv8n for demo...", onnx_path)
                self._download_onnx(onnx_path)
            else:
                logger.error(
                    "[RatDetector] Model not found at '%s'. "
                    "Provide a trained rat detection ONNX model or enable RAT_DEMO_MODE.",
                    onnx_path,
                )
                return False

        if os.path.isfile(onnx_path):
            if self._load_onnxruntime(onnx_path):
                return True

        logger.warning("[RatDetector] Falling back to ultralytics backend.")
        return self._load_ultralytics()

    def _download_onnx(self, dest: str) -> bool:
        try:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            logger.info("[RatDetector] Downloading ONNX from %s ...", YOLOV8N_ONNX_URL)

            def progress(b, bs, total):
                if total > 0:
                    pct = min(100, b * bs * 100 // total)
                    print(f"\r  Downloading... {pct}%", end="", flush=True)

            urllib.request.urlretrieve(YOLOV8N_ONNX_URL, dest, reporthook=progress)
            print()
            logger.info("[RatDetector] Downloaded: %s (%.1f MB)",
                        dest, os.path.getsize(dest) / 1e6)
            return True
        except Exception as e:
            logger.error("[RatDetector] ONNX download failed: %s", e)
            if os.path.isfile(dest):
                os.remove(dest)
            return False

    def _load_onnxruntime(self, onnx_path: str) -> bool:
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._ort_session = ort.InferenceSession(
                onnx_path, sess_options=opts, providers=["CPUExecutionProvider"]
            )
            self._use_ort = True
            self._loaded = True
            logger.info("[RatDetector][ONNXRuntime] Model loaded: %s", onnx_path)
            return True
        except ImportError:
            logger.warning("[RatDetector] onnxruntime not installed.")
            return False
        except Exception as e:
            logger.warning("[RatDetector] ONNXRuntime load failed: %s", e)
            return False

    def _load_ultralytics(self) -> bool:
        try:
            from ultralytics import YOLO
            pt = self.model_path if os.path.isfile(self.model_path) else "yolov8n.pt"
            self._yolo = YOLO(pt)
            self._use_ort = False
            self._loaded = True
            logger.info("[RatDetector][ultralytics] Model loaded: %s", pt)
            return True
        except ImportError:
            logger.error(
                "[RatDetector] No inference backend available. "
                "Install onnxruntime or ultralytics."
            )
            return False
        except Exception as e:
            logger.error("[RatDetector] ultralytics load failed: %s", e)
            return False

    # ──────────────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray) -> list:
        """
        Run rat detection on a BGR frame.
        Returns a list of RatDetection objects sorted by confidence (desc).
        """
        if not self._loaded:
            logger.error("[RatDetector] Model not loaded. Call load() first.")
            return []
        try:
            if self._use_ort:
                return self._detect_onnxruntime(frame)
            else:
                return self._detect_ultralytics(frame)
        except Exception as e:
            logger.error("[RatDetector] Detection error: %s", e)
            return []

    def _detect_onnxruntime(self, frame: np.ndarray) -> list:
        h, w = frame.shape[:2]

        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1.0 / 255.0,
            size=(INFERENCE_SIZE, INFERENCE_SIZE),
            swapRB=True,
            crop=False,
        )

        input_name = self._ort_session.get_inputs()[0].name
        output_name = self._ort_session.get_outputs()[0].name
        output = self._ort_session.run([output_name], {input_name: blob})
        preds = output[0][0]

        detections = []

        # YOLOv8 layout: (84, 8400) → transpose → (8400, 84)
        if len(preds.shape) == 2 and preds.shape[0] < preds.shape[1]:
            preds = preds.T
            for pred in preds:
                class_scores = pred[4:]
                cls_id = int(np.argmax(class_scores))
                conf = float(class_scores[cls_id])
                if conf < self.confidence:
                    continue

                cls_name = self._resolve_class(cls_id)
                if not self._is_rat_class(cls_name):
                    continue

                cx, cy, bw, bh = pred[:4]
                scale_x = w / INFERENCE_SIZE
                scale_y = h / INFERENCE_SIZE
                cx *= scale_x; cy *= scale_y
                bw *= scale_x; bh *= scale_y
                x1, y1 = cx - bw / 2, cy - bh / 2
                x2, y2 = cx + bw / 2, cy + bh / 2

                display_name = "rat(demo)" if RAT_DEMO_MODE else cls_name
                detections.append(RatDetection(
                    bbox=(max(0, x1), max(0, y1), min(w, x2), min(h, y2)),
                    confidence=conf,
                    class_name=display_name,
                ))

        # RT-DETR layout: (300, 6) → [cx, cy, w, h, conf, cls_id]
        elif len(preds.shape) == 2 and preds.shape[1] == 6:
            for pred in preds:
                conf = float(pred[4])
                cls_id = int(pred[5])
                if conf < self.confidence:
                    continue

                cls_name = self._resolve_class(cls_id)
                if not self._is_rat_class(cls_name):
                    continue

                cx, cy, bw, bh = pred[:4]
                cx *= w; cy *= h; bw *= w; bh *= h
                x1, y1 = cx - bw / 2, cy - bh / 2
                x2, y2 = cx + bw / 2, cy + bh / 2

                display_name = "rat(demo)" if RAT_DEMO_MODE else cls_name
                detections.append(RatDetection(
                    bbox=(max(0, x1), max(0, y1), min(w, x2), min(h, y2)),
                    confidence=conf,
                    class_name=display_name,
                ))

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
                if not self._is_rat_class(cls_name):
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                display_name = "rat(demo)" if RAT_DEMO_MODE else cls_name
                detections.append(RatDetection(
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    class_name=display_name,
                ))
        return detections

    # ──────────────────────────────────────────────────────────────
    def _resolve_class(self, cls_id: int) -> str:
        if RAT_DEMO_MODE:
            return COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id)
        return RAT_CLASS_NAMES[cls_id] if cls_id < len(RAT_CLASS_NAMES) else f"rodent_{cls_id}"

    def _is_rat_class(self, name: str) -> bool:
        """
        In demo mode: match any COCO animal proxy class.
        In production mode: match against RAT_CLASS_NAMES.
        """
        if RAT_DEMO_MODE:
            return name.lower() in _DEMO_PROXY_CLASSES
        name_lower = name.lower()
        return any(r.lower() in name_lower for r in RAT_CLASS_NAMES)

    # ──────────────────────────────────────────────────────────────
    def annotate_frame(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """
        Draw rat bounding boxes on the frame in red.
        Red distinguishes rats from weed (blue) and pest (orange) detections.
        """
        annotated = frame.copy()
        color = (0, 0, 220)  # red (BGR)
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"RAT:{det.class_name} {det.confidence:.0%}"
            label_y = max(y1 - 8, 15)
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, label_y - lh - 4), (x1 + lw, label_y + 2), color, -1)
            cv2.putText(annotated, label, (x1, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cx, cy = det.centroid
            cv2.circle(annotated, (cx, cy), 5, (80, 80, 255), -1)
        return annotated
