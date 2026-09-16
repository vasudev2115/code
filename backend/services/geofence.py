"""
Geofencing -- restricted "red zones" that the mission planner and live
telemetry both respect.

Uses standard ray-casting point-in-polygon: draw a ray from the point
to infinity and count how many polygon edges it crosses. Odd count =
inside, even = outside. This is a well-known, correct algorithm (not
a simulated stand-in like the sensor modules) -- it's genuinely how
you'd check this in production GIS code.

Zones are simple lat/lon polygons for now. Add your own or load from
a config file/database later; this keeps it simple to demo and edit.
"""

from dataclasses import dataclass
from typing import List, Tuple

Point = Tuple[float, float]  # (lat, lon)


@dataclass
class GeofenceZone:
    name: str
    polygon: List[Point]  # ordered vertices, lat/lon pairs


# Example restricted zones near the project's default demo coordinates
# (26.812, 80.912). Replace with real coordinates for your demo site.
DEFAULT_ZONES: List[GeofenceZone] = [
    GeofenceZone(
        name="Restricted Zone Alpha",
        polygon=[
            (26.8140, 80.9110),
            (26.8140, 80.9130),
            (26.8155, 80.9130),
            (26.8155, 80.9110),
        ],
    ),
]


def point_in_polygon(point: Point, polygon: List[Point]) -> bool:
    """Ray-casting algorithm. point and polygon vertices are (lat, lon)."""
    x, y = point[1], point[0]  # treat lon as x, lat as y for standard geometry
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0][1], polygon[0][0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n][1], polygon[i % n][0]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        x_intersect = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= x_intersect:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def check_point(lat: float, lon: float, zones: List[GeofenceZone] = None) -> GeofenceZone | None:
    """Returns the first zone this point falls inside, or None if clear."""
    zones = zones if zones is not None else DEFAULT_ZONES
    for zone in zones:
        if point_in_polygon((lat, lon), zone.polygon):
            return zone
    return None


if __name__ == "__main__":
    # Self-test: one point clearly inside the example zone, one clearly outside.
    inside_point = (26.8147, 80.9120)   # center of Restricted Zone Alpha
    outside_point = (26.8000, 80.9000)  # well outside

    result_inside = check_point(*inside_point)
    result_outside = check_point(*outside_point)

    print(f"inside_point -> {result_inside.name if result_inside else 'clear'} "
          f"({'PASS' if result_inside else 'FAIL'})")
    print(f"outside_point -> {result_outside.name if result_outside else 'clear'} "
          f"({'PASS' if result_outside is None else 'FAIL'})")
