"""Long-endurance power system simulation. Usage: python power_model.py"""
from dataclasses import dataclass
from enum import Enum


class FlightMode(Enum):
    HOVER = "hover"
    CRUISE = "cruise"
    CLIMB = "climb"


DRAIN_RATES = {FlightMode.HOVER: 1.4, FlightMode.CRUISE: 1.0, FlightMode.CLIMB: 2.2}


@dataclass
class PowerState:
    battery_pct: float
    solar_assist: bool = False

    def step(self, mode: FlightMode, minutes: float = 1.0):
        drain = DRAIN_RATES[mode] * minutes
        if self.solar_assist:
            drain *= 0.85
        self.battery_pct = max(0.0, self.battery_pct - drain)
        return self.battery_pct

    def estimated_remaining_minutes(self, mode: FlightMode) -> float:
        rate = DRAIN_RATES[mode] * (0.85 if self.solar_assist else 1.0)
        return round(self.battery_pct / rate, 1)


if __name__ == "__main__":
    state = PowerState(battery_pct=100.0)
    plan = [FlightMode.CLIMB] * 2 + [FlightMode.CRUISE] * 10 + [FlightMode.HOVER] * 3
    for minute, mode in enumerate(plan, start=1):
        pct = state.step(mode)
        print(f"t={minute:02d}min mode={mode.value:6s} battery={pct:.1f}%")
        if pct < 30 and mode != FlightMode.HOVER:
            print(f"  -> est. {state.estimated_remaining_minutes(FlightMode.CRUISE)} min left -- recommend return")
