import { useState } from "react";
import { useMissionStore } from "./store";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function MissionPlanner({
  planningMode,
  setPlanningMode,
}: {
  planningMode: boolean;
  setPlanningMode: (v: boolean) => void;
}) {
  const waypoints = useMissionStore((s) => s.waypoints);
  const updateWaypoint = useMissionStore((s) => s.updateWaypoint);
  const removeWaypoint = useMissionStore((s) => s.removeWaypoint);
  const clearWaypoints = useMissionStore((s) => s.clearWaypoints);
  const selectedWaypointId = useMissionStore((s) => s.selectedWaypointId);
  const selectWaypoint = useMissionStore((s) => s.selectWaypoint);

  const [missionName, setMissionName] = useState("Mission " + new Date().toLocaleDateString());
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedMissionId, setUploadedMissionId] = useState<number | null>(null);

  async function handleUpload() {
    setUploadStatus("uploading");
    setUploadError(null);

    const payload = {
      name: missionName,
      waypoints: waypoints.map((w, i) => ({
        seq: i,
        latitude: w.lat,
        longitude: w.lon,
        altitude_m: w.altitude_m,
        hover_s: w.hover_s,
      })),
    };

    try {
      const res = await fetch(`${BACKEND_URL}/missions/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = await res.text();
        try {
          detail = JSON.parse(detail).detail || detail; // FastAPI's {"detail": "..."} shape
        } catch {
          /* not JSON, use raw text */
        }
        throw new Error(detail);
      }
      const mission = await res.json();
      setUploadedMissionId(mission.id);
      setUploadStatus("success");
    } catch (e: any) {
      setUploadStatus("error");
      setUploadError(e.message || "Could not reach backend");
    }
  }

  return (
    <div className="mission-planner">
      <div className="planner-header">
        <button
          className={`plan-toggle ${planningMode ? "active" : ""}`}
          onClick={() => setPlanningMode(!planningMode)}
        >
          {planningMode ? "Click map to add waypoint (ON)" : "Enable waypoint planning"}
        </button>
        {waypoints.length > 0 && (
          <button className="clear-btn" onClick={clearWaypoints}>
            Clear all
          </button>
        )}
      </div>

      {waypoints.length === 0 ? (
        <p className="muted">No waypoints yet. Enable planning mode and click the map.</p>
      ) : (
        <ul className="waypoint-list">
          {waypoints.map((w, i) => (
            <li
              key={w.id}
              className={`waypoint-row ${w.id === selectedWaypointId ? "selected" : ""}`}
              onClick={() => selectWaypoint(w.id)}
            >
              <span className="wp-index">{i + 1}</span>
              <span className="wp-coords">
                {w.lat.toFixed(5)}, {w.lon.toFixed(5)}
              </span>
              <label>
                Alt
                <input
                  type="number"
                  value={w.altitude_m}
                  onChange={(e) => updateWaypoint(w.id, { altitude_m: Number(e.target.value) })}
                  onClick={(e) => e.stopPropagation()}
                />
                m
              </label>
              <label>
                Hover
                <input
                  type="number"
                  value={w.hover_s}
                  onChange={(e) => updateWaypoint(w.id, { hover_s: Number(e.target.value) })}
                  onClick={(e) => e.stopPropagation()}
                />
                s
              </label>
              <button
                className="remove-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  removeWaypoint(w.id);
                }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        className="mission-name-input"
        value={missionName}
        onChange={(e) => setMissionName(e.target.value)}
        placeholder="Mission name"
      />

      <button
        className="upload-btn"
        disabled={waypoints.length === 0 || uploadStatus === "uploading"}
        onClick={handleUpload}
      >
        {uploadStatus === "uploading" ? "Uploading..." : `Upload Mission (${waypoints.length} waypoints)`}
      </button>

      {uploadStatus === "success" && (
        <p className="upload-success">
          Saved as mission #{uploadedMissionId}. Run drone-sim/mission.py --mission-id {uploadedMissionId} to fly it.
        </p>
      )}
      {uploadStatus === "error" && (
        <p className="upload-error">Upload failed: {uploadError}</p>
      )}
    </div>
  );
}
