import { useState } from "react";
import { useMissionSocket } from "./useMissionSocket";
import { useMissionStore } from "./store";
import TacticalMap from "./TacticalMap";
import TelemetryGraphs from "./TelemetryGraphs";
import ThreatTimeline from "./ThreatTimeline";
import CameraFeed from "./CameraFeed";
import MissionPlanner from "./MissionPlanner";
import MissionControl from "./MissionControl";
import "./App.css";

export default function App() {
  useMissionSocket(); // connects once, feeds the store
  const connected = useMissionStore((s) => s.connected);
  const telemetry = useMissionStore((s) => s.telemetry);
  const [planningMode, setPlanningMode] = useState(false);
  const [showPlanner, setShowPlanner] = useState(false);

  return (
    <div className="dashboard">
      <header>
        <h1>AEGISNET SENTINEL — TACTICAL OPERATIONS</h1>
        <div className="header-right">
          <button className="planner-toggle" onClick={() => setShowPlanner(!showPlanner)}>
            {showPlanner ? "Hide Mission Planner" : "Mission Planner"}
          </button>
          <span className={`status-pill ${connected ? "online" : "offline"}`}>
            {connected ? "● LINK ONLINE" : "● LINK OFFLINE"}
          </span>
        </div>
      </header>

      <div className="grid">
        <section className="panel map-panel">
          <h2>Live GIS Map</h2>
          <div className="map-wrap">
            <TacticalMap planningMode={planningMode} />
          </div>
        </section>

        {showPlanner && (
          <section className="panel planner-panel">
            <h2>Mission Planner</h2>
            <MissionPlanner planningMode={planningMode} setPlanningMode={setPlanningMode} />
          </section>
        )}

        <section className="panel control-panel">
          <h2>Mission Control</h2>
          <MissionControl />
        </section>

        <section className="panel camera-panel">
          <h2>AI Camera Feed</h2>
          <CameraFeed />
        </section>

        <section className="panel telemetry-strip">
          <div>
            <label>ALT</label>
            <span>{telemetry?.altitude_m?.toFixed(1) ?? "--"}m</span>
          </div>
          <div>
            <label>BATTERY</label>
            <span>{telemetry?.battery_pct?.toFixed(0) ?? "--"}%</span>
          </div>
          <div>
            <label>SPEED</label>
            <span>{telemetry?.speed_mps?.toFixed(1) ?? "--"}m/s</span>
          </div>
          <div>
            <label>LINK</label>
            <span>{connected ? "ONLINE" : "OFFLINE"}</span>
          </div>
        </section>

        <section className="panel graphs-panel">
          <h2>Telemetry History</h2>
          <TelemetryGraphs />
        </section>

        <section className="panel timeline-panel">
          <h2>Threat Timeline</h2>
          <ThreatTimeline />
        </section>
      </div>
    </div>
  );
}
