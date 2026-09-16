"""
Simulated satellite connectivity: models real trade-offs (longer range,
higher latency, occasional dropout) vs. direct radio, without needing
real satellite hardware.

Usage: python satellite_link_sim.py
"""
import random
import time
from datetime import datetime, timezone

RADIO_RANGE_KM = 5.0
SATELLITE_LATENCY_S = (0.5, 2.5)
SATELLITE_DROPOUT_RATE = 0.03


def send_via_radio(distance_km: float, payload: dict) -> bool:
    if distance_km > RADIO_RANGE_KM:
        print(f"[radio] FAILED -- {distance_km:.1f}km exceeds radio range ({RADIO_RANGE_KM}km)")
        return False
    print(f"[radio] delivered instantly: {payload}")
    return True


def send_via_satellite(distance_km: float, payload: dict) -> bool:
    if random.random() < SATELLITE_DROPOUT_RATE:
        print("[satellite] dropped packet (simulated signal loss)")
        return False
    latency = random.uniform(*SATELLITE_LATENCY_S)
    time.sleep(latency)
    print(f"[satellite] delivered after {latency:.2f}s over {distance_km:.1f}km: {payload}")
    return True


def send(distance_km: float, payload: dict):
    if distance_km <= RADIO_RANGE_KM and send_via_radio(distance_km, payload):
        return
    send_via_satellite(distance_km, payload)


if __name__ == "__main__":
    for distance in [2, 4, 8, 15]:
        send(distance, {"type": "telemetry", "distance_km": distance,
                         "timestamp": datetime.now(timezone.utc).isoformat()})
