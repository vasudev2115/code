import { useState } from "react";
import { useMissionStore } from "./store";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const STATE_COLOR: Record<string, string> = {
  IDLE: "#8b98a5",
  ARMED: "#60a5fa",
  TAKEOFF: "#60a5fa",
  MISSION: "#4ade80",
  OBSERVATION: "#4ade80",
  RETURN: "#fbbf24",
  LAND: "#fbbf24",
  COMPLETE: "#4ade80",
  ABORTED: "#f87171",
};

/**
 * Start/Abort update the mission's tracked state in the backend and
 * broadcast it live over WebSocket. As of this version, Abort ALSO
 * reaches a live mission.py flight: mission.py polls the backend every
 * ~2 seconds for a remote abort and will interrupt its current
 * waypoint hold, then proceed through RETURN -> LAND safely. That
 * poll interval means there's a real (up to ~2s) delay between
 * clicking Abort and the drone reacting -- not instant, but genuine.
 *
 * "Start" only matters for tracking purposes -- it doesn't remotely
 * launch a mission.py process on your machine. You still run
 * `python mission.py --mission-id N` yourself to actually fly.
 */
export default function MissionControl() {
  const currentMission = useMissionStore((s) => s.currentMission);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function callTransition(action: "start" | "abort" | "complete") {
    if (!currentMission) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/missions/${currentMission.id}/${action}`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      // No need to setMissionStatus manually -- the backend broadcasts
      // mission_status over WebSocket, which useMissionSocket picks up.
    } catch (e: any) {
      setError(e.message || "Could not reach backend");
    } finally {
      setBusy(false);
    }
  }

  if (!currentMission) {
    return (
      <div className="mission-control">
        <p className="muted">
          No mission tracked yet. Upload a mission in the planner, or start one via the API.
        </p>
      </div>
    );
  }

  const color = STATE_COLOR[currentMission.state] || "#8b98a5";
  const canStart = currentMission.state === "IDLE";
  const canAbort = !["IDLE", "COMPLETE", "ABORTED"].includes(currentMission.state);

  return (
    <div className="mission-control">
      <div className="mc-header">
        <span className="mc-name">{currentMission.name}</span>
        <span className="mc-state" style={{ color, borderColor: color }}>
          {currentMission.state}
        </span>
      </div>

      <div className="mc-buttons">
        <button disabled={!canStart || busy} onClick={() => callTransition("start")}>
          Start
        </button>
        <button className="mc-abort" disabled={!canAbort || busy} onClick={() => callTransition("abort")}>
          Abort
        </button>
      </div>

      {error && <p className="upload-error">{error}</p>}

      <p className="muted small">
        Abort reaches a live mission.py flight within ~2s (it polls the backend).
        Start only updates tracked state -- you still run mission.py yourself to fly.
      </p>
    </div>
  );
}
