"""Simulated MQ-2/MQ-135 style gas sensor. Synthetic PPM data, no real hardware.

Usage: python gas_sensor_sim.py
"""
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

NORMAL = {"lpg_ppm": (0, 50), "ch4_ppm": (0, 50), "co_ppm": (0, 9), "smoke_ppm": (0, 50)}
ALERT = {"lpg_ppm": 400, "ch4_ppm": 400, "co_ppm": 50, "smoke_ppm": 300}


@dataclass
class GasReading:
    timestamp: str
    lpg_ppm: float
    ch4_ppm: float
    co_ppm: float
    smoke_ppm: float
    anomaly_detected: bool


def read_sensor() -> GasReading:
    anomaly = random.random() < 0.08
    values = {}
    for gas, (lo, hi) in NORMAL.items():
        values[gas] = round(random.uniform(hi, ALERT[gas] * 1.3), 1) if anomaly else round(random.uniform(lo, hi), 1)
    return GasReading(datetime.now(timezone.utc).isoformat(), anomaly_detected=anomaly, **values)


if __name__ == "__main__":
    for _ in range(5):
        r = read_sensor()
        print(asdict(r))
        time.sleep(1)
