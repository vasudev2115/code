import { useState } from "react";
import { useMissionStore, Alert, Detection } from "./store";

type Severity = "info" | "warning" | "critical" | "all";

function detectionToSeverity(d: Detection): "info" | "warning" | "critical" {
  if (d.status === "high_priority_area_of_interest") return "critical";
  if (d.status === "area_of_interest") return "warning";
  return "info";
}

export default function ThreatTimeline() {
  const alerts = useMissionStore((s) => s.alerts);
  const detections = useMissionStore((s) => s.detections);
  const [filter, setFilter] = useState<Severity>("all");

  type TimelineEntry = { timestamp: string; severity: "info" | "warning" | "critical"; label: string };

  const entries: TimelineEntry[] = [
    ...alerts.map((a: Alert) => ({ timestamp: a.timestamp, severity: a.severity, label: `[${a.alert_type}] ${a.message}` })),
    ...detections
      .filter((d) => d.status !== "routine")
      .map((d: Detection) => ({
        timestamp: d.timestamp,
        severity: detectionToSeverity(d),
        label: `${d.object_class} flagged (${(d.confidence * 100).toFixed(0)}%)`,
      })),
  ]
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 100);

  const filtered = filter === "all" ? entries : entries.filter((e) => e.severity === filter);

  return (
    <div className="threat-timeline">
      <div className="timeline-filters">
        {(["all", "info", "warning", "critical"] as Severity[]).map((s) => (
          <button
            key={s}
            className={`filter-btn ${filter === s ? "active" : ""}`}
            onClick={() => setFilter(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <ul className="timeline-list">
        {filtered.length === 0 && <li className="muted">No events.</li>}
        {filtered.map((e, i) => (
          <li key={i} className={`timeline-entry sev-${e.severity}`}>
            <span className="timeline-time">
              {new Date(e.timestamp).toLocaleTimeString([], { hour12: false })}
            </span>
            <span className="timeline-label">{e.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
