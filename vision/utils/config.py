"""
Central configuration for the vision pipeline.

Model note: DEFAULT_MODEL can be any Ultralytics YOLO weights file --
"yolov8n.pt" (original) or "yolo11n.pt" (newer, same library, drop-in
replacement -- ultralytics added YOLOv11 support in the same `ultralytics`
pip package, no new dependency needed). Swap via AEGISNET_MODEL env var
or --model CLI flag; nothing else in the codebase needs to change.

Per the code review: don't hard-code model name, confidence threshold,
camera index, or backend URL inside detect_webcam.py / observation_engine.py.
Everything here can still be overridden by CLI args at runtime --
this file just defines the defaults in one place.
"""

import os

# --- Detection ---
# "yolov8n.pt" (original) or "yolo11n.pt" (newer YOLOv11, same ultralytics package)
DEFAULT_MODEL = os.environ.get("AEGISNET_MODEL", "yolov8n.pt")
DEFAULT_CONFIDENCE = float(os.environ.get("AEGISNET_CONFIDENCE", "0.5"))
DEFAULT_CAMERA_INDEX = int(os.environ.get("AEGISNET_CAMERA_INDEX", "0"))

# --- Tracking ---
# "iou" = the custom SimpleTracker in tracker.py (zero dependencies, always works)
# "bytetrack" = ultralytics' built-in ByteTrack (better under occlusion, needs
#               model.track() instead of model.predict() -- see detect_webcam.py --tracker flag)
DEFAULT_TRACKER = os.environ.get("AEGISNET_TRACKER", "iou")

# --- Hazard rules ---
INTEREST_CLASSES = {"backpack", "suitcase", "handbag"}  # move to a JSON/YAML file later if this grows
HIGH_CONFIDENCE_THRESHOLD = 0.75

# --- Backend integration ---
DEFAULT_BACKEND_URL = os.environ.get("AEGISNET_BACKEND", "http://localhost:8000")
HTTP_TIMEOUT_S = float(os.environ.get("AEGISNET_HTTP_TIMEOUT", "3.0"))

# De-duplication: don't re-report the same label more than once per this window.
DEDUP_WINDOW_S = 5.0

# Telemetry snapshot: how stale a cached position can be before we warn about it.
TELEMETRY_STALE_AFTER_S = 10.0
