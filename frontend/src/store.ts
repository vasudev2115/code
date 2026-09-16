import { create } from "zustand";

export interface TelemetryPoint {
  latitude: number;
  longitude: number;
  altitude_m: number;
  battery_pct: number;
  speed_mps?: number;
  heading_deg?: number;
  timestamp: string;
}

export interface Detection {
  object_class: string;
  confidence: number;
  latitude: number;
  longitude: number;
  status: "routine" | "area_of_interest" | "high_priority_area_of_interest";
  timestamp: string;
}

export interface Alert {
  alert_type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  latitude?: number;
  longitude?: number;
  timestamp: string;
}

export interface Waypoint {
  id: string;
  lat: number;
  lon: number;
  altitude_m: number;
  hover_s: number;
}

export type MissionState =
  | "IDLE" | "ARMED" | "TAKEOFF" | "MISSION" | "OBSERVATION"
  | "RETURN" | "LAND" | "COMPLETE" | "ABORTED";

export interface MissionStatus {
  id: number;
  name: string;
  state: MissionState;
  started_at?: string;
  ended_at?: string;
}

interface MissionStore {
  // Live telemetry
  telemetry: TelemetryPoint | null;
  telemetryHistory: TelemetryPoint[]; // capped, for charts
  setTelemetry: (t: TelemetryPoint) => void;

  // Drone path (for the map polyline)
  dronePath: [number, number][];

  // Detections + alerts
  detections: Detection[];
  addDetection: (d: Detection) => void;
  alerts: Alert[];
  addAlert: (a: Alert) => void;

  // Connection status
  connected: boolean;
  setConnected: (c: boolean) => void;

  // Mission planner
  waypoints: Waypoint[];
  addWaypoint: (lat: number, lon: number) => void;
  updateWaypoint: (id: string, patch: Partial<Waypoint>) => void;
  removeWaypoint: (id: string) => void;
  clearWaypoints: () => void;
  selectedWaypointId: string | null;
  selectWaypoint: (id: string | null) => void;

  // Mission lifecycle
  currentMission: MissionStatus | null;
  setMissionStatus: (m: MissionStatus) => void;
}

const MAX_HISTORY = 200;

export const useMissionStore = create<MissionStore>((set, get) => ({
  telemetry: null,
  telemetryHistory: [],
  setTelemetry: (t) =>
    set((state) => ({
      telemetry: t,
      telemetryHistory: [...state.telemetryHistory, t].slice(-MAX_HISTORY),
      dronePath: [...state.dronePath, [t.latitude, t.longitude]].slice(-500),
    })),

  dronePath: [],

  detections: [],
  addDetection: (d) => set((state) => ({ detections: [d, ...state.detections].slice(0, 100) })),

  alerts: [],
  addAlert: (a) => set((state) => ({ alerts: [a, ...state.alerts].slice(0, 100) })),

  connected: false,
  setConnected: (c) => set({ connected: c }),

  waypoints: [],
  addWaypoint: (lat, lon) =>
    set((state) => ({
      waypoints: [
        ...state.waypoints,
        { id: crypto.randomUUID(), lat, lon, altitude_m: 10, hover_s: 0 },
      ],
    })),
  updateWaypoint: (id, patch) =>
    set((state) => ({
      waypoints: state.waypoints.map((w) => (w.id === id ? { ...w, ...patch } : w)),
    })),
  removeWaypoint: (id) =>
    set((state) => ({
      waypoints: state.waypoints.filter((w) => w.id !== id),
      selectedWaypointId: get().selectedWaypointId === id ? null : get().selectedWaypointId,
    })),
  clearWaypoints: () => set({ waypoints: [], selectedWaypointId: null }),
  selectedWaypointId: null,
  selectWaypoint: (id) => set({ selectedWaypointId: id }),

  currentMission: null,
  setMissionStatus: (m) => set({ currentMission: m }),
}));
