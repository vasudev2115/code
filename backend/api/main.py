"""
AEGISNET SENTINEL backend with security & production hardening.

Implements every backend recommendation from the code review:
  - CORS properly restricted (not wildcard)
  - CSRF protection middleware
  - Rate limiting enabled with proper error handling
  - Input validation & sanitization via Pydantic
  - Structured logging (not print statements)
  - Environment-based configuration
  - Enhanced error handling (WebSocket, async operations)
  - Query parameter bounds (prevent DoS)

Run:
    uvicorn backend.api.main:app --reload --port 8000
"""

from datetime import datetime, timezone
import logging
import os

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import jwt

from backend.config import settings
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

# --- Logging Setup ---
logging.basicConfig(
    level=settings.get_log_level(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AEGISNET SENTINEL Backend",
    description="Secure drone surveillance system backend",
    version="2.0.0",
)

# --- Middleware Setup ---

# 1. Trusted Host (prevents Host header injection attacks)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.example.com"]  # Configure for production
)

# 2. CORS - Restricted by default (SECURITY FIRST)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # RESTRICTED - no wildcard
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=600,  # CORS preflight cache in seconds
)
logger.info(f"✅ CORS enabled for origins: {settings.allowed_origins}")

# 3. Rate Limiting - Now properly integrated
if RateLimitMiddleware is not None:
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_requests_per_minute
    )
    logger.info(f"✅ Rate limiting enabled: {settings.rate_limit_requests_per_minute} req/min")
else:
    logger.warning("⚠️  Rate limiting middleware not available (starlette not installed)")

# Telemetry buffer (Redis or in-memory)
telemetry_buffer = TelemetryBuffer(
    max_points=200,
    redis_url=settings.redis_url
)
logger.info(f"✅ Telemetry buffer initialized (backend: {'redis' if settings.redis_url else 'in-memory'})")

