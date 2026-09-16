"""
YOLO Segmentation -- optional alternative to bounding-box detection.

Uses the same ultralytics package, just a "-seg" model variant
(e.g. "yolov8n-seg.pt" or "yolo11n-seg.pt") which outputs pixel masks
instead of rectangular boxes. Useful if you want to know the actual
shape/outline of a detected object rather than just its bounding box.

This needs the same `ultralytics` + `opencv-python` install as
detect_webcam.py -- no new dependency, just a different model file
(auto-downloaded on first run, same as the detection model).

Usage:
    python detect_segmentation.py
"""

import argparse
import cv2
from ultralytics import YOLO

from vision.utils.config import DEFAULT_CAMERA_INDEX, DEFAULT_CONFIDENCE


def main():
    parser = argparse.ArgumentParser(description="AEGISNET segmentation demo")
    parser.add_argument("--model", default="yolov8n-seg.pt", help="Segmentation model file")
    parser.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX)
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    args = parser.parse_args()

    model = YOLO(args.model)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera})")

    print("-- Segmentation mode. Press 'q' to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            results = model.predict(frame, conf=args.confidence, verbose=False)
            annotated = results[0].plot()  # ultralytics draws masks automatically for -seg models
            cv2.imshow("AEGISNET SENTINEL - Segmentation", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
