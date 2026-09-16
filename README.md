# AEGISNET SENTINEL

Student capstone: an AI-assisted drone surveillance simulation. Flags
"areas of interest" for human review from simulated multi-sensor data —
never claims to detect explosives or confirm hazards. See
`docs/CODE_REVIEW_RESPONSE.md` for how this build addresses supplied
code review/roadmap feedback, and `docs/MILESTONES.md` for the full
run-order.

## Structure

```
aegisnet-sentinel/
├── backend/
│   ├── api/          # FastAPI app (main.py) -- the entrypoint
│   ├── models/        # SQLAlchemy ORM (orm.py) + Pydantic schemas (schemas.py)
│   ├── services/        # database.py, geofence.py, telemetry_buffer.py
│   ├── websocket/          # ws_manager.py -- typed event broadcast
│   └── security/             # auth.py (JWT), rate_limit.py, generate_dev_cert.py
├── vision/
│   ├── detectors/     # detect_webcam.py, observation_engine.py, telemetry_snapshot.py
│   ├── trackers/        # tracker.py (custom IoU), deepsort_wrapper.py (optional)
│   ├── fusion/             # thermal/gas/lidar simulators + weighted fusion_engine.py
│   └── utils/                # config.py, hazard_rules.py
├── drone/            # PX4/MAVSDK flight scripts + mission.py central controller
├── swarm/             # leader election, formation flying, A* routing, ECDH, secure comms
├── frontend/           # React/TS tactical dashboard
├── tests/                # pytest-compatible test suite (25 tests)
├── docs/                   # milestones, architecture, code review response
├── docker-compose.yml        # backend + frontend + postgres + redis (untested here, no Docker access)
└── .github/workflows/ci.yml    # GitHub Actions: tests, lint, build
```

## Run order (see docs/MILESTONES.md for full detail)

Backend and vision now use proper Python packages -- run with `-m` from
this top-level directory, not by `cd`-ing into the subfolder:

1. **drone/**: get PX4 SITL running, then `cd drone && python mission.py`
2. **vision**: `python -m vision.detectors.detect_webcam` (needs a webcam)
3. **backend**: `cd backend/api && uvicorn main:app --reload --port 8000`
   (or `python -m uvicorn backend.api.main:app --reload --port 8000` from the root)
4. **frontend**: `cd frontend && npm install && npm run dev`
5. **tests**: `pip install pytest && pytest tests/` from the root

## Docker (untested here -- no Docker access in the build environment)

```
docker compose up
```
Starts postgres, redis, backend, frontend. drone/ and vision/ still run on your host, not containerized (need GUI/camera access PX4/Gazebo and a webcam require).

## Scope honesty

- `vision/fusion/` sensors (thermal, gas, LiDAR) are simulated software --
  no physical hardware exists.
- `swarm/secure_comm.py` and `swarm/ecdh_exchange.py` use real, verified
  cryptography. `swarm/swarm_coordinator.py`'s formation flying / collision
  avoidance / mesh relay are real algorithms, verified with the test suite,
  running on simulated (not physical) multi-drone agents.
- `backend/security/rate_limit.py`'s TokenBucket algorithm is verified;
  its Starlette middleware wrapper is standard code but untested here
  (starlette isn't installed in the build environment).
- `vision/detectors/ocr_reader.py` and `vision/trackers/deepsort_wrapper.py`
  are written correctly against their libraries' documented APIs but
  untested -- those packages need a `pip install` this environment
  couldn't reach (no network).
- `docker-compose.yml` and the Postgres path in `backend/services/database.py`
  are correct, standard configuration but unverified against a real
  Docker/Postgres instance for the same reason.

Where something says "verified," it was actually executed during
development, with real assertions checked -- not just written and
assumed correct.