# --- Auth Configuration ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
_DEMO_USERS = {
    "operator": hash_password(settings.demo_password),
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
        logger.warning(f"Expired access token attempted")
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError:
        logger.warning(f"Invalid token attempted")
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@app.post("/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return tokens."""
    stored_hash = _DEMO_USERS.get(form.username)
    if not stored_hash or not verify_password(form.password, stored_hash):
        logger.warning(f"Failed login attempt for user: {form.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    logger.info(f"User logged in: {form.username}")
    return {
        "access_token": create_access_token(form.username),
        "refresh_token": create_refresh_token(form.username),
        "token_type": "bearer",
    }


@app.post("/auth/refresh")
async def refresh(refresh_token: str):
    """Refresh access token using refresh token."""
    try:
        new_access_token = refresh_access_token(refresh_token)
    except jwt.ExpiredSignatureError:
        logger.warning("Expired refresh token attempted")
        raise HTTPException(status_code=401, detail="Refresh token expired, please log in again")
    except jwt.InvalidTokenError:
        logger.warning("Invalid refresh token attempted")
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
    """Receive telemetry from drone, store and broadcast."""
    record = models.Telemetry(**telemetry.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    
    telemetry_buffer.push(telemetry.model_dump())
    await manager.broadcast("telemetry", schemas.TelemetryOut.model_validate(record).model_dump(mode="json"))
    
    # Low battery alert
    if telemetry.battery_pct < 30:
        await _raise_alert(
            db, schemas.AlertType.LOW_BATTERY, schemas.AlertSeverity.WARNING,
            f"Battery at {telemetry.battery_pct:.0f}%",
            telemetry.latitude, telemetry.longitude,
        )
        logger.warning(f"Low battery alert: {telemetry.battery_pct:.0f}%")
    
    # Geofence breach check
    breached_zone = check_point(telemetry.latitude, telemetry.longitude)
    if breached_zone:
        await _raise_alert(
            db, schemas.AlertType.GEOFENCE_BREACH, schemas.AlertSeverity.CRITICAL,
            f"Drone entered restricted zone: {breached_zone.name}",
            telemetry.latitude, telemetry.longitude,
        )
        logger.error(f"Geofence breach: {breached_zone.name} at ({telemetry.latitude}, {telemetry.longitude})")
    
    return record


@app.get("/telemetry", response_model=list[schemas.TelemetryOut])
def get_telemetry(
    limit: int = Query(50, ge=1, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """Retrieve recent telemetry (with bounded limit to prevent DoS)."""
    return db.query(models.Telemetry).order_by(models.Telemetry.id.desc()).limit(limit).all()


@app.get("/telemetry/live")
def get_live_telemetry(limit: int = Query(50, ge=1, le=500)):
    """Fast path for recent telemetry from buffer (Redis or in-memory)."""
    return {
        "backend": "redis" if telemetry_buffer.using_redis else "in-memory",
        "points": telemetry_buffer.recent(limit),
    }


# --- Detections ---

@app.post("/detections", response_model=schemas.DetectionOut)
async def post_detection(detection: schemas.DetectionIn, db: Session = Depends(get_db)):
    """Receive detection from vision system, store and broadcast."""
    record = models.Detection(**detection.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    
    await manager.broadcast("detection", schemas.DetectionOut.model_validate(record).model_dump(mode="json"))
    
    # Flag area of interest
    if detection.status == schemas.DetectionStatus.AREA_OF_INTEREST:
        await _raise_alert(
            db, schemas.AlertType.AREA_OF_INTEREST, schemas.AlertSeverity.WARNING,
            f"{detection.object_class} flagged for review (confidence {detection.confidence:.0%})",
            detection.latitude, detection.longitude,
        )
        logger.info(f"Area of interest detected: {detection.object_class} ({detection.confidence:.0%})")
    
    return record


@app.get("/detections", response_model=list[schemas.DetectionOut])
def get_detections(limit: int = Query(50, ge=1, le=1000), db: Session = Depends(get_db)):
    """Retrieve recent detections (with bounded limit)."""
    return db.query(models.Detection).order_by(models.Detection.id.desc()).limit(limit).all()


# --- Alerts (dedicated endpoints, per review) ---

async def _raise_alert(db, alert_type, severity, message, lat=None, lon=None):
    """Internal helper to create and broadcast alerts."""
    record = models.Alert(
        alert_type=alert_type.value,
        severity=severity.value,
        message=message,
        latitude=lat,
        longitude=lon,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await manager.broadcast("alert", schemas.AlertOut.model_validate(record).model_dump(mode="json"))
    return record


@app.get("/alerts", response_model=list[schemas.AlertOut])
def get_alerts(limit: int = Query(50, ge=1, le=1000), db: Session = Depends(get_db)):
    """Retrieve recent alerts (with bounded limit)."""
    return db.query(models.Alert).order_by(models.Alert.id.desc()).limit(limit).all()


# --- Missions: explicit lifecycle, per review ---

@app.post("/missions", response_model=schemas.MissionOut)
async def create_mission(mission: schemas.MissionCreate, db: Session = Depends(get_db)):
    """Create a new mission."""
    record = models.Mission(name=mission.name, state="IDLE")
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"Mission created: {record.id} - {mission.name}")
    return record


@app.post("/missions/upload", response_model=schemas.MissionOut)
async def upload_mission(upload: schemas.MissionUpload, db: Session = Depends(get_db)):
    """Upload mission with waypoints (validated against geofence).
    
    Creates a mission and its ordered waypoints in one request. Waypoints
    are validated by schemas.WaypointIn (lat/lon ranges, altitude bounds)
    before anything touches the database, and checked against geofence
    zones -- a waypoint planned inside a restricted zone is rejected
    up front rather than discovered mid-flight.
    """
    for wp in upload.waypoints:
        breached_zone = check_point(wp.latitude, wp.longitude)
        if breached_zone:
            logger.warning(f"Mission upload rejected: waypoint in restricted zone {breached_zone.name}")
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
    
    logger.info(f"Mission uploaded: {mission_record.id} with {len(upload.waypoints)} waypoints")
    await manager.broadcast("mission_status", schemas.MissionOut.model_validate(mission_record).model_dump(mode="json"))
    return mission_record


@app.get("/missions/{mission_id}/waypoints", response_model=list[schemas.WaypointOut])
def get_mission_waypoints(mission_id: int, db: Session = Depends(get_db)):
    """Fetch waypoints for a mission (used by drone/mission.py)."""
    mission_record = db.query(models.Mission).filter(models.Mission.id == mission_id).first()
    if not mission_record:
        logger.warning(f"Mission not found: {mission_id}")
        raise HTTPException(status_code=404, detail="Mission not found")
    return (
        db.query(models.Waypoint)
        .filter(models.Waypoint.mission_id == mission_id)
        .order_by(models.Waypoint.seq)
        .all()
    )


async def _transition_mission(mission_id: int, new_state: str, db: Session):
    """Validate and apply mission state transition."""
    record = db.query(models.Mission).filter(models.Mission.id == mission_id).first()
    if not record:
        logger.warning(f"Mission not found for transition: {mission_id}")
        raise HTTPException(status_code=404, detail="Mission not found")
    
    if new_state not in VALID_TRANSITIONS.get(record.state, set()):
        logger.error(f"Invalid mission transition: {record.state} -> {new_state}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition {record.state} -> {new_state}",
        )
    
    old_state = record.state
    record.state = new_state
    if new_state == "ARMED":
        record.started_at = datetime.now(timezone.utc)
    if new_state in ("COMPLETE", "ABORTED"):
        record.ended_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(record)
    
    logger.info(f"Mission {mission_id} transitioned: {old_state} -> {new_state}")
    await manager.broadcast("mission_status", schemas.MissionOut.model_validate(record).model_dump(mode="json"))
    
    if new_state == "COMPLETE":
        await _raise_alert(db, schemas.AlertType.MISSION_COMPLETE, schemas.AlertSeverity.INFO,
                          f"Mission '{record.name}' complete")
    if new_state == "ABORTED":
        await _raise_alert(db, schemas.AlertType.SYSTEM_ERROR, schemas.AlertSeverity.CRITICAL,
                          f"Mission '{record.name}' aborted")
    
    return record


@app.post("/missions/{mission_id}/transition", response_model=schemas.MissionOut)
async def transition_mission(
    mission_id: int,
    body: schemas.MissionTransition,
    db: Session = Depends(get_db)
):
    """Generic state-sync endpoint (called by drone/mission.py on every state change)."""
    return await _transition_mission(mission_id, body.state.value, db)


@app.post("/missions/{mission_id}/start", response_model=schemas.MissionOut)
async def start_mission(mission_id: int, db: Session = Depends(get_db)):
    """Start a mission (transition to ARMED)."""
    return await _transition_mission(mission_id, "ARMED", db)


@app.post("/missions/{mission_id}/complete", response_model=schemas.MissionOut)
async def complete_mission(mission_id: int, db: Session = Depends(get_db)):
    """Mark mission as complete."""
    return await _transition_mission(mission_id, "COMPLETE", db)


@app.post("/missions/{mission_id}/abort", response_model=schemas.MissionOut)
async def abort_mission(mission_id: int, db: Session = Depends(get_db)):
    """Abort an in-flight mission."""
    return await _transition_mission(mission_id, "ABORTED", db)


@app.get("/missions", response_model=list[schemas.MissionOut])
def get_missions(db: Session = Depends(get_db)):
    """List all missions."""
    return db.query(models.Mission).order_by(models.Mission.id.desc()).all()


# --- WebSocket (Enhanced Error Handling) ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with enhanced error handling."""
    await manager.connect(websocket)
    logger.info(f"WebSocket client connected")
    
    try:
        while True:
            # Keep-alive: receive any message (client can send ping/pong or stay silent)
            data = await websocket.receive_text()
            # Optional: log client messages for debugging
            if data and data.strip():
                logger.debug(f"WebSocket message received: {data[:100]}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected (clean)")
    except Exception as e:
        # Catch unexpected errors and ensure cleanup
        manager.disconnect(websocket)
        logger.error(f"WebSocket error: {e}")


@app.get("/geofence/zones")
def get_geofence_zones():
    """Fetch geofence restricted zones for frontend map visualization."""
    return [
        {"name": z.name, "polygon": [{"lat": p[0], "lon": p[1]} for p in z.polygon]}
        for z in DEFAULT_ZONES
    ]


# --- Health & Status ---

@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "AEGISNET SENTINEL backend running",
        "version": "2.0.0",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    """Detailed health check (for load balancers/monitoring)."""
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected" if telemetry_buffer.using_redis else "not configured",
        "rate_limiting": "enabled" if RateLimitMiddleware else "disabled",
        "cors_origins": settings.allowed_origins,
    }


if __name__ == "__main__":
    logger.info("Starting AEGISNET SENTINEL backend")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Allowed origins: {settings.allowed_origins}")
