"""Modular payload registry. Usage: python payload_registry.py"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class Payload:
    name: str
    category: str
    description: str
    enabled: bool = True


DEFAULT_PAYLOADS: Dict[str, Payload] = {
    "rgb_camera": Payload("rgb_camera", "vision", "Standard RGB camera for YOLO object detection"),
    "thermal_camera": Payload("thermal_camera", "thermal", "Simulated thermal/heat-signature sensor"),
    "gas_sensor": Payload("gas_sensor", "gas", "Simulated MQ-2/MQ-135 gas sensor"),
    "lidar": Payload("lidar", "lidar", "Simulated LiDAR for terrain/obstacle scanning"),
    "satcom": Payload("satcom", "comms", "Simulated satellite uplink", enabled=False),
}


class PayloadRegistry:
    def __init__(self, payloads=None):
        self.payloads = payloads or dict(DEFAULT_PAYLOADS)

    def enable(self, name):
        if name in self.payloads:
            self.payloads[name].enabled = True

    def disable(self, name):
        if name in self.payloads:
            self.payloads[name].enabled = False

    def active(self):
        return [p for p in self.payloads.values() if p.enabled]

    def summary(self):
        for p in self.payloads.values():
            status = "ON " if p.enabled else "OFF"
            print(f"[{status}] {p.name:15s} ({p.category:8s}) - {p.description}")


if __name__ == "__main__":
    registry = PayloadRegistry()
    print("-- Default mission loadout:")
    registry.summary()
    print("\n-- Enabling satcom for a long-range mission:")
    registry.enable("satcom")
    registry.summary()
