"""
Connect to a simulated PX4 drone via MAVSDK.

Prerequisites (on your own machine, not this sandbox):
    1. PX4 SITL + Gazebo running: `make px4_sitl gz_x500` inside PX4-Autopilot
    2. pip install mavsdk httpx

Usage:
    python connect.py
"""

import asyncio
from mavsdk import System


async def connect_drone(system_address: str = "udp://:14540") -> System:
    drone = System()
    await drone.connect(system_address=system_address)

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("-- Connected to drone!")
            break

    print("Waiting for global position + home position lock...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position and home position OK")
            break

    return drone


async def main():
    drone = await connect_drone()
    count = 0
    async for position in drone.telemetry.position():
        print(f"lat={position.latitude_deg:.6f} lon={position.longitude_deg:.6f} alt={position.relative_altitude_m:.1f}m")
        count += 1
        if count >= 5:
            break


if __name__ == "__main__":
    asyncio.run(main())
