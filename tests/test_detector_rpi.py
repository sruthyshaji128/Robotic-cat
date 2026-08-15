#!/usr/bin/env python3
# Quick diagnostic: checks what works on this system
import sys
print("Python:", sys.version)

results = {}

try:
    import cv2
    results["cv2"] = cv2.__version__
except Exception as e:
    results["cv2"] = f"FAIL: {e}"

try:
    import numpy as np
    results["numpy"] = np.__version__
except Exception as e:
    results["numpy"] = f"FAIL: {e}"

try:
    import onnxruntime as ort
    results["onnxruntime"] = ort.__version__
except Exception as e:
    results["onnxruntime"] = f"FAIL: {e}"

try:
    import ultralytics
    results["ultralytics"] = ultralytics.__version__
except Exception as e:
    results["ultralytics"] = f"FAIL: {e}"

try:
    import torch
    results["torch"] = torch.__version__
except Exception as e:
    results["torch"] = f"FAIL: {e}"

print("\n=== Import Diagnostics ===")
for pkg, ver in results.items():
    status = "OK" if not ver.startswith("FAIL") else "FAIL"
    print(f"  [{status}] {pkg}: {ver}")

# Test cv2.dnn if cv2 loaded
if not results.get("cv2", "").startswith("FAIL"):
    import cv2
    try:
        attrs = dir(cv2.dnn)
        has_onnx = "readNetFromONNX" in attrs
        print(f"\n  cv2.dnn.readNetFromONNX available: {has_onnx}")
    except Exception as e:
        print(f"\n  cv2.dnn test failed: {e}")
