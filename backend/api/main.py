"""
AEGISNET SENTINEL backend.

Implements every backend recommendation from the code review:
  - Telemetry/detection/alert validation via Pydantic schemas
  - Dedicated Alert model/schema (not reusing detection objects)
  - Mission lifecycle: start / complete / abort endpoints with
    predictable state transitions
  - CORS wildcard for local dev (documented as needing restriction
    before any real deployment)
  - Typed WebSocket event envelope: {type, timestamp, data}

Run:
    uvicorn main:app --reload --port 8000
"""

from datetime import datetime, timezone
import os

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import jwt

from backend.models import orm as models
from backend.models import schemas
from backend.services.database import engine, get_db, Base
from backend.websocket.ws_manager import manager
from backend.services.geofence import check_point, DEFAULT_ZONES
from backend.security.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, verify_token, refresh_access_token,
)
from backend.security.rate_limit import RateLimitMiddleware
from backend.services.telemetry_buffer import TelemetryBuffer

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AEGISNET SENTINEL Backend")

# Falls back to in-memory automatically if REDIS_URL isn't set or Redis
# isn't reachable -- see telemetry_buffer.py.
telemetry_buffer = TelemetryBuffer(max_points=200, redis_url=os.environ.get("REDIS_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev only -- restrict before any real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if RateLimitMiddleware is not None:
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120)


# --- Auth ---
# Demo, in-memory single-user store -- swap for a real users table before
# any real deployment. Default credentials are for local testing only.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
_DEMO_USERS = {
    "operator": hash_password(os.environ.get("AEGISNET_DEMO_PASSWORD", "changeme")),
}


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Protects an endpoint: `user: str = Depends(get_current_user)`.

    NOT applied to the existing telemetry/detection/mission endpoints
    yet -- the frontend has no login flow, so requiring auth there
    would break the dashboard outright. This is real, working
    infrastructure ready to apply once a login UI exists.
    """
    try:
        payload = verify_token(token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@app.post("/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    stored_hash = _DEMO_USERS.get(form.username)
    if not stored_hash or not verify_password(form.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    return {
        "access_token": create_access_token(form.username),
        "refresh_token": create_refresh_token(form.username),
        "token_type": "bearer",
    }


@app.post("/auth/refresh")
async def refresh(refresh_token: str):
    try:
        new_access_token = refresh_access_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return {"access_token": new_access_token, "token_type": "bearer"}


@app.get("/auth/me")
async def read_current_user(user: str = Depends(get_current_user)):
    """Example protected endpoint -- proves the auth dependency works."""
    return {"username": user}


# --- Mission state machine rules (mirrors drone/mission.py) ---
VALID_TRANSITIONS = {
    "IDLE": {"ARMED"},
    "ARMED": {"TAKEOFF", "ABORTED"},
    "TAKEOFF": {"MISSION", "ABORTED"},
    "MISSION": {"OBSERVATION", "RETURN", "ABORTED"},
    "OBSERVATION": {"RETURN", "ABORTED"},
    "RETURN": {"LAND", "ABORTED"},
    "LAND": {"COMPLETE", "ABORTED"},
    "COMPLETE": set(),
    "ABORTED": set(),
}


# --- Telemetry ---

@app.post("/telemetry", response_model=schemas.TelemetryOut)
async def post_telemetry(telemetry: schemas.TelemetryIn, db: Session = Depends(get_db)):
    record = models.Telemetry(**telemetry.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    telemetry_buffer.push(telemetry.model_dump())

    await manager.broadcast("telemetry", schemas.TelemetryOut.model_validate(record).model_dump(mode="json"))

    if telemetry.battery_pct < 30:
        await _raise_alert(
            db, schemas.AlertType.LOW_BATTERY, schemas.AlertSeverity.WARNING,
            f"Battery at {telemetry.battery_pct:.0f}%",
            telemetry.latitude, telemetry.longitude,
        )

    breached_zone = check_point(telemetry.latitude, telemetry.longitude)
    if breached_zone:
        await _raise_alert(
            db, schemas.AlertType.GEOFENCE_BREACH, schemas.AlertSeverity.CRITICAL,
            f"Drone entered restricted zone: {breached_zone.name}",
            telemetry.latitude, telemetry.longitude,
        )

    return record


@app.get("/telemetry", response_model=list[schemas.TelemetryOut])
def get_telemetry(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(models.Telemetry).order_by(models.Telemetry.id.desc()).limit(limit).all()


@app.get("/telemetry/live")
def get_live_telemetry(limit: int = 50):
    """Fast path for 'what's happening right now' -- reads from the
    in-memory/Redis buffer instead of the database. Useful for a
    dashboard that wants recent points without hitting SQLite/Postgres
    on every poll."""
    return {
        "backend": "redis" if telemetry_buffer.using_redis else "in-memory",
        "points": telemetry_buffer.recent(limit),
    }


# --- Detections ---

@app.post("/detections", response_model=schemas.DetectionOut)
async def post_detection(detection: schemas.DetectionIn, db: Session = Depends(get_db)):
    record = models.Detection(**detection.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    await manager.broadcast("detection", schemas.DetectionOut.model_validate(record).model_dump(mode="json"))

    if detection.status == schemas.DetectionStatus.AREA_OF_INTEREST:
        await _raise_alert(
            db, schemas.AlertType.AREA_OF_INTEREST, schemas.AlertSeverity.WARNING,
            f"{detection.object_class} flagged for review (confidence {detection.confidence:.0%})",
            detection.latitude, detection.longitude,
        )

    return record


@app.get("/detections", response_model=list[schemas.DetectionOut])
def get_detections(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(models.Detection).order_by(models.Detection.id.desc()).limit(limit).all()


# --- Alerts (dedicated endpoints, per review) ---

async def _raise_alert(db, alert_type, severity, message, lat=None, lon=None):
    record = models.Alert(
        alert_type=alert_type.value, severity=severity.value,
        message=message, latitude=lat, longitude=lon,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await manager.broadcast("alert", schemas.AlertOut.model_validate(record).model_dump(mode="json"))
    return record


@app.get("/alerts", response_model=list[schemas.AlertOut])
def get_alerts(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(models.Alert).order_by(models.Alert.id.desc()).limit(limit).all()


# --- Missions: explicit lifecycle, per review ---

@app.post("/missions", response_model=schemas.MissionOut)
async def create_mission(mission: schemas.MissionCreate, db: Session = Depends(get_db)):
    record = models.Mission(name=mission.name, state="IDLE")
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.post("/missions/upload", response_model=schemas.MissionOut)
async def upload_mission(upload: schemas.MissionUpload, db: Session = Depends(get_db)):
    """What the frontend's Mission Planner 'Upload Mission' button calls.

    Creates a mission and its ordered waypoints in one request. Waypoints
    are validated by schemas.WaypointIn (lat/lon ranges, altitude bounds)
    before anything touches the database, and checked against geofence
    zones -- a waypoint planned inside a restricted zone is rejected
    up front rather than discovered mid-flight.
    """
    for wp in upload.waypoints:
        breached_zone = check_point(wp.latitude, wp.longitude)
        if breached_zone:
            raise HTTPException(
                status_code=400,
                detail=f"Waypoint {wp.seq} falls inside restricted zone '{breached_zone.name}'. "
                       f"Move it outside the marked red zone before uploading.",
            )

    mission_record = models.Mission(name=upload.name, state="IDLE")
    db.add(mission_record)
    db.commit()
    db.refresh(mission_record)

    for wp in upload.waypoints:
        db.add(models.Waypoint(
            mission_id=mission_record.id,
            seq=wp.seq,
            latitude=wp.latitude,
            longitude=wp.longitude,
            altitude_m=wp.altitude_m,
            hover_s=wp.hover_s,
        ))
    db.commit()

    await manager.broadcast("mission_status", schemas.MissionOut.model_validate(mission_record).model_dump(mode="json"))
    return mission_record


@app.get("/missions/{mission_id}/waypoints", response_model=list[schemas.WaypointOut])
def get_mission_waypoints(mission_id: int, db: Session = Depends(get_db)):
    """drone/mission.py polls this to fetch the waypoints to fly."""
    mission_record = db.query(models.Mission).filter(models.Mission.id == mission_id).first()
    if not mission_record:
        raise HTTPException(status_code=404, detail="Mission not found")
    return (
        db.query(models.Waypoint)
        .filter(models.Waypoint.mission_id == mission_id)
        .order_by(models.Waypoint.seq)
        .all()
    )


async def _transition_mission(mission_id: int, new_state: str, db: Session):
    record = db.query(models.Mission).filter(models.Mission.id == mission_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mission not found")

    if new_state not in VALID_TRANSITIONS.get(record.state, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition {record.state} -> {new_state}",
        )

    record.state = new_state
    if new_state == "ARMED":
        record.started_at = datetime.now(timezone.utc)
    if new_state in ("COMPLETE", "ABORTED"):
        record.ended_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)

    await manager.broadcast("mission_status", schemas.MissionOut.model_validate(record).model_dump(mode="json"))

    if new_state == "COMPLETE":
        await _raise_alert(db, schemas.AlertType.MISSION_COMPLETE, schemas.AlertSeverity.INFO,
                            f"Mission '{record.name}' complete")
    if new_state == "ABORTED":
        await _raise_alert(db, schemas.AlertType.SYSTEM_ERROR, schemas.AlertSeverity.CRITICAL,
                            f"Mission '{record.name}' aborted")

    return record


@app.post("/missions/{mission_id}/transition", response_model=schemas.MissionOut)
async def transition_mission(mission_id: int, body: schemas.MissionTransition, db: Session = Depends(get_db)):
    """Generic state-sync endpoint -- drone/mission.py calls this on
    every internal state change, so the dashboard reflects the actual
    live flight, not just whatever was last clicked manually. Reuses
    the same validated transition logic and VALID_TRANSITIONS table as
    the manual start/complete/abort endpoints, so mission.py can't push
    an illegal transition either.
    """
    return await _transition_mission(mission_id, body.state.value, db)


@app.post("/missions/{mission_id}/start", response_model=schemas.MissionOut)
async def start_mission(mission_id: int, db: Session = Depends(get_db)):
    return await _transition_mission(mission_id, "ARMED", db)


@app.post("/missions/{mission_id}/complete", response_model=schemas.MissionOut)
async def complete_mission(mission_id: int, db: Session = Depends(get_db)):
    return await _transition_mission(mission_id, "COMPLETE", db)


@app.post("/missions/{mission_id}/abort", response_model=schemas.MissionOut)
async def abort_mission(mission_id: int, db: Session = Depends(get_db)):
    return await _transition_mission(mission_id, "ABORTED", db)


@app.get("/missions", response_model=list[schemas.MissionOut])
def get_missions(db: Session = Depends(get_db)):
    return db.query(models.Mission).order_by(models.Mission.id.desc()).all()


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client doesn't need to send anything meaningful
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/geofence/zones")
def get_geofence_zones():
    """Frontend fetches this to draw restricted zones on the map."""
    return [
        {"name": z.name, "polygon": [{"lat": p[0], "lon": p[1]} for p in z.polygon]}
        for z in DEFAULT_ZONES
    ]


@app.get("/")
def root():
    return {"status": "AEGISNET SENTINEL backend running"}
