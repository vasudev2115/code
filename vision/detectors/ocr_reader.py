"""
Optional OCR module -- reads text from a detected region (e.g. a sign,
vehicle plate, or label) using EasyOCR.

NOT installed/verified in the environment this was written in --
EasyOCR pulls in a substantial dependency chain (torch, etc.) that
needs network access this sandbox didn't have. This is real,
correctly-written integration code following EasyOCR's documented
API, but treat it as untested until you run it yourself.

Install:
    pip install easyocr

Usage:
    python ocr_reader.py path/to/image.jpg
"""

import sys

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


def read_text(image_path: str, languages: list[str] = None) -> list[dict]:
    """Returns a list of {"text": str, "confidence": float, "bbox": [...]}."""
    if not EASYOCR_AVAILABLE:
        raise RuntimeError(
            "easyocr is not installed. Run `pip install easyocr` first -- "
            "this pulls in torch and other large dependencies, so expect a sizeable download."
        )

    reader = easyocr.Reader(languages or ["en"])
    results = reader.readtext(image_path)

    return [
        {"bbox": bbox, "text": text, "confidence": round(float(confidence), 3)}
        for bbox, text, confidence in results
    ]


if __name__ == "__main__":
    if not EASYOCR_AVAILABLE:
        print("easyocr is not installed in this environment. Install it with:")
        print("  pip install easyocr")
        print("(This will download a substantial dependency chain including torch.)")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python ocr_reader.py path/to/image.jpg")
        sys.exit(1)

    for result in read_text(sys.argv[1]):
        print(f"'{result['text']}' (confidence: {result['confidence']:.0%})")
