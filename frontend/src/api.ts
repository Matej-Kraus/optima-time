// Types mirror backend/optima_time (config/models.py, fields/models.py, api/app.py).

export type Point = [number, number];

export interface Roi {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type FieldType = "clock" | "number" | "period" | "indicator";

export interface FieldConfig {
  type: FieldType;
  id: string;
  label: string;
  roi: Roi;
  enabled: boolean;
  [key: string]: unknown; // type-specific options are kept as the backend sends them
}

export interface DerivedField {
  id: string;
  template: string;
  enabled: boolean;
}

export interface ImageConfig {
  brightness: number;
  contrast: number;
  gamma: number;
  sharpen: number;
  net_removal: number;
  invert: boolean;
}

export const NEUTRAL_IMAGE: ImageConfig = { brightness: 0, contrast: 1, gamma: 1, sharpen: 0, net_removal: 0, invert: false };

export interface GuardHistory {
  threshold: number;
  points: { ago: number; score: number | null; state: string }[];
}

export interface SourceConfig {
  type: "file" | "ndi" | "device" | "stream";
  path: string;
  url: string;
  loop: boolean;
  speed: number;
  ndi_name: string;
  device_index: number;
  device_name: string;
  width: number;
  height: number;
  fps: number;
  fourcc: string;
  deinterlace: "none" | "blend" | "bob";
}

export interface DeviceInfo {
  index: number;
  name: string;
  backend: string;
}

export interface SourcesList {
  ndi: string[] | null;
  ndi_error: string | null;
  devices: DeviceInfo[];
}

export interface ProfilesList {
  current: { name: string; path: string | null };
  profiles: { name: string; path: string; modified: string }[];
  folder: string;
}

export interface RecorderStatus {
  active: boolean;
  folder: string;
  seconds: number;
  frames: number;
  dropped: number;
  error: string | null;
}

export interface Anchor {
  roi: Roi;
  template: string;
}

export interface Profile {
  schema_version: number;
  name: string;
  source: SourceConfig;
  geometry: { corners: Point[]; rotate: number; max_width: number };
  fields: FieldConfig[];
  derived: DerivedField[];
  guard: { anchors: Anchor[]; threshold: number; recover_frames: number; search_margin: number };
  preprocess: { blend_frames: number; blend_mode: "max" | "mean" };
  image: ImageConfig;
  detection: { enabled: boolean; threshold: number; max_age_ms: number };
  outputs: { xml_file: { enabled: boolean; path: string; newline: string; clear_on_exit: boolean }; delay_ms: number };
}

export type ReadStatus = "valid" | "invalid" | "low_confidence" | "blank";
export type FieldStatus = "new" | "same" | "pending" | "rejected" | "blank" | "stale" | "held";

export interface FieldState {
  text: string; // published
  status: FieldStatus;
  held: boolean;
  pending: string | null;
  read_status: ReadStatus | null;
  read_text: string | null;
  raw: string | null;
  confidence: number | null;
  contrast: number | null;
}

export interface OutputStatus {
  ok: boolean | null;
  message: string;
  writes: number;
  failures: number;
  slow_writes: number;
  last_ok_wall: number | null;
  last_write_ms: number | null;
  max_write_ms: number;
  last_latency_ms: number | null;
  target: string;
}

export type OutputMode = "live" | "paused" | "test";

export interface LiveState {
  version?: string;
  source: {
    state: string;
    width?: number;
    height?: number;
    fps?: number;
    received?: number;
    dropped?: number;
    error?: string | null;
  };
  processing_fps: number;
  frame: { seq: number; pts: number | null; timings_ms: Record<string, number> } | null;
  guard: { state: "off" | "ok" | "lost" | "recovering"; scores: number[] } | null;
  outputs: { mode: OutputMode; workers: Record<string, OutputStatus> };
  rectified_size: [number, number] | null;
  fields: Record<string, FieldState>;
  locked?: boolean;
  last_test_wall?: number | null;
  derived?: Record<string, string>;
  process?: {
    cpu_percent: number;
    cpu_count: number;
    rss_mb: number;
    threads: number;
    supervisor_restarts: number;
    pipeline_stuck: boolean;
    frame_jitter_ms: number | null;
    frame_ms_p50: number | null;
    frame_ms_p95: number | null;
  };
}

export interface LoggedEvent {
  wall: string;
  mono_ns: number;
  kind: string;
  field: string;
  text: string;
  detail: string;
}

export class ApiError extends Error {
  detail: unknown;
  constructor(message: string, detail: unknown) {
    super(message);
    this.detail = detail;
  }
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(`HTTP ${response.status}`, body?.detail ?? body);
  }
  return (await response.json()) as T;
}

