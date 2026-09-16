"""Tests for tracker.py's IoU matching logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from vision.trackers.tracker import SimpleTracker, _iou  # noqa: E402


def test_iou_identical_boxes_is_one():
    box = (100, 100, 200, 200)
    assert _iou(box, box) == 1.0


def test_iou_non_overlapping_is_zero():
    box_a = (0, 0, 10, 10)
    box_b = (100, 100, 110, 110)
    assert _iou(box_a, box_b) == 0.0


def test_same_object_keeps_same_id_across_frames():
    tracker = SimpleTracker()
    frame1 = [{"label": "person", "confidence": 0.9, "xyxy": (100, 100, 200, 300)}]
    frame2 = [{"label": "person", "confidence": 0.88, "xyxy": (105, 102, 205, 302)}]

    tracks1 = tracker.update(frame1)
    tracks2 = tracker.update(frame2)

    assert tracks1[0].track_id == tracks2[0].track_id


def test_new_object_gets_new_id():
    tracker = SimpleTracker()
    frame1 = [{"label": "person", "confidence": 0.9, "xyxy": (100, 100, 200, 300)}]
    frame2 = [
        {"label": "person", "confidence": 0.9, "xyxy": (100, 100, 200, 300)},
        {"label": "backpack", "confidence": 0.7, "xyxy": (400, 400, 450, 480)},
    ]

    tracks1 = tracker.update(frame1)
    tracks2 = tracker.update(frame2)

    ids = {t.track_id for t in tracks2}
    assert len(ids) == 2
    assert tracks1[0].track_id in ids


def test_different_labels_at_same_position_dont_merge():
    """A person and a backpack at the exact same box shouldn't be treated as the same track."""
    tracker = SimpleTracker()
    frame1 = [{"label": "person", "confidence": 0.9, "xyxy": (100, 100, 200, 300)}]
    frame2 = [{"label": "backpack", "confidence": 0.9, "xyxy": (100, 100, 200, 300)}]

    tracks1 = tracker.update(frame1)
    tracks2 = tracker.update(frame2)

    assert tracks1[0].track_id != tracks2[0].track_id


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__} -- {e}")
    print(f"\n{passed}/{len(tests)} passed")
