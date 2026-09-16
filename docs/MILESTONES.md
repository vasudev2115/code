# Milestones

## M1-M7 (core pipeline, do these in order)

1. **M1** — `drone/connect.py` prints live simulated GPS from PX4 SITL
2. **M2** — `vision/detect_webcam.py` shows live bounding boxes from webcam
3. **M4** — `python vision/observation_engine.py` prints structured observations
4. **M5** — `uvicorn app.main:app --reload` + confirm `POST /detections` stores data
5. **Telemetry integration** — run `drone/telemetry_streamer.py` alongside vision, confirm `vision/detectors/telemetry_snapshot.py` shows `live=True`
6. **WebSocket** — confirm the dashboard receives live telemetry/detection/alert events
7. **M7** — run drone + vision + backend + frontend together, full loop

## Advanced (after M7, one at a time)

- `vision/fusion/` — thermal, gas, LiDAR, fusion (all simulated, verified running)
- `swarm/` — swarm coordination, satellite link, secure comms, payload registry, power model (all simulated except encryption/ECDH, which is real), plus formation flying/collision avoidance/A* routing (real algorithms, verified with tests/test_swarm_coordinator.py)
- Frontend tactical dashboard — Leaflet map, Recharts telemetry graphs, threat timeline, camera feed panel
- Mission planner — click-to-add/drag waypoints, per-waypoint altitude/hover, geofence-validated upload
- Mission Control — live state sync between mission.py and the dashboard, remote abort (mission.py polls every ~2s)
- Security — JWT auth w/ refresh tokens, ECDH key exchange, rate limiting, HTTPS dev cert generator (all verified except the Starlette middleware wrapper)
- Folder restructure — backend/vision reorganized into api/models/services/websocket/security and detectors/trackers/fusion/utils, run via `python -m` from the project root
- CI/CD — GitHub Actions (`.github/workflows/ci.yml`), pytest suite, ESLint config, Docker Compose (compose/CI YAML validated, not run against real infra)

## Stretch goals (not built, noted honestly)

- Real multi-vehicle PX4 SITL swarm (heavier setup, more RAM/CPU)
- Real SDR-based anti-jamming
- Physical sensor hardware integration
- RTK GPS
