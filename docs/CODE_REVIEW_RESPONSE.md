# Code Review Response

This tracks every recommendation from `AEGISNET_Code_Review_and_Recommended_Changes.pdf`
and `AEGISNET_Sentinel_Feature_Code_Roadmap.pdf` against what was actually
implemented, so you can show your mentor the feedback loop closed.

## From the Code Review

| Recommendation | Status | Where |
|---|---|---|
| Don't hard-code model/confidence/camera index | Done | `vision/config.py` + CLI args in `detect_webcam.py` |
| Handle Ctrl+C and camera cleanup | Done | `detect_webcam.py` try/finally block |
| Keep detect_webcam.py simple, no backend/DB logic mixed in | Done | Detection posting delegated to `ObservationEngine` |
| Create `get_current_position()` telemetry interface | Done | `vision/telemetry_snapshot.py` |
| Don't query drone per bounding box | Done | Snapshot read from a local file, not a live MAVSDK call, per frame |
| Keep 5-second per-label dedup | Done | `ObservationEngine._should_report()` |
| Check HTTP response status, not just transport errors | Done | `response.raise_for_status()` in `post_observation()` |
| Configurable timeout | Done | `config.HTTP_TIMEOUT_S`, overridable via `--timeout` |
| Replace blocking `httpx.post()` with async/reusable client | Done | `httpx.AsyncClient` reused across the engine's lifetime, posts fired as background tasks |
| Keep `hazard_rules.py` separate, don't rename to "explosive-confirmed" | Done | Still returns only `routine` / `area_of_interest` |
| Add unit tests for hazard rules | Done | Self-tests in `hazard_rules.py` (`python hazard_rules.py`) |
| Telemetry validation (lat/lon ranges, battery 0-100, altitude) | Done | `schemas.TelemetryIn` field constraints |
| Detection validation (confidence 0-1, restricted status) | Done | `schemas.DetectionIn` |
| Dedicated Alert schema, not reused detection objects | Done | `schemas.AlertIn`/`AlertOut`, separate `Alert` model/table |
| Mission lifecycle: start/complete/abort | Done | `/missions/{id}/start`, `/complete`, `/abort` with state-machine validation |
| WebSocket event envelope `{type, timestamp, data}` | Done | `ws_manager.ConnectionManager.broadcast()` |
| Keep dependency versions pinned during integration | Done | `requirements.txt` files unchanged from originally reviewed versions |

## From the Feature Roadmap

| Item | Status | Where |
|---|---|---|
| `mission.py` as central controller | Done | `drone/mission.py` — full state machine (IDLE→ARMED→...→COMPLETE/ABORTED), owns battery failsafe + telemetry streaming |
| `tracker.py` for stable object IDs | Done | `vision/tracker.py`, simple IoU-based tracker with self-test |
| `config.py` for vision settings | Done | `vision/config.py` |
| Sensor fusion module structure | Done | `vision/fusion/fusion_engine.py` |
| Alert types (LOW_BATTERY, AREA_OF_INTEREST, GPS_LOSS, etc.) | Done | `schemas.AlertType` enum |
| WebSocket event types (telemetry/detection/alert/mission_status) | Done | Implemented in `ws_manager.py`, consumed in `frontend/src/useMissionSocket.ts` |

## What was intentionally NOT changed

Per both documents' "What NOT to Change/Do Now" sections:
- YOLOv8n was not swapped for a heavier model
- Thermal/LiDAR/swarm/satellite code lives in separate `vision/fusion/`
  and `swarm/` folders, not mixed into the M1-M7 pipeline
- No dependency versions were bumped
- `area_of_interest` was never renamed to imply confirmed explosive
  detection, anywhere in the codebase

## Bug found during cross-file consistency audit

While double-checking that every frontend/backend/drone/vision call
site agreed on field names, one real bug turned up (not caught by
`py_compile`, since it's a runtime/logic issue, not a syntax error):

**`observation_engine.py` was sending a field called `category`, but
the backend's `DetectionIn` schema expects `status`.** Because `status`
has a default value (`"routine"`), this didn't cause an error -- it
would have silently stored every single detection as `routine`, even
genuine `area_of_interest` flags, defeating the entire hazard-alerting
pipeline while looking like it worked.

Fixed via an explicit `to_backend_payload()` method that maps
`category` -> `status` by name, plus a `_self_test()` in
`observation_engine.py` that asserts this mapping is correct --
run `python -m vision.detectors.observation_engine --self-test` to verify.

This is exactly the kind of bug that only surfaces when two halves of
a system are actually run together, which is why the milestone order
(get M2 working, then M4, then M5, then connect them) matters more
than any individual file being "done."

## Honest verification note

Everything above was checked for syntax correctness (`python -m
py_compile`) across all files. Modules with no external network
dependency were actually executed and their output verified:
`hazard_rules.py` (5/5 self-tests pass), `tracker.py`, `telemetry_snapshot.py`,
`fusion_engine.py`, `secure_comm.py` (real AES-GCM encrypt/decrypt round-trip
verified), `swarm_coordinator.py`.

`observation_engine.py`, `detect_webcam.py`, and the entire `backend/`
could only be syntax-checked in this environment — installing
`fastapi`/`httpx`/`ultralytics` requires network access this sandbox
didn't have when this build ran. Run the M2 → M4 → M5 sequence from
`docs/MILESTONES.md` on your own machine to get the first real runtime
confirmation of those pieces.
