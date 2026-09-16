"""
Mission Controller -- the central controller the roadmap calls for.

Now does two-way sync with the backend:
  1. Every internal state change is pushed to the backend via
     POST /missions/{id}/transition, so the dashboard's Mission Control
     panel reflects the ACTUAL live flight, not just whatever was last
     clicked manually.
  2. A background task polls GET /missions/{id} for a remote abort --
     if someone clicks "Abort" on the dashboard, this picks it up and
     triggers the same abort_event the battery failsafe uses, so a
     live flight can actually be interrupted from the UI.

State sync is fire-and-forget (background tasks, not awaited inline) --
per the same non-blocking principle applied to observation_engine.py:
a slow/unreachable backend should never stall actual flight control
calls. If the backend is down, the mission still flies; it just won't
show up live on the dashboard.

State machine (per roadmap Phase 5):
    IDLE -> ARMED -> TAKEOFF -> MISSION -> OBSERVATION -> RETURN -> LAND -> COMPLETE
                                     |
                                     v (failsafe trigger, local OR remote abort)
                                  RETURN

Usage:
    python mission.py                                  # single default waypoint, no backend sync
    python mission.py --mission-id 3                    # fly uploaded waypoints, synced to dashboard
    python mission.py --mission-id 3 --backend http://localhost:8000
"""

import argparse
import asyncio
from enum import Enum

import httpx

from connect import connect_drone
from telemetry_snapshot_bridge import write_snapshot

LOW_BATTERY_THRESHOLD = 0.30
WAYPOINT_HOLD_S = 20
TAKEOFF_ALTITUDE_M = 10.0
DEFAULT_BACKEND = "http://localhost:8000"
REMOTE_ABORT_POLL_S = 2.0


