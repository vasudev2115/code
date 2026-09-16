"""Milestone 1c: Arm and take off to 10m. python takeoff.py"""
import asyncio
from connect import connect_drone

async def main():
    drone = await connect_drone()
    await drone.action.arm()
    await drone.action.set_takeoff_altitude(10.0)
    await drone.action.takeoff()
    async for position in drone.telemetry.position():
        print(f"altitude: {position.relative_altitude_m:.1f}m")
        if position.relative_altitude_m > 9.0:
            print("-- Reached target altitude")
            break

if __name__ == "__main__":
    asyncio.run(main())
