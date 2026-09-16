"""
Pydantic schemas with validation.

Per the code review:
  - Telemetry: validate lat/lon ranges, battery 0-100, sensible altitude.
  - Detection: confidence 0-1, status restricted to known values.
  - Alerts: dedicated schema, not reusing detection objects.
  - Mission lifecycle: explicit states.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- Telemetry ---

class TelemetryIn(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=-100, le=10000)  # generous bounds, catches garbage data
    battery_pct: float = Field(..., ge=0, le=100)
    speed_mps: Optional[float] = Field(default=None, ge=0, le=150)
    heading_deg: Optional[float] = Field(default=None, ge=0, le=360)
    flight_mode: Optional[str] = None


class TelemetryOut(TelemetryIn):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Detections ---

class DetectionStatus(str, Enum):
    ROUTINE = "routine"
    AREA_OF_INTEREST = "area_of_interest"


class DetectionIn(BaseModel):
    object_class: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=-100, le=10000)
    status: DetectionStatus = DetectionStatus.ROUTINE

    @field_validator("object_class")
    @classmethod
    def strip_class(cls, v: str) -> str:
        return v.strip().lower()


class DetectionOut(DetectionIn):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Alerts (dedicated schema, per review -- not reusing detection objects) ---

class AlertType(str, Enum):
    LOW_BATTERY = "LOW_BATTERY"
    AREA_OF_INTEREST = "AREA_OF_INTEREST"
    GPS_LOSS = "GPS_LOSS"
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    MISSION_COMPLETE = "MISSION_COMPLETE"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    GEOFENCE_BREACH = "GEOFENCE_BREACH"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertIn(BaseModel):
    alert_type: AlertType
    severity: AlertSeverity
    message: str = Field(..., min_length=1, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class AlertOut(AlertIn):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Missions ---

class MissionState(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    TAKEOFF = "TAKEOFF"
    MISSION = "MISSION"
    OBSERVATION = "OBSERVATION"
    RETURN = "RETURN"
    LAND = "LAND"
    COMPLETE = "COMPLETE"
    ABORTED = "ABORTED"


class MissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class MissionTransition(BaseModel):
    """What drone/mission.py posts on every state change, to keep
    the dashboard's Mission Control panel in sync with the actual flight."""
    state: MissionState


class MissionOut(BaseModel):
    id: int
    name: str
    state: MissionState
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Waypoints (mission planner) ---

class WaypointIn(BaseModel):
    seq: int = Field(..., ge=0, description="Order within the mission, 0-indexed")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=0, le=500)
    hover_s: float = Field(default=0, ge=0, le=600)


class WaypointOut(WaypointIn):
    id: int
    mission_id: int

    class Config:
        from_attributes = True


class MissionUpload(BaseModel):
    """What the frontend's 'Upload Mission' button posts."""
    name: str = Field(..., min_length=1, max_length=200)
    waypoints: list[WaypointIn] = Field(..., min_length=1, max_length=100)