class MissionState(Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    TAKEOFF = "TAKEOFF"
    MISSION = "MISSION"
    OBSERVATION = "OBSERVATION"
    RETURN = "RETURN"
    LAND = "LAND"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


async def fetch_waypoints(backend_url: str, mission_id: int) -> list[dict]:
    """Pulls the uploaded waypoint list from the backend, ordered by seq."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{backend_url}/missions/{mission_id}/waypoints")
        response.raise_for_status()
        return response.json()


class MissionController:
    def __init__(
        self,
        drone,
        waypoints: list[dict] | None = None,
        mission_id: int | None = None,
        backend_url: str = DEFAULT_BACKEND,
    ):
        self.drone = drone
        self.state = MissionState.IDLE
        self.abort_event = asyncio.Event()
        self.waypoints = waypoints or []
        self.mission_id = mission_id
        self.backend_url = backend_url.rstrip("/")
        self._sync_client = httpx.AsyncClient(timeout=3.0) if mission_id is not None else None
        self._background_syncs: set[asyncio.Task] = set()

    def _sync_state_to_backend(self, new_state: MissionState):
        """Fire-and-forget POST -- never blocks flight logic on network I/O."""
        if self._sync_client is None:
            return  # no --mission-id given, nothing to sync

        async def _post():
            try:
                response = await self._sync_client.post(
                    f"{self.backend_url}/missions/{self.mission_id}/transition",
                    json={"state": new_state.value},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Most likely an illegal transition per the backend's own
                # VALID_TRANSITIONS table -- surfacing this matters, since
                # it means our local state machine and the backend's have
                # disagreed about what's legal.
                print(f"!! Backend rejected state sync to {new_state.value}: {e.response.text}")
            except httpx.RequestError as e:
                print(f"!! Could not sync state to backend ({e}) -- flight continues regardless")

        task = asyncio.create_task(_post())
        self._background_syncs.add(task)
        task.add_done_callback(self._background_syncs.discard)

    def _set_state(self, new_state: MissionState):
        print(f"-- Mission state: {self.state.value} -> {new_state.value}")
        self.state = new_state
        self._sync_state_to_backend(new_state)

    async def _monitor_battery(self):
        """Local failsafe: watches battery, triggers abort on low charge."""
        async for battery in self.drone.telemetry.battery():
            if battery.remaining_percent < LOW_BATTERY_THRESHOLD and self.state not in (
                MissionState.RETURN, MissionState.LAND, MissionState.COMPLETE, MissionState.ABORTED,
            ):
                print(f"!! FAILSAFE: battery at {battery.remaining_percent:.0%}, aborting mission")
                self.abort_event.set()
                return

    async def _poll_remote_abort(self):
        """Watches the backend for a remote abort (e.g. dashboard 'Abort' button).

        Only runs when --mission-id was given. Polling rather than a
        push channel keeps this simple -- a WebSocket-based command
        channel would be lower-latency but is a bigger change for a
        marginal responsiveness gain on a 2-second poll interval.
        """
        if self.mission_id is None:
            return

        async with httpx.AsyncClient(timeout=3.0) as client:
            while self.state not in (MissionState.COMPLETE, MissionState.ABORTED):
                try:
                    response = await client.get(f"{self.backend_url}/missions")
                    response.raise_for_status()
                    missions = response.json()
                    mine = next((m for m in missions if m["id"] == self.mission_id), None)
                    if mine and mine["state"] == "ABORTED" and self.state != MissionState.ABORTED:
                        print("!! REMOTE ABORT: dashboard requested mission abort")
                        self.abort_event.set()
                        return
                except httpx.RequestError:
                    pass  # backend unreachable, just keep flying and try again next poll

                await asyncio.sleep(REMOTE_ABORT_POLL_S)

    async def _stream_telemetry(self):
        async for position in self.drone.telemetry.position():
            write_snapshot(
                lat=position.latitude_deg,
                lon=position.longitude_deg,
                altitude_m=position.relative_altitude_m,
                battery_pct=100.0,
            )
            if self.state in (MissionState.COMPLETE, MissionState.ABORTED):
                return
            await asyncio.sleep(0.5)

    async def _fly_waypoint(self, wp: dict) -> bool:
        """Fly to one waypoint, hold for its hover_s. Returns False if aborted mid-flight."""
        print(f"-- Flying to lat={wp['latitude']:.6f}, lon={wp['longitude']:.6f}, alt={wp['altitude_m']}m")
        await self.drone.action.goto_location(wp["latitude"], wp["longitude"], wp["altitude_m"], 0.0)

        hold_s = max(wp.get("hover_s", 0), 3)
        try:
            await asyncio.wait_for(self.abort_event.wait(), timeout=hold_s)
            print("-- Aborting early due to failsafe/remote-abort trigger")
            return False
        except asyncio.TimeoutError:
            return True

    async def run(self):
        battery_task = asyncio.create_task(self._monitor_battery())
        telemetry_task = asyncio.create_task(self._stream_telemetry())
        abort_poll_task = asyncio.create_task(self._poll_remote_abort())

        try:
            self._set_state(MissionState.ARMED)
            await self.drone.action.arm()

            self._set_state(MissionState.TAKEOFF)
            await self.drone.action.set_takeoff_altitude(TAKEOFF_ALTITUDE_M)
            await self.drone.action.takeoff()
            await asyncio.sleep(8)

            self._set_state(MissionState.MISSION)

            aborted_mid_flight = False
            if self.waypoints:
                print(f"-- Flying {len(self.waypoints)} uploaded waypoint(s)")
                for wp in self.waypoints:
                    ok = await self._fly_waypoint(wp)
                    if not ok:
                        aborted_mid_flight = True
                        break
            else:
                async for position in self.drone.telemetry.position():
                    home_lat, home_lon = position.latitude_deg, position.longitude_deg
                    break
                ok = await self._fly_waypoint({
                    "latitude": home_lat + 0.0009,
                    "longitude": home_lon,
                    "altitude_m": TAKEOFF_ALTITUDE_M,
                    "hover_s": WAYPOINT_HOLD_S,
                })
                aborted_mid_flight = not ok

            if not aborted_mid_flight:
                self._set_state(MissionState.OBSERVATION)
                await asyncio.sleep(2)

            self._set_state(MissionState.RETURN)
            await self.drone.action.return_to_launch()

            self._set_state(MissionState.LAND)
            async for in_air in self.drone.telemetry.in_air():
                if not in_air:
                    break

            self._set_state(MissionState.ABORTED if aborted_mid_flight else MissionState.COMPLETE)

        except Exception as e:
            print(f"!! Mission error: {e}")
            self._set_state(MissionState.ABORTED)
            raise
        finally:
            battery_task.cancel()
            telemetry_task.cancel()
            abort_poll_task.cancel()
            if self._background_syncs:
                await asyncio.gather(*self._background_syncs, return_exceptions=True)
            if self._sync_client:
                await self._sync_client.aclose()


async def main():
    parser = argparse.ArgumentParser(description="AEGISNET mission controller")
    parser.add_argument("--mission-id", type=int, default=None,
                         help="Fetch and fly waypoints uploaded via the Mission Planner, syncing state live")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="Backend URL")
    args = parser.parse_args()

    waypoints = []
    if args.mission_id is not None:
        print(f"-- Fetching waypoints for mission #{args.mission_id} from {args.backend}")
        try:
            waypoints = await fetch_waypoints(args.backend, args.mission_id)
            if not waypoints:
                print("!! No waypoints found for that mission ID, falling back to default single waypoint")
        except httpx.HTTPError as e:
            print(f"!! Could not fetch waypoints ({e}), falling back to default single waypoint")

    drone = await connect_drone()
    controller = MissionController(drone, waypoints=waypoints, mission_id=args.mission_id, backend_url=args.backend)
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
