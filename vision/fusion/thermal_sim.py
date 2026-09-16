"""Simulated thermal camera. Synthetic heat-signature data, no real hardware exists yet.

Usage: python thermal_sim.py
"""
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class ThermalReading:
    timestamp: str
    max_temp_c: float
    avg_temp_c: float
    hotspot_detected: bool
    hotspot_lat: float | None
    hotspot_lon: float | None


def read_frame(base_lat: float = 26.812, base_lon: float = 80.912) -> ThermalReading:
    ambient = random.uniform(18.0, 28.0)
    has_hotspot = random.random() < 0.15
    if has_hotspot:
        max_temp = random.uniform(34.0, 60.0)
        lat = base_lat + random.uniform(-0.001, 0.001)
        lon = base_lon + random.uniform(-0.001, 0.001)
    else:
        max_temp = ambient + random.uniform(0, 2)
        lat = lon = None
    return ThermalReading(
        datetime.now(timezone.utc).isoformat(), round(max_temp, 1), round(ambient, 1),
        has_hotspot, lat, lon,
    )


if __name__ == "__main__":
    for _ in range(5):
        r = read_frame()
        print(asdict(r))
        time.sleep(1)
