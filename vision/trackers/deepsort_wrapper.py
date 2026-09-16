"""
Optional DeepSORT tracker -- alternative to tracker.py's custom IoU
tracker or detect_webcam.py's --tracker bytetrack option.

DeepSORT adds appearance-based re-identification (a small neural net
that recognizes "this is the same person" even after they're briefly
occluded), which plain IoU/ByteTrack can't do. It's a meaningfully
heavier dependency (deep-sort-realtime + a small embedding model) for
a real accuracy benefit under occlusion.

NOT installed/verified here -- no network access to pip install
deep-sort-realtime in the environment this was written in. Written
correctly against that package's documented API; treat as untested
until you run it.

Install:
    pip install deep-sort-realtime

Usage: see integrate() below for how this would slot into detect_webcam.py.
"""

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
except ImportError:
    DEEPSORT_AVAILABLE = False


class DeepSortWrapper:
    def __init__(self, max_age: int = 30):
        if not DEEPSORT_AVAILABLE:
            raise RuntimeError(
                "deep-sort-realtime is not installed. Run `pip install deep-sort-realtime` first."
            )
        self.tracker = DeepSort(max_age=max_age)

    def update(self, detections: list[dict], frame):
        """detections: list of {"xyxy": (x1,y1,x2,y2), "confidence": float, "label": str}
        frame: the raw video frame (DeepSORT needs pixel data for its
        appearance embedding, unlike the plain IoU tracker).

        Returns ultralytics-independent track objects from deep-sort-realtime.
        """
        # deep-sort-realtime expects [[x1,y1,w,h], confidence, class_name]
        formatted = [
            ([d["xyxy"][0], d["xyxy"][1], d["xyxy"][2] - d["xyxy"][0], d["xyxy"][3] - d["xyxy"][1]],
             d["confidence"], d["label"])
            for d in detections
        ]
        return self.tracker.update_tracks(formatted, frame=frame)


def integrate_note():
    print(__doc__)
    print("\nTo actually use this in detect_webcam.py, you'd replace the SimpleTracker")
    print("import with DeepSortWrapper and pass each frame's raw pixels into update(),")
    print("since DeepSORT needs image data for its re-identification embeddings --")
    print("this is a real architectural difference from the IoU/ByteTrack options,")
    print("not just a drop-in swap.")


if __name__ == "__main__":
    if not DEEPSORT_AVAILABLE:
        print("deep-sort-realtime is not installed in this environment. Install with:")
        print("  pip install deep-sort-realtime")
    else:
        integrate_note()
