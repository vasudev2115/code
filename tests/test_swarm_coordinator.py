"""Tests for swarm_coordinator.py's formation flying, collision avoidance,
and mesh-relay logic -- the actual geometry/graph algorithms, not just
whether the file runs without crashing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "swarm"))
from swarm_coordinator import SwarmCoordinator, _meters_between, MIN_SEPARATION_M, DIRECT_COMMS_RANGE_M  # noqa: E402


def test_v_formation_followers_are_behind_leader():
    swarm = SwarmCoordinator(["leader", "f1", "f2", "f3"])
    for d in swarm.drones:
        d.is_leader = (d.drone_id == "leader")
    swarm.apply_v_formation(spacing_m=20.0)

    leader = swarm.leader()
    followers = [d for d in swarm.drones if not d.is_leader]

    for f in followers:
        # "Behind" means south of the leader in this sim's convention (dy negative).
        assert f.lat < leader.lat, f"{f.drone_id} should be behind (south of) the leader"


def test_v_formation_spacing_is_reasonable():
    swarm = SwarmCoordinator(["leader", "f1"])
    for d in swarm.drones:
        d.is_leader = (d.drone_id == "leader")
    swarm.apply_v_formation(spacing_m=20.0)

    leader = swarm.leader()
    follower = next(d for d in swarm.drones if not d.is_leader)
    dist = _meters_between(leader, follower)
    # rank 1, spacing 20m in both x and y -> distance should be roughly sqrt(20^2+20^2) =~ 28m
    assert 20 < dist < 35, f"expected ~28m separation for rank-1 V-formation, got {dist:.1f}m"


def test_collision_detection_finds_close_pair():
    swarm = SwarmCoordinator(["a", "b"])
    # Force them very close together (same position)
    swarm.drones[1].lat = swarm.drones[0].lat
    swarm.drones[1].lon = swarm.drones[0].lon

    violations = swarm.check_collisions()
    assert len(violations) == 1
    assert violations[0][2] < MIN_SEPARATION_M


def test_collision_resolution_increases_separation():
    swarm = SwarmCoordinator(["a", "b"])
    swarm.drones[1].lat = swarm.drones[0].lat
    swarm.drones[1].lon = swarm.drones[0].lon

    dist_before = _meters_between(swarm.drones[0], swarm.drones[1])
    swarm.resolve_collisions()
    dist_after = _meters_between(swarm.drones[0], swarm.drones[1])

    assert dist_after > dist_before, "collision resolution should increase separation"
    assert dist_after >= MIN_SEPARATION_M, f"expected safe separation after resolving, got {dist_after:.1f}m"


def test_no_collision_when_already_separated():
    swarm = SwarmCoordinator(["a", "b"])
    # Force them far apart (well beyond MIN_SEPARATION_M)
    swarm.drones[1].lat = swarm.drones[0].lat + 0.01  # ~1.1km
    violations = swarm.check_collisions()
    assert violations == []


def test_relay_direct_when_in_range():
    swarm = SwarmCoordinator(["leader", "nearby"])
    for d in swarm.drones:
        d.is_leader = (d.drone_id == "leader")
    # Force "nearby" within direct range
    swarm.drones[1].lat = swarm.drones[0].lat
    swarm.drones[1].lon = swarm.drones[0].lon

    path = swarm.relay_path_to_leader("nearby")
    assert path == ["nearby", "leader"], f"expected direct 2-hop path, got {path}"


def test_relay_multi_hop_when_out_of_direct_range():
    swarm = SwarmCoordinator(["leader", "relay", "far"])
    for d in swarm.drones:
        d.is_leader = (d.drone_id == "leader")

    leader = next(d for d in swarm.drones if d.drone_id == "leader")
    relay = next(d for d in swarm.drones if d.drone_id == "relay")
    far = next(d for d in swarm.drones if d.drone_id == "far")

    # leader and relay close together; far is out of range of leader but in range of relay
    relay.lat, relay.lon = leader.lat, leader.lon
    far_offset_deg = (DIRECT_COMMS_RANGE_M * 0.7) / 111_000  # within range of relay, not leader directly
    far.lat = leader.lat + (DIRECT_COMMS_RANGE_M * 1.5) / 111_000  # out of leader's direct range
    far.lon = leader.lon
    relay.lat = leader.lat + far_offset_deg  # relay sits between leader and far

    path = swarm.relay_path_to_leader("far")
    assert path is not None, "expected a relay path to exist"
    assert path[0] == "far" and path[-1] == "leader"
    assert len(path) >= 2


def test_relay_returns_none_when_unreachable():
    swarm = SwarmCoordinator(["leader", "isolated"])
    for d in swarm.drones:
        d.is_leader = (d.drone_id == "leader")
    leader = next(d for d in swarm.drones if d.drone_id == "leader")
    isolated = next(d for d in swarm.drones if d.drone_id == "isolated")
    isolated.lat = leader.lat + (DIRECT_COMMS_RANGE_M * 10) / 111_000  # way out of any range

    path = swarm.relay_path_to_leader("isolated")
    assert path is None, "expected no relay path when nothing is in range"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__} -- {e}")
    print(f"\n{passed}/{len(tests)} passed")
