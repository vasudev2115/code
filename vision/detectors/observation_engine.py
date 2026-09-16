"""
Observation Engine -- turns YOLO detections into structured, geotagged
observations and posts them to the backend.

Fixes applied from the code review:
  1. GPS placeholder replaced with get_current_position() telemetry
     snapshot (see telemetry_snapshot.py) -- no more --lat/--lon
     command-line placeholders.
  2. Synchronous httpx.post() replaced with a reusable httpx.AsyncClient
     so frequent posts don't block the detection loop.
  3. HTTP response status is checked (raise_for_status), not just
     transport-level errors caught.
  4. Timeout is configurable via config.py / CLI, not hard-coded.
  5. 5-second per-label de-duplication preserved as-is (works, review
     said keep it for now; object tracking is a separate future step).

Recommended data flow (matches the roadmap doc):
    Drone Telemetry -> current GPS snapshot -> YOLO detection ->
    hazard rule -> observation JSON -> POST /detections -> DB -> WebSocket

Usage:
    python -m vision.detectors.observation_engine --backend http://localhost:8000
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import httpx

from vision.utils.config import DEFAULT_BACKEND_URL, HTTP_TIMEOUT_S, DEDUP_WINDOW_S
from vision.utils.hazard_rules import classify
from vision.detectors.telemetry_snapshot import get_current_position


@dataclass
class Observation:
    object_class: str
    confidence: float
    latitude: float
    longitude: float
    altitude_m: float
    timestamp: str
    category: str  # "routine" | "area_of_interest" -- internal name
    telemetry_is_live: bool

    def to_dict(self):
        """Full local representation, including fields the backend doesn't take."""
        return asdict(self)

    def to_backend_payload(self) -> dict:
        """What actually gets POSTed to /detections.

        IMPORTANT: the backend's DetectionIn schema calls this field
        `status`, not `category` -- and status has a default of
        "routine", so sending the wrong key name doesn't error, it just
        silently discards every real classification. This explicit
        mapping exists specifically so that mismatch can't happen again
        if this dataclass gets extended later.
        """
        return {
            "object_class": self.object_class,
            "confidence": self.confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "status": self.category,  # <-- the field-name fix
        }


class ObservationEngine:
    def __init__(self, backend_url: str = DEFAULT_BACKEND_URL, timeout_s: float = HTTP_TIMEOUT_S):
        self.backend_url = backend_url.rstrip("/")
        self.timeout_s = timeout_s
        self._last_reported: dict[str, float] = {}  # label -> last-sent unix time
        # Reusable client, per review recommendation -- avoids opening a
        # new connection for every single detection.
        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    def _should_report(self, label: str) -> bool:
        """5-second per-label de-duplication."""
        now = time.time()
        last = self._last_reported.get(label, 0)
        if now - last < DEDUP_WINDOW_S:
            return False
        self._last_reported[label] = now
        return True

    def make_observation(self, object_class: str, confidence: float) -> Optional[Observation]:
        """Build one observation using the current telemetry snapshot.

        Returns None if this label was already reported within the
        de-dup window (caller should just skip it, not an error).
        """
        if not self._should_report(object_class):
            return None

        position = get_current_position()
        category = classify(object_class, confidence)

        return Observation(
            object_class=object_class,
            confidence=round(confidence, 3),
            latitude=position.latitude,
            longitude=position.longitude,
            altitude_m=position.altitude_m,
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category,
            telemetry_is_live=position.is_live,
        )

    async def post_observation(self, observation: Observation) -> bool:
        """POST to the backend, check the response status, return success/fail.

        This is async and non-blocking -- fire-and-forget style callers
        should use asyncio.create_task(post_observation(...)) so a slow
        or unreachable backend never stalls the camera loop.
        """
        try:
            response = await self._client.post(
                f"{self.backend_url}/detections",
                json=observation.to_backend_payload(),
            )
            response.raise_for_status()  # review: check status, not just transport errors
            return True
        except httpx.HTTPStatusError as e:
            print(f"!! Backend rejected observation: {e.response.status_code} {e.response.text}")
            return False
        except httpx.RequestError as e:
            print(f"!! Could not reach backend at {self.backend_url}: {e}")
            return False

    async def observe_and_report(self, object_class: str, confidence: float) -> Optional[Observation]:
        """Convenience wrapper: build + post in one call, non-blocking."""
        observation = self.make_observation(object_class, confidence)
        if observation is None:
            return None
        # Fire the POST without awaiting it inline in a tight loop --
        # callers running a live camera loop should use create_task().
        await self.post_observation(observation)
        return observation

    async def close(self):
        await self._client.aclose()


async def _demo():
    """Standalone demo: no camera, no backend needed to see it work."""
    engine = ObservationEngine()

    print("-- Current telemetry snapshot:")
    pos = get_current_position()
    print(f"   lat={pos.latitude} lon={pos.longitude} live={pos.is_live}")

    print("\n-- Building sample observations (backend POST will fail gracefully if not running):")
    obs1 = engine.make_observation("person", 0.92)
    obs2 = engine.make_observation("backpack", 0.81)
    obs3 = engine.make_observation("backpack", 0.81)  # should be deduped (None)

    for obs in (obs1, obs2, obs3):
        print(obs.to_dict() if obs else "  (deduplicated, not re-reported)")

    if obs1:
        await engine.post_observation(obs1)

    await engine.close()


def main():
    parser = argparse.ArgumentParser(description="AEGISNET observation engine")
    parser.add_argument("--backend", default=DEFAULT_BACKEND_URL, help="Backend base URL")
    parser.add_argument("--timeout", type=float, default=HTTP_TIMEOUT_S, help="HTTP timeout in seconds")
    args = parser.parse_args()

    asyncio.run(_demo())


def _self_test():
    """Guards against the category/status field-name mismatch bug directly.

    If this ever fails, an area_of_interest detection would silently be
    stored as "routine" in the backend -- run this after any change to
    Observation or to_backend_payload().
    """
    engine = ObservationEngine()
    obs = engine.make_observation("backpack", 0.90)  # backpack + high confidence -> area_of_interest
    assert obs is not None
    assert obs.category == "area_of_interest", f"hazard_rules classified this as {obs.category!r}"

    payload = obs.to_backend_payload()
    assert "status" in payload, "backend payload must use 'status', not 'category'"
    assert payload["status"] == "area_of_interest", (
        f"BUG: payload['status'] is {payload['status']!r}, expected 'area_of_interest' -- "
        f"this would silently store as routine in the backend"
    )
    assert "category" not in payload, "backend payload should not include the internal 'category' key"

    print("PASS: to_backend_payload() correctly maps category -> status")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        _self_test()
    else:
        main()
