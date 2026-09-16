"""
Milestone 2: Real-time object detection from a webcam using YOLO + OpenCV.

Fixes applied from the code review:
  - Model name, confidence threshold, and camera index are now CLI
    arguments (with config.py defaults), not hard-coded.
  - Ctrl+C and camera-release cleanup handled consistently via
    try/finally.
  - Kept as a simple, standalone M2 test -- no backend/database logic
    mixed in here. Detections are handed to ObservationEngine, which
    lives in its own file.

Install:
    pip install ultralytics opencv-python httpx

Usage:
    python -m vision.detectors.detect_webcam
    python -m vision.detectors.detect_webcam --camera 1 --confidence 0.6 --model yolov8n.pt
Press 'q' to quit, or Ctrl+C in the terminal.
"""

import argparse
import asyncio

import cv2
from ultralytics import YOLO

from vision.utils.config import DEFAULT_MODEL, DEFAULT_CONFIDENCE, DEFAULT_CAMERA_INDEX, DEFAULT_BACKEND_URL, DEFAULT_TRACKER
from vision.detectors.observation_engine import ObservationEngine


def parse_args():
    parser = argparse.ArgumentParser(description="AEGISNET webcam object detection")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="YOLO model file")
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE, help="Min confidence to report")
    parser.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX, help="Webcam device index")
    parser.add_argument("--backend", default=DEFAULT_BACKEND_URL, help="Backend URL to post detections to")
    parser.add_argument("--no-backend", action="store_true", help="Run detection only, skip posting to backend")
    parser.add_argument(
        "--tracker", choices=["iou", "bytetrack"], default=DEFAULT_TRACKER,
        help="'iou' = custom SimpleTracker (tracker.py, zero dependencies). "
             "'bytetrack' = ultralytics' built-in ByteTrack (better under occlusion, "
             "same ultralytics package, no extra install needed).",
    )
    return parser.parse_args()


async def run(args):
    model = YOLO(args.model)
    engine = None if args.no_backend else ObservationEngine(backend_url=args.backend)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {args.camera})")

    pending_tasks = set()

    try:
        print(f"-- Detecting with {args.model} (confidence >= {args.confidence}). Press 'q' to quit.")
        while True:
            ok, frame = cap.read()
            if not ok:
                print("!! Failed to read frame from camera, stopping.")
                break

            results = model.predict(frame, conf=args.confidence, verbose=False) if args.tracker == "iou" else \
                model.track(frame, conf=args.confidence, tracker="bytetrack.yaml", persist=True, verbose=False)
            annotated = results[0].plot()

            # Non-blocking: fire observation posts as background tasks so
            # a slow/unreachable backend never stalls the video loop.
            if engine is not None:
                for box in results[0].boxes:
                    label = model.names[int(box.cls[0])]
                    confidence = float(box.conf[0])
                    task = asyncio.create_task(engine.observe_and_report(label, confidence))
                    pending_tasks.add(task)
                    task.add_done_callback(pending_tasks.discard)

            cv2.imshow("AEGISNET SENTINEL - Object Detection", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            # Let queued background POSTs get a chance to run each frame.
            await asyncio.sleep(0)

    except KeyboardInterrupt:
        print("\n-- Interrupted, shutting down cleanly...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        if engine is not None:
            await engine.close()
        print("-- Camera released, cleanup complete.")


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
