import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useMissionStore } from "./store";

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour12: false });
  } catch {
    return ts;
  }
}

function MiniChart({
  data,
  dataKey,
  label,
  unit,
  color,
}: {
  data: any[];
  dataKey: string;
  label: string;
  unit: string;
  color: string;
}) {
  return (
    <div className="chart-block">
      <span className="chart-label">
        {label} {data.length > 0 && `(${data[data.length - 1][dataKey]?.toFixed(1)}${unit})`}
      </span>
      <ResponsiveContainer width="100%" height={70}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2833" />
          <XAxis dataKey="timestamp" tickFormatter={formatTime} hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip
            labelFormatter={formatTime}
            contentStyle={{ background: "#131a22", border: "1px solid #1f2833", fontSize: 12 }}
          />
          <Line type="monotone" dataKey={dataKey} stroke={color} dot={false} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function TelemetryGraphs() {
  const history = useMissionStore((s) => s.telemetryHistory);

  if (history.length === 0) {
    return <p className="muted">Waiting for telemetry history...</p>;
  }

  return (
    <div className="telemetry-graphs">
      <MiniChart data={history} dataKey="battery_pct" label="Battery" unit="%" color="#4ade80" />
      <MiniChart data={history} dataKey="altitude_m" label="Altitude" unit="m" color="#60a5fa" />
      <MiniChart data={history} dataKey="speed_mps" label="Speed" unit="m/s" color="#fbbf24" />
    </div>
  );
}
