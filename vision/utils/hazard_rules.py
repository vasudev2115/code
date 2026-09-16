"""
Hazard classification rules -- deliberately simple and transparent.

Per the code review: this file does NOT claim to be an explosive
classifier. It flags a small, explicit set of object categories as
"area of interest" when detection confidence is high, meaning
"worth a human looking at this," nothing more.

Kept as a separate module (not merged into YOLO or the API) so the
rule set stays easy to read, test, and explain in a viva -- every
decision here is one `if` statement you can point to.
"""

from vision.utils.config import INTEREST_CLASSES, HIGH_CONFIDENCE_THRESHOLD


def classify(object_class: str, confidence: float) -> str:
    """Return 'routine' or 'area_of_interest'. Nothing else, ever.

    This function must never return anything implying a confirmed
    hazard or explosive identification -- that determination is
    explicitly left to a trained human reviewer, per the project's
    own research-concept framing.
    """
    if object_class in INTEREST_CLASSES and confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "area_of_interest"
    return "routine"


# --- Simple self-tests, run directly with `python -m vision.utils.hazard_rules` ---
# Per the review: "add unit tests for routine vs. area_of_interest decisions."
def _run_self_tests():
    cases = [
        ("person", 0.90, "routine"),                # not in INTEREST_CLASSES
        ("backpack", 0.90, "area_of_interest"),      # in list, high confidence
        ("backpack", 0.50, "routine"),               # in list, but confidence too low
        ("suitcase", 0.75, "area_of_interest"),      # exactly at threshold
        ("car", 0.99, "routine"),                    # not in list, regardless of confidence
    ]
    passed = 0
    for obj_class, conf, expected in cases:
        actual = classify(obj_class, conf)
        ok = actual == expected
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}: classify({obj_class!r}, {conf}) = {actual!r} (expected {expected!r})")
    print(f"\n{passed}/{len(cases)} tests passed")


if __name__ == "__main__":
    _run_self_tests()
