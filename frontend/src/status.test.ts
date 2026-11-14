import { describe, expect, it } from "vitest";
import type { LiveState } from "./api";
import { lights } from "./status";

function state(patch: Partial<LiveState> = {}): LiveState {
  return {
    source: { state: "ok", fps: 25 },
    processing_fps: 25,
    frame: null,
    guard: { state: "ok", scores: [0.95] },
    outputs: {
      mode: "live",
      workers: {
        xml_file: {
          ok: true, message: "", writes: 3, failures: 0, slow_writes: 0, last_ok_wall: 1,
          last_write_ms: 1, max_write_ms: 2, last_latency_ms: 30, target: "x.xml",
        },
      },
    },
    rectified_size: null,
    fields: {},
    ...patch,
  };
}

describe("traffic light", () => {
  it("is all green when everything works", () => {
    const r = lights(state());
    expect(r.problems).toEqual([]);
    expect(r.lights.map((l) => l.level)).toEqual(["ok", "ok", "ok", "ok"]);
  });

  it("explains a lost source and a failing write in plain words", () => {
    const s = state({ source: { state: "lost" } });
    s.outputs.workers.xml_file.ok = false;
    s.outputs.workers.xml_file.message = "PermissionError";
    const r = lights(s);
    expect(r.problems.map((p) => p.level)).toEqual(["bad", "bad"]);
    expect(r.problems[1].text).toContain("PermissionError");
  });

  it("warns when paused, slow, guard lost or no output", () => {
    const r = lights(
      state({
        processing_fps: 10,
        guard: { state: "lost", scores: [0.2] },
        outputs: { mode: "paused", workers: {} },
      }),
    );
    expect(r.problems.length).toBe(4);
    expect(r.problems.every((p) => p.level === "warn")).toBe(true);
  });

  it("reports a missing backend", () => {
    expect(lights(null).problems[0].level).toBe("bad");
  });
});
