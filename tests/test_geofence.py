"""
Tests for geofence.py's point-in-polygon logic.
Run with: pytest tests/ (see test_hazard_rules.py header for the note
on why this environment verifies via __main__ instead).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.services.geofence import check_point, point_in_polygon, GeofenceZone  # noqa: E402

SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]  # 10x10 square


def test_point_clearly_inside():
    assert point_in_polygon((5.0, 5.0), SQUARE) is True


def test_point_clearly_outside():
    assert point_in_polygon((50.0, 50.0), SQUARE) is False


def test_point_outside_negative_coords():
    assert point_in_polygon((-5.0, -5.0), SQUARE) is False


def test_check_point_returns_correct_zone_name():
    zones = [GeofenceZone(name="Test Zone", polygon=SQUARE)]
    result = check_point(5.0, 5.0, zones)
    assert result is not None
    assert result.name == "Test Zone"


def test_check_point_returns_none_when_clear():
    zones = [GeofenceZone(name="Test Zone", polygon=SQUARE)]
    assert check_point(50.0, 50.0, zones) is None


def test_multiple_zones_checks_all():
    zone_a = GeofenceZone(name="A", polygon=[(0.0, 0.0), (0.0, 5.0), (5.0, 5.0), (5.0, 0.0)])
    zone_b = GeofenceZone(name="B", polygon=[(20.0, 20.0), (20.0, 25.0), (25.0, 25.0), (25.0, 20.0)])
    assert check_point(22.0, 22.0, [zone_a, zone_b]).name == "B"


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
