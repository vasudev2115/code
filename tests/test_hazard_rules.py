"""
Pytest-style tests for hazard_rules.py.

Run with: pip install pytest && pytest tests/
(pytest isn't installed in the environment these were written in --
verified instead via the __main__ block at the bottom, which calls
the same test functions directly with plain asserts. If a function
here fails under pytest, it would have failed here too.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from vision.utils.hazard_rules import classify  # noqa: E402


def test_routine_object_not_in_interest_list():
    assert classify("person", 0.99) == "routine"


def test_interest_object_high_confidence_flagged():
    assert classify("backpack", 0.90) == "area_of_interest"


def test_interest_object_low_confidence_stays_routine():
    assert classify("backpack", 0.50) == "routine"


def test_threshold_boundary_is_inclusive():
    # HIGH_CONFIDENCE_THRESHOLD is 0.75 -- exactly at it should flag.
    assert classify("suitcase", 0.75) == "area_of_interest"


def test_just_below_threshold_stays_routine():
    assert classify("suitcase", 0.749) == "routine"


def test_never_returns_explosive_confirmation():
    """Regression guard: this function must NEVER return anything other
    than 'routine' or 'area_of_interest', regardless of input."""
    for obj_class in ["backpack", "suitcase", "handbag", "person", "car", "bomb", "explosive"]:
        for conf in [0.0, 0.5, 0.75, 0.99, 1.0]:
            result = classify(obj_class, conf)
            assert result in ("routine", "area_of_interest"), (
                f"classify({obj_class!r}, {conf}) returned {result!r} -- "
                f"must only ever be 'routine' or 'area_of_interest'"
            )


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
