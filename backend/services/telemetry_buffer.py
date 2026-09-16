"""
Live telemetry buffering -- Redis when available, in-memory otherwise.

Why buffer telemetry separately from the main SQLite/Postgres table:
telemetry can arrive many times per second during a real flight, and
writing every single point straight to a relational DB doesn't scale
well. A fast in-memory ring buffer (Redis, or this fallback) holds the
last N points for "what's happening right now" queries (e.g. the
dashboard's live graphs), while the DB keeps the full historical
record for post-mission analysis.

`redis` isn't installed in the environment this was written in (no
network to pip install it), so this ships with a real, working
in-memory fallback -- not a stub -- and automatically prefers Redis
if it's available on your machine. The fallback has the exact same
interface, so nothing else needs to change based on which backend is
active.

Usage:
    from telemetry_buffer import TelemetryBuffer
    buffer = TelemetryBuffer(max_points=200)
    buffer.push({"lat": 26.8, "lon": 80.9, "battery_pct": 91})
    recent = buffer.recent(50)
"""

import json
import time
from collections import deque
from typing import Optional

try:
    import redis as redis_module
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class InMemoryBackend:
    """Fallback when Redis isn't installed/reachable. Same interface as
    the Redis-backed path -- a ring buffer capped at max_points."""

    def __init__(self, max_points: int):
        self._buffer: deque = deque(maxlen=max_points)

    def push(self, point: dict):
        self._buffer.append({**point, "_buffered_at": time.time()})

    def recent(self, n: int) -> list[dict]:
        return list(self._buffer)[-n:]

    def clear(self):
        self._buffer.clear()


class RedisBackend:
    """Real Redis-backed ring buffer using a capped Redis LIST.

    NOTE: this class is written correctly against the redis-py API but
    could not be executed in the environment this was built in --
    `redis` isn't installed there (no network access), and there's no
    Redis server running either. Test this specifically once you have
    both installed: `pip install redis` and a local `redis-server`.
    """

    def __init__(self, max_points: int, redis_url: str = "redis://localhost:6379/0", key: str = "aegisnet:telemetry"):
        self.client = redis_module.from_url(redis_url)
        self.max_points = max_points
        self.key = key

    def push(self, point: dict):
        payload = json.dumps({**point, "_buffered_at": time.time()})
        pipe = self.client.pipeline()
        pipe.rpush(self.key, payload)
        pipe.ltrim(self.key, -self.max_points, -1)  # keep only the most recent max_points
        pipe.execute()

    def recent(self, n: int) -> list[dict]:
        raw = self.client.lrange(self.key, -n, -1)
        return [json.loads(item) for item in raw]

    def clear(self):
        self.client.delete(self.key)


class TelemetryBuffer:
    """Public interface -- picks Redis if available and reachable, else
    falls back to the in-memory backend. Same interface either way."""

    def __init__(self, max_points: int = 200, redis_url: Optional[str] = None):
        self.backend = None
        if REDIS_AVAILABLE and redis_url:
            try:
                candidate = RedisBackend(max_points, redis_url)
                candidate.client.ping()  # fail fast if Redis isn't actually reachable
                self.backend = candidate
                self.using_redis = True
            except Exception:
                self.backend = None

        if self.backend is None:
            self.backend = InMemoryBackend(max_points)
            self.using_redis = False

    def push(self, point: dict):
        self.backend.push(point)

    def recent(self, n: int = 50) -> list[dict]:
        return self.backend.recent(n)

    def clear(self):
        self.backend.clear()


def _self_test():
    """Verifies the in-memory fallback path -- the one actually runnable here."""
    buffer = TelemetryBuffer(max_points=5)  # no redis_url given -> forces in-memory
    assert buffer.using_redis is False, "expected in-memory fallback when no redis_url given"

    for i in range(10):
        buffer.push({"seq": i, "battery_pct": 100 - i})

    recent = buffer.recent(3)
    assert len(recent) == 3, f"expected 3 recent points, got {len(recent)}"
    assert [p["seq"] for p in recent] == [7, 8, 9], (
        f"expected the 3 most recent (seq 7,8,9), got {[p['seq'] for p in recent]}"
    )
    print("PASS: in-memory buffer keeps only the most recent points, correctly ordered")

    all_points = buffer.recent(100)
    assert len(all_points) == 5, f"max_points=5 should cap storage at 5, got {len(all_points)}"
    print("PASS: buffer correctly caps at max_points even though 10 pushes were made")

    buffer.clear()
    assert buffer.recent(10) == [], "buffer should be empty after clear()"
    print("PASS: clear() empties the buffer")

    print(f"\nREDIS_AVAILABLE in this environment: {REDIS_AVAILABLE} "
          f"(RedisBackend class is written but unverified without a real redis-py install + server)")


if __name__ == "__main__":
    _self_test()
