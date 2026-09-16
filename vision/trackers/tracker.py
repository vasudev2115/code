"""
Lightweight object tracker -- assigns stable IDs to detections across
frames so two different objects with the same label aren't confused,
and the same object isn't re-reported as if it were new every frame.

Per the roadmap: "tracker.py add karo taaki same object ko frames ke
across track kiya ja sake." This uses simple IoU (box overlap) matching
frame-to-frame -- no ML model needed, cheap enough to run in the same
loop as YOLO.

This is intentionally basic (nearest-IoU matching, no Kalman filter/
re-ID). Good enough for a single-camera demo; swap for ByteTrack or
DeepSORT later if you need robustness to occlusion.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TrackedBox:
    track_id: int
    label: str
    confidence: float
    xyxy: tuple  # (x1, y1, x2, y2)
    frames_seen: int = 1
    frames_missing: int = 0


def _iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter_area

    return inter_area / union if union > 0 else 0.0


class SimpleTracker:
    IOU_MATCH_THRESHOLD = 0.3
    MAX_FRAMES_MISSING = 10  # drop a track if unseen for this many frames

    def __init__(self):
        self._next_id = 1
        self._tracks: List[TrackedBox] = []

    def update(self, detections: List[dict]) -> List[TrackedBox]:
        """detections: list of {"label": str, "confidence": float, "xyxy": (x1,y1,x2,y2)}

        Returns the current list of TrackedBox, each with a stable track_id.
        """
        unmatched_detections = list(detections)
        updated_tracks = []

        for track in self._tracks:
            best_match, best_iou = None, 0.0
            for det in unmatched_detections:
                if det["label"] != track.label:
                    continue
                iou = _iou(track.xyxy, det["xyxy"])
                if iou > best_iou:
                    best_match, best_iou = det, iou

            if best_match is not None and best_iou >= self.IOU_MATCH_THRESHOLD:
                track.xyxy = best_match["xyxy"]
                track.confidence = best_match["confidence"]
                track.frames_seen += 1
                track.frames_missing = 0
                unmatched_detections.remove(best_match)
                updated_tracks.append(track)
            else:
                track.frames_missing += 1
                if track.frames_missing <= self.MAX_FRAMES_MISSING:
                    updated_tracks.append(track)

        for det in unmatched_detections:
            updated_tracks.append(
                TrackedBox(
                    track_id=self._next_id,
                    label=det["label"],
                    confidence=det["confidence"],
                    xyxy=det["xyxy"],
                )
            )
            self._next_id += 1

        self._tracks = updated_tracks
        return [t for t in self._tracks if t.frames_missing == 0]


if __name__ == "__main__":
    # Tiny self-test: same object drifting slightly across 3 frames should keep one ID.
    tracker = SimpleTracker()

    frame1 = [{"label": "person", "confidence": 0.9, "xyxy": (100, 100, 200, 300)}]
    frame2 = [{"label": "person", "confidence": 0.88, "xyxy": (105, 102, 205, 302)}]
    frame3 = [{"label": "person", "confidence": 0.91, "xyxy": (110, 105, 210, 305)},
              {"label": "backpack", "confidence": 0.7, "xyxy": (400, 400, 450, 480)}]

    for i, frame in enumerate((frame1, frame2, frame3), start=1):
        tracks = tracker.update(frame)
        print(f"frame {i}: {[(t.track_id, t.label) for t in tracks]}")
