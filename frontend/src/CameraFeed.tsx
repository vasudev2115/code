import { useMissionStore } from "./store";

function statusColor(status: string) {
  if (status === "high_priority_area_of_interest") return "#f87171";
  if (status === "area_of_interest") return "#fbbf24";
  return "#4ade80";
}

/**
 * Shows the live detection stream as a list with color-coded status,
 * matching the severity colors used on the map and timeline. This
 * panel does NOT render actual video frames -- streaming a live MJPEG/
 * WebRTC feed from detect_webcam.py into the browser is a separate,
 * larger piece of plumbing (would need the vision script to also run
 * a small video server). This gives you the detection stream now;
 * wiring an actual video element is a good next increment once this
 * is working.
 */
export default function CameraFeed() {
  const detections = useMissionStore((s) => s.detections);

  return (
    <div className="camera-feed">
      <div className="camera-placeholder">
        <span className="muted">
          Live video overlay not wired yet -- run detect_webcam.py locally to see the annotated
          feed in its own window. This panel shows the same detections it's posting to the backend.
        </span>
      </div>
      <ul className="detection-stream">
        {detections.slice(0, 15).map((d, i) => (
          <li key={i} style={{ borderLeft: `3px solid ${statusColor(d.status)}` }}>
            <span className="det-label">{d.object_class}</span>
            <span className="det-conf">{(d.confidence * 100).toFixed(0)}%</span>
            <span className="det-status" style={{ color: statusColor(d.status) }}>
              {d.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