const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const api = {
  getProfile: () => fetch("/api/profile").then((r) => json<Profile>(r)),
  putProfile: (profile: Profile) =>
    fetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    }).then((r) => json<Profile>(r)),
  getState: () => fetch("/api/state").then((r) => json<LiveState>(r)),
  getProfiles: () => fetch("/api/profiles").then((r) => json<ProfilesList>(r)),
  loadProfile: (name: string) => post("/api/profiles/load", { name }).then(json),
  saveProfileAs: (name: string) => post("/api/profiles/save-as", { name }).then(json),
  importProfile: (name: string, profile: unknown) => post("/api/profiles/import", { name, profile }).then(json),
  exportUrl: "/api/profiles/export",
  diagnosticsUrl: "/api/diagnostics.zip",
  recordSample: (seconds: number) => post("/api/samples/record", { seconds }).then((r) => json<RecorderStatus>(r)),
  sampleStatus: () => fetch("/api/samples/status").then((r) => json<RecorderStatus>(r)),
  previewUrl: (view: "source" | "rectified", key = 0) => `/api/preview.mjpg?view=${view}&fps=8&max_width=960&k=${key}`,
  getSources: () => fetch("/api/sources").then((r) => json<SourcesList>(r)),
  getEvents: (limit = 50) => fetch(`/api/events?limit=${limit}`).then((r) => json<LoggedEvent[]>(r)),
  getXml: () => fetch("/data/values.xml").then((r) => r.text()),
  hold: (id: string, text: string) => post(`/api/fields/${encodeURIComponent(id)}/hold`, { text }).then(json),
  release: (id: string) => post(`/api/fields/${encodeURIComponent(id)}/release`).then(json),
  clearValues: () => post("/api/values/clear").then(json),
  output: (action: "pause" | "live" | "test" | "test-clear") => post(`/api/output/${action}`).then(json),
  addAnchor: (roi: Roi) => post("/api/anchors", { roi }).then((r) => json<Profile>(r)),
  autoAnchors: () => post("/api/anchors/auto").then((r) => json<Profile>(r)),
  updateAnchor: (i: number, roi: Roi) =>
    fetch(`/api/anchors/${i}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ roi }),
    }).then((r) => json<Profile>(r)),
  deleteAnchor: (i: number) => fetch(`/api/anchors/${i}`, { method: "DELETE" }).then((r) => json<Profile>(r)),
  frameUrl: (view: "source" | "rectified", tick: number) => `/api/frame.jpg?view=${view}&max_width=960&t=${tick}`,
  cropUrl: (id: string, tick: number, mode: "raw" | "otsu" = "raw") =>
    `/api/crop/${encodeURIComponent(id)}.png?mode=${mode}&t=${tick}`,
  lock: (locked: boolean) => post("/api/lock", { locked }).then((r) => json<{ locked: boolean }>(r)),
  guardHistory: () => fetch("/api/guard/history").then((r) => json<GuardHistory>(r)),
};

// XML element name rule, same as the backend (fields/models.py FIELD_ID_PATTERN)
export const FIELD_ID_PATTERN = /^[A-Za-z_][A-Za-z0-9_.-]*$/;

export function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

/** A rectangle from two corner points, normalized and clamped to 0-1. */
export function rectFromPoints(a: Point, b: Point): Roi {
  const x0 = clamp01(Math.min(a[0], b[0]));
  const y0 = clamp01(Math.min(a[1], b[1]));
  const x1 = clamp01(Math.max(a[0], b[0]));
  const y1 = clamp01(Math.max(a[1], b[1]));
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** The next free id like "field1", "field2". */
export function nextFieldId(fields: FieldConfig[], base = "field"): string {
  const ids = new Set(fields.map((f) => f.id));
  let i = 1;
  while (ids.has(`${base}${i}`)) i++;
  return `${base}${i}`;
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    if (Array.isArray(e.detail)) {
      // pydantic: [{loc, msg}] -> readable lines
      return e.detail
        .map((d: { msg?: string; loc?: unknown[] }) => {
          const msg = String(d.msg ?? "").replace(/^Value error, /, "");
          const where = (d.loc ?? []).filter((x) => x !== "body").join(".");
          return where ? `${where}: ${msg}` : msg;
        })
        .join("; ");
    }
    return JSON.stringify(e.detail);
  }
  return String(e);
}
