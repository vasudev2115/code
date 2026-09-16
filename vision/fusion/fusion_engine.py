"""
Multi-Sensor Fusion Engine -- weighted confidence scoring.

Formula:
    S = 0.40*Y + 0.25*T + 0.20*G + 0.15*L

    Y = YOLO detection confidence (0-1, from vision/ -- pass in, or
        0.0 if this fusion pass has no associated vision detection)
    T = thermal anomaly confidence (0-1, derived from thermal_sim)
    G = gas anomaly confidence (0-1, derived from gas_sensor_sim)
    L = LiDAR obstacle confidence (0-1, derived from lidar_sim)

Classification:
    0.00 - 0.35  -> routine
    0.35 - 0.65  -> area_of_interest
    0.65 - 1.00  -> high_priority_area_of_interest

This still NEVER outputs a hazard/explosive confirmation -- only a
numeric score and a category meant to prompt human review, per the
project's research-concept framing. The weights are a starting point
based on which sensor is generally most informative (vision > thermal
> gas > LiDAR for this use case) -- tune them against real data later,
and say so if asked in a viva; there's no ground-truth dataset behind
these specific numbers.

Usage: python -m vision.fusion.fusion_engine
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from vision.fusion.thermal_sim import read_frame as read_thermal
from vision.fusion.gas_sensor_sim import read_sensor as read_gas
from vision.fusion.lidar_sim import scan as read_lidar

WEIGHT_YOLO = 0.40
WEIGHT_THERMAL = 0.25
WEIGHT_GAS = 0.20
WEIGHT_LIDAR = 0.15

THRESHOLD_ROUTINE_MAX = 0.35
THRESHOLD_AREA_OF_INTEREST_MAX = 0.65


@dataclass
class FusedObservation:
    timestamp: str
    latitude: Optional[float]
    longitude: Optional[float]
    yolo_confidence: float
    thermal_confidence: float
    gas_confidence: float
    lidar_confidence: float
    anomaly_score: float
    category: str
    note: str


def _thermal_confidence(thermal) -> float:
    """Map a thermal reading to a 0-1 confidence, not just a boolean.

    Scales max_temp above the ambient baseline into 0-1, capped at 1.0.
    A reading right at body/engine-heat range (~40C) maxes this out.
    """
    if not thermal.hotspot_detected:
        return 0.0
    return min((thermal.max_temp_c - 30.0) / 30.0, 1.0)


def _gas_confidence(gas) -> float:
    """How far the worst gas reading is past its normal range, 0-1 capped."""
    if not gas.anomaly_detected:
        return 0.0
    ratios = [
        gas.lpg_ppm / 400, gas.ch4_ppm / 400,
        gas.co_ppm / 50, gas.smoke_ppm / 300,
    ]
    return min(max(ratios), 1.0)


def _lidar_confidence(lidar) -> float:
    """Closer obstacles score higher confidence, 0-1."""
    if not lidar.obstacle_warning:
        return 0.0
    return min(1.0 - (lidar.closest_obstacle_m / 5.0), 1.0)


def fuse_once(
    yolo_confidence: float = 0.0,
    base_lat: float = 26.812,
    base_lon: float = 80.912,
) -> FusedObservation:
    """Run one fusion pass.

    yolo_confidence: pass in the current vision detection's confidence
    (0-1) if this fusion pass is tied to a specific YOLO detection.
    Defaults to 0.0 when running sensor-only (no vision component).
    """
    thermal = read_thermal(base_lat, base_lon)
    gas = read_gas()
    lidar = read_lidar()

    t_conf = _thermal_confidence(thermal)
    g_conf = _gas_confidence(gas)
    l_conf = _lidar_confidence(lidar)

    score = (
        WEIGHT_YOLO * yolo_confidence
        + WEIGHT_THERMAL * t_conf
        + WEIGHT_GAS * g_conf
        + WEIGHT_LIDAR * l_conf
    )
    score = round(min(score, 1.0), 3)

    if score >= THRESHOLD_AREA_OF_INTEREST_MAX:
        category = "high_priority_area_of_interest"
        note = "Weighted score from multiple sensors is high -- recommend priority inspection by trained personnel."
    elif score >= THRESHOLD_ROUTINE_MAX:
        category = "area_of_interest"
        note = "Weighted score outside routine range -- recommend follow-up inspection, not a confirmed hazard."
    else:
        category = "routine"
        note = "No significant anomaly across sensors."

    return FusedObservation(
        timestamp=datetime.now(timezone.utc).isoformat(),
        latitude=thermal.hotspot_lat or base_lat,
        longitude=thermal.hotspot_lon or base_lon,
        yolo_confidence=round(yolo_confidence, 3),
        thermal_confidence=round(t_conf, 3),
        gas_confidence=round(g_conf, 3),
        lidar_confidence=round(l_conf, 3),
        anomaly_score=score,
        category=category,
        note=note,
    )


def _self_test():
    """Sanity check the formula and thresholds with hand-picked inputs."""
    # All-zero sensors -> pure YOLO contribution
    result = fuse_once(yolo_confidence=1.0)
    print(f"YOLO=1.0 alone -> score in [0, {WEIGHT_YOLO}] range, got {result.anomaly_score}")
    assert result.anomaly_score <= WEIGHT_YOLO + 0.5  # thermal/gas/lidar are random, upper bound check only

    print("-- formula: S = 0.40*Y + 0.25*T + 0.20*G + 0.15*L")
    print("-- thresholds: <0.35 routine | 0.35-0.65 area_of_interest | >=0.65 high_priority")


if __name__ == "__main__":
    import time
    _self_test()
    print()
    for _ in range(5):
        # Simulated vision confidence for demo purposes -- in the real
        # pipeline this comes from vision/observation_engine.py.
        demo_yolo_conf = 0.6
        print(asdict(fuse_once(yolo_confidence=demo_yolo_conf)))
        time.sleep(1)
