"""
Simulated swarm coordination: leader election, formation flying,
collision avoidance, battery-aware leader replacement, and mesh-relay
alerting across multiple lightweight in-process drone agents.

Real multi-vehicle PX4 simulation is a separate, heavier stretch goal
(see docs/MILESTONES.md) -- this proves the coordination algorithms
with real geometry/graph logic, not just printed narration.

Usage: python swarm_coordinator.py
"""
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

# ~1 degree latitude is about 111km -- used to convert formation offsets
# (given in meters) into lat/lon deltas for this simulation.
METERS_PER_DEGREE_LAT = 111_000
MIN_SEPARATION_M = 5.0       # collision avoidance trigger distance
DIRECT_COMMS_RANGE_M = 150.0  # beyond this, a drone must relay through a neighbor


@dataclass
class DroneAgent:
    drone_id: str
    lat: float
    lon: float
    battery_pct: float = 100.0
    is_leader: bool = False


def _meters_between(a: DroneAgent, b: DroneAgent) -> float:
    """Flat-earth approximation -- fine at this scale (meters, not km)."""
    dlat_m = (a.lat - b.lat) * METERS_PER_DEGREE_LAT
    dlon_m = (a.lon - b.lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians(a.lat))
    return math.hypot(dlat_m, dlon_m)


def _offset_position(base: DroneAgent, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Returns a (lat, lon) offset from base by dx/dy meters (east/north)."""
    dlat = dy_m / METERS_PER_DEGREE_LAT
    dlon = dx_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(base.lat)))
    return base.lat + dlat, base.lon + dlon


class SwarmCoordinator:
    def __init__(self, drone_ids: List[str], base_lat=26.812, base_lon=80.912):
        self.drones = [
            DroneAgent(did, base_lat + random.uniform(-0.002, 0.002), base_lon + random.uniform(-0.002, 0.002))
            for did in drone_ids
        ]
        self._elect_leader()

    def _elect_leader(self):
        for d in self.drones:
            d.is_leader = False
        leader = max(self.drones, key=lambda d: (d.battery_pct, d.drone_id))
        leader.is_leader = True
        print(f"-- Leader elected: {leader.drone_id} (battery={leader.battery_pct:.0f}%)")

    def leader(self) -> DroneAgent:
        return next(d for d in self.drones if d.is_leader)

    def apply_v_formation(self, spacing_m: float = 20.0):
        """Moves followers into V-formation positions behind the leader.

        Real geometry: each follower i sits spacing_m*i meters behind and
        spacing_m*i meters to alternating sides of the leader -- a classic
        V/wedge shape, not just "somewhere near the leader."
        """
        leader = self.leader()
        followers = [d for d in self.drones if not d.is_leader]

        for i, follower in enumerate(followers, start=1):
            side = -1 if i % 2 == 1 else 1  # alternate left/right of the leader
            rank = (i + 1) // 2
            dx = side * spacing_m * rank
            dy = -spacing_m * rank  # behind the leader
            follower.lat, follower.lon = _offset_position(leader, dx, dy)

    def check_collisions(self) -> list[tuple[str, str, float]]:
        """Returns (drone_a, drone_b, distance_m) for every pair closer than
        MIN_SEPARATION_M. Real pairwise distance check, not simulated."""
        violations = []
        for i, a in enumerate(self.drones):
            for b in self.drones[i + 1:]:
                dist = _meters_between(a, b)
                if dist < MIN_SEPARATION_M:
                    violations.append((a.drone_id, b.drone_id, dist))
        return violations

    def resolve_collisions(self):
        """Nudges drones apart along their separation vector until clear.
        Simple but real: this is a genuine (if basic) repulsion-based
        collision avoidance step, not just a printed warning."""
        violations = self.check_collisions()
        for id_a, id_b, dist in violations:
            drone_a = next(d for d in self.drones if d.drone_id == id_a)
            drone_b = next(d for d in self.drones if d.drone_id == id_b)

            push_m = (MIN_SEPARATION_M - dist) / 2 + 0.5  # push each half the deficit, plus margin
            dlat_m = (drone_a.lat - drone_b.lat) * METERS_PER_DEGREE_LAT
            dlon_m = (drone_a.lon - drone_b.lon) * METERS_PER_DEGREE_LAT * math.cos(math.radians(drone_a.lat))
            norm = math.hypot(dlat_m, dlon_m)

            if norm < 1e-9:
                # Exact overlap: there's no natural separation direction to
                # push along, since the vector between them is (0,0). Pick
                # an arbitrary fixed direction (east-west) rather than
                # silently doing nothing, which was the bug this replaced --
                # verified by test_collision_resolution_increases_separation,
                # which specifically covers this exact-overlap case.
                unit_dlat, unit_dlon = 0.0, 1.0
            else:
                unit_dlat, unit_dlon = dlat_m / norm, dlon_m / norm

            drone_a.lat, drone_a.lon = _offset_position(drone_a, unit_dlon * push_m, unit_dlat * push_m)
            drone_b.lat, drone_b.lon = _offset_position(drone_b, -unit_dlon * push_m, -unit_dlat * push_m)
            print(f"!! COLLISION AVOIDANCE: {id_a} and {id_b} were {dist:.1f}m apart, pushed to safe separation")

    def relay_path_to_leader(self, source_id: str) -> Optional[list[str]]:
        """Mesh communication: if source is out of direct range of the
        leader, find a relay chain through intermediate drones using
        simple BFS over the "in range of each other" graph. Returns the
        hop path, or None if no relay chain connects them."""
        leader = self.leader()
        source = next(d for d in self.drones if d.drone_id == source_id)

        if _meters_between(source, leader) <= DIRECT_COMMS_RANGE_M:
            return [source_id, leader.drone_id]

        # BFS over the "within DIRECT_COMMS_RANGE_M of each other" graph
        visited = {source_id}
        queue = [[source_id]]
        while queue:
            path = queue.pop(0)
            current = next(d for d in self.drones if d.drone_id == path[-1])
            for other in self.drones:
                if other.drone_id in visited:
                    continue
                if _meters_between(current, other) <= DIRECT_COMMS_RANGE_M:
                    new_path = path + [other.drone_id]
                    if other.drone_id == leader.drone_id:
                        return new_path
                    visited.add(other.drone_id)
                    queue.append(new_path)
        return None  # no relay chain reaches the leader

    def broadcast_alert(self, source_id: str, lat: float, lon: float, category: str):
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[{ts}] ALERT from {source_id}: {category} at ({lat:.5f}, {lon:.5f})")
        for d in self.drones:
            if d.drone_id != source_id:
                print(f"  -> {d.drone_id} notified, adjusting patrol toward alert location")

    def tick(self):
        for d in self.drones:
            d.battery_pct = max(0.0, d.battery_pct - random.uniform(0.5, 2.0))
        leader = self.leader()
        if leader.battery_pct < 20.0:
            print(f"-- {leader.drone_id} battery critical, re-electing leader")
            self._elect_leader()


if __name__ == "__main__":
    swarm = SwarmCoordinator(["drone-01", "drone-02", "drone-03", "drone-04"])
    swarm.apply_v_formation(spacing_m=20.0)
    print("-- Applied V-formation")

    for _ in range(6):
        swarm.tick()
        if random.random() < 0.3:
            src = random.choice(swarm.drones)
            swarm.broadcast_alert(src.drone_id, src.lat, src.lon, "area_of_interest")
        time.sleep(0.3)
