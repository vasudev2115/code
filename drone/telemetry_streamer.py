"""
Telemetry Streamer -- the other half of the GPS placeholder fix.

Continuously reads live position/battery from the connected drone and:
  1. Writes it to vision/telemetry_snapshot.json (via telemetry_snapshot.write_snapshot)
     so observation_engine.py's get_current_position() always has fresh data.
  2. Optionally POSTs each telemetry update to the backend's /telemetry
     endpoint, using the same non-blocking async-client pattern as
     observation_engine.py (reusable httpx.AsyncClient, checked status).

Run this alongside mission.py (or standalone) whenever you want vision/
to have real GPS instead of the fallback position.

Usage:
    python telemetry_streamer.py --backend http://localhost:8000
"""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "vision"))
from telemetry_snapshot import write_snapshot  # noqa: E402
from connect import connect_drone  # noqa: E402


async def stream_telemetry(drone, backend_url: str | None, timeout_s: float = 3.0):
    client = httpx.AsyncClient(timeout=timeout_s) if backend_url else None

    try:
        async for position in drone.telemetry.position():
            battery = None
            async for b in drone.telemetry.battery():
                battery = b.remaining_percent * 100
                break

            write_snapshot(
                lat=position.latitude_deg,
                lon=position.longitude_deg,
                altitude_m=position.relative_altitude_m,
                battery_pct=battery if battery is not None else 100.0,
            )

            if client:
                payload = {
                    "latitude": position.latitude_deg,
                    "longitude": position.longitude_deg,
                    "altitude_m": position.relative_altitude_m,
                    "battery_pct": battery if battery is not None else 100.0,
                }
                try:
                    response = await client.post(f"{backend_url}/telemetry", json=payload)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"!! Backend rejected telemetry: {e.response.status_code}")
                except httpx.RequestError as e:
                    print(f"!! Could not reach backend: {e}")

            await asyncio.sleep(0.5)  # ~2Hz, plenty for a demo
    finally:
        if client:
            await client.aclose()


async def main():
    parser = argparse.ArgumentParser(description="Stream live drone telemetry to snapshot + backend")
    parser.add_argument("--backend", default=None, help="Backend URL (omit to only write local snapshot)")
    args = parser.parse_args()

    drone = await connect_drone()
    print("-- Streaming telemetry. Ctrl+C to stop.")
    try:
        await stream_telemetry(drone, args.backend)
    except KeyboardInterrupt:
        print("\n-- Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
