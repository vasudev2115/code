"""Milestone 1d: Land wherever the drone currently is. python land.py"""
import asyncio
from connect import connect_drone

async def main():
    drone = await connect_drone()
    print("-- Landing")
    await drone.action.land()
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("-- Landed and disarmed")
            break

if __name__ == "__main__":
    asyncio.run(main())
