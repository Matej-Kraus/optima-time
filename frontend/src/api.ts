// Types mirror backend/optima_time/config/models.py and fields/models.py (subset the UI edits).

export type Point = [number, number];

export interface Roi {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type FieldType = "clock" | "number" | "period";

export interface FieldConfig {
  type: FieldType;
  id: string;
  label: string;
  roi: Roi;
  enabled: boolean;
  [key: string]: unknown; // type-specific options are kept as the backend sends them
}

export interface Profile {
  schema_version: number;
  name: string;
  source: { type: string; path: string; [key: string]: unknown };
  geometry: { corners: Point[]; rotate: number; max_width: number };
  fields: FieldConfig[];
}

export type ReadStatus = "valid" | "invalid" | "low_confidence" | "blank";

export interface FieldState {
  status: ReadStatus;
  text: string | null;
  raw: string | null;
  confidence: number | null;
  contrast: number;
}

export interface LiveState {
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
  rectified_size: [number, number] | null;
  fields: Record<string, FieldState>;
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

export const api = {
  getProfile: () => fetch("/api/profile").then((r) => json<Profile>(r)),
  putProfile: (profile: Profile) =>
    fetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    }).then((r) => json<Profile>(r)),
  getState: () => fetch("/api/state").then((r) => json<LiveState>(r)),
  frameUrl: (view: "source" | "rectified", tick: number) =>
    `/api/frame.jpg?view=${view}&max_width=960&t=${tick}`,
  cropUrl: (id: string, tick: number) => `/api/crop/${encodeURIComponent(id)}.png?t=${tick}`,
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
