import { useEffect, useRef } from "react";
import { useMissionStore } from "./store";

// Matches the backend's typed envelope: {type, timestamp, data}
export interface WsEvent<T = unknown> {
  type: "telemetry" | "detection" | "alert" | "mission_status" | "system_status";
  timestamp: string;
  data: T;
}

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

/** Connects once and streams events into the shared Zustand store.
 * Call this exactly once near the app root (e.g. in App.tsx) --
 * components read live state via useMissionStore(), not via this hook.
 */
export function useMissionSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const setTelemetry = useMissionStore((s) => s.setTelemetry);
  const addDetection = useMissionStore((s) => s.addDetection);
  const addAlert = useMissionStore((s) => s.addAlert);
  const setConnected = useMissionStore((s) => s.setConnected);
  const setMissionStatus = useMissionStore((s) => s.setMissionStatus);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        try {
          const envelope: WsEvent<any> = JSON.parse(event.data);
          switch (envelope.type) {
            case "telemetry":
              setTelemetry(envelope.data);
              break;
            case "detection":
              addDetection(envelope.data);
              break;
            case "alert":
              addAlert(envelope.data);
              break;
            case "mission_status":
              setMissionStatus(envelope.data);
              break;
          }
        } catch (e) {
          console.error("Bad WS message", e);
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [setTelemetry, addDetection, addAlert, setConnected, setMissionStatus]);
}
