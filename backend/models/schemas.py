"""
Pydantic schemas with advanced validation.

Per the code review:
  - Telemetry: validate lat/lon ranges, battery 0-100, sensible altitude.
  - Detection: confidence 0-1, status restricted to known values.
  - Alerts: dedicated schema, not reusing detection objects.
  - Mission lifecycle: explicit states.
  - Input sanitization: strip/normalize strings, prevent HTML/script injection.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import html
import re

from pydantic import BaseModel, Field, field_validator


# --- Input Sanitization Utilities ---

def sanitize_string(value: str, max_length: int = 500) -> str:
    """Remove/escape HTML, normalize whitespace, prevent injection attacks."""
    if not isinstance(value, str):
        return ""
    
    # Escape HTML entities to prevent XSS
    value = html.escape(value)
    
    # Remove control characters
    value = "".join(char for char in value if ord(char) >= 32 or char in "\n\r\t")
    
    # Normalize whitespace
    value = " ".join(value.split())
    
    # Truncate to max length
    return value[:max_length]


def validate_no_sql_injection(value: str) -> str:
    """Additional check for common SQL injection patterns."""
    if not isinstance(value, str):
        return value
    
    # Check for suspicious SQL keywords/patterns
    suspicious_patterns = [
        r"(?i)(union|select|insert|update|delete|drop|exec|script)",
        r"(?i)(--|;|/\*|\*/)",  # SQL comments
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, value):
            raise ValueError(
                f"Input contains suspicious SQL patterns: {value[:50]}..."
            )
    
    return value


# --- Telemetry ---

class TelemetryIn(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude")
    altitude_m: float = Field(..., ge=-100, le=10000, description="Altitude in meters")
    battery_pct: float = Field(..., ge=0, le=100, description="Battery percentage")
    speed_mps: Optional[float] = Field(default=None, ge=0, le=150, description="Speed m/s")
    heading_deg: Optional[float] = Field(default=None, ge=0, le=360, description="Heading degrees")
    flight_mode: Optional[str] = Field(default=None, max_length=50, description="Flight mode")
    
    @field_validator("flight_mode")
    @classmethod
    def validate_flight_mode(cls, v: str | None) -> str | None:
        if v:
            v = sanitize_string(v, max_length=50)
        return v


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
    object_class: str = Field(..., min_length=1, max_length=100, description="Object class/label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=-100, le=10000)
    status: DetectionStatus = DetectionStatus.ROUTINE
    
    @field_validator("object_class")
    @classmethod
    def validate_object_class(cls, v: str) -> str:
        v = sanitize_string(v, max_length=100)
        v = v.strip().lower()
        # Only alphanumeric and underscores
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(f"Invalid object_class format: {v}")
        return v


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
    message: str = Field(..., min_length=1, max_length=500, description="Alert message")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    
    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        return sanitize_string(v, max_length=500)


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
    name: str = Field(..., min_length=1, max_length=200, description="Mission name")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = sanitize_string(v, max_length=200)
        return validate_no_sql_injection(v)


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
    seq: int = Field(..., ge=0, description="Order within mission, 0-indexed")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude_m: float = Field(..., ge=0, le=500)
    hover_s: float = Field(default=0, ge=0, le=600, description="Hover time seconds")


class WaypointOut(WaypointIn):
    id: int
    mission_id: int
    
    class Config:
        from_attributes = True


class MissionUpload(BaseModel):
    """What the frontend's 'Upload Mission' button posts."""
    name: str = Field(..., min_length=1, max_length=200)
    waypoints: list[WaypointIn] = Field(..., min_length=1, max_length=100)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = sanitize_string(v, max_length=200)
        return validate_no_sql_injection(v)
