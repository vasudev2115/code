import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Polygon, Popup, useMapEvents } from "react-leaflet";
import { DivIcon } from "leaflet";
import { useMissionStore } from "./store";
import "leaflet/dist/leaflet.css";

const DEFAULT_CENTER: [number, number] = [26.812, 80.912];
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

interface GeofenceZone {
  name: string;
  polygon: { lat: number; lon: number }[];
}

function droneIcon() {
  return new DivIcon({
    className: "",
    html: `<div class="drone-marker"></div>`,
    iconSize: [16, 16],
  });
}

function hazardIcon(status: string) {
  const color =
    status === "high_priority_area_of_interest" ? "#f87171" :
    status === "area_of_interest" ? "#fbbf24" : "#60a5fa";
  return new DivIcon({
    className: "",
    html: `<div class="hazard-marker" style="background:${color}"></div>`,
    iconSize: [14, 14],
  });
}

function waypointIcon(index: number, selected: boolean) {
  return new DivIcon({
    className: "",
    html: `<div class="waypoint-marker ${selected ? "selected" : ""}">${index + 1}</div>`,
    iconSize: [26, 26],
  });
}

/** Invisible layer that just listens for map clicks to add waypoints. */
function ClickToAddWaypoint({ enabled }: { enabled: boolean }) {
  const addWaypoint = useMissionStore((s) => s.addWaypoint);
  useMapEvents({
    click(e) {
      if (enabled) addWaypoint(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function TacticalMap({ planningMode }: { planningMode: boolean }) {
  const telemetry = useMissionStore((s) => s.telemetry);
  const dronePath = useMissionStore((s) => s.dronePath);
  const detections = useMissionStore((s) => s.detections);
  const waypoints = useMissionStore((s) => s.waypoints);
  const updateWaypoint = useMissionStore((s) => s.updateWaypoint);
  const selectedWaypointId = useMissionStore((s) => s.selectedWaypointId);
  const selectWaypoint = useMissionStore((s) => s.selectWaypoint);
  const removeWaypoint = useMissionStore((s) => s.removeWaypoint);

  const [zones, setZones] = useState<GeofenceZone[]>([]);

  useEffect(() => {
    fetch(`${BACKEND_URL}/geofence/zones`)
      .then((res) => (res.ok ? res.json() : []))
      .then(setZones)
      .catch(() => setZones([])); // backend not running yet -- just show no zones, don't crash the map
  }, []);

  const center: [number, number] = telemetry
    ? [telemetry.latitude, telemetry.longitude]
    : DEFAULT_CENTER;

  const hazards = detections.filter((d) => d.status !== "routine");

  return (
    <MapContainer center={center} zoom={16} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; OpenStreetMap &copy; CARTO'
      />

      <ClickToAddWaypoint enabled={planningMode} />

      {zones.map((zone, i) => (
        <Polygon
          key={i}
          positions={zone.polygon.map((p) => [p.lat, p.lon] as [number, number])}
          pathOptions={{ color: "#f87171", fillColor: "#f87171", fillOpacity: 0.15, weight: 2 }}
        >
          <Popup>⚠ {zone.name} — restricted, no waypoints allowed</Popup>
        </Polygon>
      ))}

      {dronePath.length > 1 && (
        <Polyline positions={dronePath} pathOptions={{ color: "#4ade80", weight: 2 }} />
      )}

      {waypoints.length > 1 && (
        <Polyline
          positions={waypoints.map((w) => [w.lat, w.lon] as [number, number])}
          pathOptions={{ color: "#60a5fa", weight: 2, dashArray: "6 6" }}
        />
      )}

      {telemetry && (
        <Marker position={[telemetry.latitude, telemetry.longitude]} icon={droneIcon()}>
          <Popup>
            Drone — alt {telemetry.altitude_m.toFixed(1)}m, battery {telemetry.battery_pct.toFixed(0)}%
          </Popup>
        </Marker>
      )}

      {hazards.map((h, i) => (
        <Marker key={i} position={[h.latitude, h.longitude]} icon={hazardIcon(h.status)}>
          <Popup>
            {h.object_class} ({(h.confidence * 100).toFixed(0)}%) — {h.status}
          </Popup>
        </Marker>
      ))}

      {waypoints.map((w, i) => (
        <Marker
          key={w.id}
          position={[w.lat, w.lon]}
          icon={waypointIcon(i, w.id === selectedWaypointId)}
          draggable={planningMode}
          eventHandlers={{
            click: () => selectWaypoint(w.id),
            dragend: (e) => {
              const marker = e.target;
              const { lat, lng } = marker.getLatLng();
              updateWaypoint(w.id, { lat, lon: lng });
            },
          }}
        >
          <Popup>
            <div>
              Waypoint {i + 1} — alt {w.altitude_m}m, hover {w.hover_s}s
              {planningMode && <><br /><em>Drag to reposition</em></>}
              <br />
              <button onClick={() => removeWaypoint(w.id)}>Remove</button>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
