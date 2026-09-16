"""Milestone 1b: Arm the drone (motors spin up, no takeoff). python arm.py"""
import asyncio
from connect import connect_drone

async def main():
    drone = await connect_drone()
    print("-- Arming")
    await drone.action.arm()
    async for is_armed in drone.telemetry.armed():
        print(f"Armed: {is_armed}")
        break
    await asyncio.sleep(2)
    print("-- Disarming")
    await drone.action.disarm()

if __name__ == "__main__":
    asyncio.run(main())
