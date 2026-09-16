from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from backend.services.database import Base


class Telemetry(Base):
    __tablename__ = "telemetry"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    battery_pct = Column(Float, nullable=False)
    speed_mps = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    flight_mode = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    object_class = Column(String, nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="routine")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    state = Column(String, nullable=False, default="IDLE")
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)


class Waypoint(Base):
    __tablename__ = "waypoints"
    id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    hover_s = Column(Float, nullable=False, default=0)
