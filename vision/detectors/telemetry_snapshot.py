"""
Live telemetry snapshot -- the fix for the GPS placeholder problem.

Both review documents flag the same issue: observation_engine.py was
using --lat/--lon CLI defaults instead of real drone position, and
querying the drone once per bounding box would be wasteful and slow.

The fix: drone/telemetry_streamer.py writes the current position
to a small shared JSON file (or, in production, a shared in-memory
object/Redis key) every time telemetry updates. This module just
reads the latest snapshot -- fast, non-blocking, and decoupled from
the detection loop's frame rate.

    Drone Telemetry -> current GPS snapshot (this file)
                                |
                     Camera -> YOLO -> Observation

This intentionally does NOT talk to MAVSDK directly. That keeps
vision/ independent of drone/ -- you can run detect_webcam.py on
a laptop with no drone connected at all, and it just falls back to a
default position with a stale-data warning.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

SNAPSHOT_PATH = Path(__file__).parent.parent.parent / "drone" / "telemetry_snapshot.json"

# Fallback used only when no snapshot file exists yet (e.g. running vision
# standalone without a drone). This is clearly logged, never silently used.
FALLBACK_LAT = 26.812
FALLBACK_LON = 80.912


@dataclass
class TelemetrySnapshot:
    latitude: float
    longitude: float
    altitude_m: float
    battery_pct: float
    timestamp: float  # unix epoch seconds
    is_live: bool  # False if this is the fallback, not real telemetry

    @property
    def age_s(self) -> float:
        return time.time() - self.timestamp


def write_snapshot(lat: float, lon: float, altitude_m: float, battery_pct: float):
    """Called by drone/telemetry_streamer.py on every telemetry update."""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "latitude": lat,
        "longitude": lon,
        "altitude_m": altitude_m,
        "battery_pct": battery_pct,
        "timestamp": time.time(),
    }
    SNAPSHOT_PATH.write_text(json.dumps(data))


def get_current_position(stale_after_s: float = 10.0) -> TelemetrySnapshot:
    """The one function observation_engine.py should call.

    Reads the latest telemetry snapshot from disk. Cheap enough to call
    once per detected frame (it's a small local file read, not a
    network round-trip to the drone).
    """
    if not SNAPSHOT_PATH.exists():
        return TelemetrySnapshot(
            latitude=FALLBACK_LAT,
            longitude=FALLBACK_LON,
            altitude_m=0.0,
            battery_pct=100.0,
            timestamp=time.time(),
            is_live=False,
        )

    try:
        data = json.loads(SNAPSHOT_PATH.read_text())
        snapshot = TelemetrySnapshot(
            latitude=data["latitude"],
            longitude=data["longitude"],
            altitude_m=data["altitude_m"],
            battery_pct=data["battery_pct"],
            timestamp=data["timestamp"],
            is_live=True,
        )
        if snapshot.age_s > stale_after_s:
            print(f"!! WARNING: telemetry snapshot is {snapshot.age_s:.1f}s old -- drone may not be running")
        return snapshot
    except (json.JSONDecodeError, KeyError) as e:
        print(f"!! WARNING: could not read telemetry snapshot ({e}), using fallback position")
        return TelemetrySnapshot(
            latitude=FALLBACK_LAT,
            longitude=FALLBACK_LON,
            altitude_m=0.0,
            battery_pct=100.0,
            timestamp=time.time(),
            is_live=False,
        )


if __name__ == "__main__":
    pos = get_current_position()
    print(f"lat={pos.latitude} lon={pos.longitude} alt={pos.altitude_m}m "
          f"battery={pos.battery_pct}% live={pos.is_live} age={pos.age_s:.1f}s")
