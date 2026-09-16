"""Simulated LiDAR obstacle scan. Synthetic ranging data, no real hardware.

Usage: python lidar_sim.py
"""
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

NUM_BEAMS = 36
MAX_RANGE_M = 40.0
OBSTACLE_WARNING_M = 5.0


@dataclass
class LidarScan:
    timestamp: str
    closest_obstacle_m: float
    closest_obstacle_angle_deg: float
    obstacle_warning: bool


def scan() -> LidarScan:
    distances = [
        round(random.uniform(1.0, OBSTACLE_WARNING_M), 2) if random.random() < 0.05
        else round(random.uniform(OBSTACLE_WARNING_M, MAX_RANGE_M), 2)
        for _ in range(NUM_BEAMS)
    ]
    closest = min(distances)
    idx = distances.index(closest)
    return LidarScan(
        datetime.now(timezone.utc).isoformat(), closest,
        idx * (360 / NUM_BEAMS), closest < OBSTACLE_WARNING_M,
    )


if __name__ == "__main__":
    for _ in range(5):
        r = scan()
        flag = "!! WARNING" if r.obstacle_warning else ""
        print(f"[{r.timestamp}] closest={r.closest_obstacle_m}m @ {r.closest_obstacle_angle_deg:.0f}deg {flag}")
        time.sleep(1)
