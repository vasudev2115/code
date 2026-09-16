"""Milestone 1e: Fly to a specific GPS waypoint. python goto.py"""
import asyncio
from connect import connect_drone

async def main():
    drone = await connect_drone()
    await drone.action.arm()
    await drone.action.set_takeoff_altitude(10.0)
    await drone.action.takeoff()
    await asyncio.sleep(8)
    async for position in drone.telemetry.position():
        home_lat, home_lon = position.latitude_deg, position.longitude_deg
        break
    target_lat = home_lat + 0.0009
    print(f"-- Flying to lat={target_lat}, lon={home_lon}")
    await drone.action.goto_location(target_lat, home_lon, 10.0, 0.0)
    async for position in drone.telemetry.position():
        dist = abs(position.latitude_deg - target_lat) + abs(position.longitude_deg - home_lon)
        if dist < 0.0001:
            print("-- Reached waypoint")
            break
    await drone.action.return_to_launch()

if __name__ == "__main__":
    asyncio.run(main())
