import { describe, expect, it } from "vitest";
import { applyDrag, nudge } from "./roiEdit";

const r = { x: 0.2, y: 0.2, w: 0.3, h: 0.2 };
const close = (a: object, b: object) =>
  Object.entries(b).forEach(([k, v]) => expect((a as Record<string, number>)[k]).toBeCloseTo(v as number));

describe("editing rectangles", () => {
  it("moves and stays inside the image", () => {
    close(applyDrag(r, "move", [0.5, 0.5], [0.6, 0.55]), { x: 0.3, y: 0.25, w: 0.3, h: 0.2 });
    close(applyDrag(r, "move", [0.5, 0.5], [1.5, 1.5]), { x: 0.7, y: 0.8, w: 0.3, h: 0.2 });
  });
  it("resizes by a corner and never collapses", () => {
    close(applyDrag(r, "se", [0.5, 0.4], [0.6, 0.5]), { x: 0.2, y: 0.2, w: 0.4, h: 0.3 });
    close(applyDrag(r, "nw", [0.2, 0.2], [0.1, 0.15]), { x: 0.1, y: 0.15, w: 0.4, h: 0.25 });
    const tiny = applyDrag(r, "se", [0.5, 0.4], [0.0, 0.0]);
    expect(tiny.w).toBeCloseTo(0.01);
    expect(tiny.h).toBeCloseTo(0.01);
  });
  it("nudges by pixels", () => {
    close(nudge(r, 10, -5, [1000, 500]), { x: 0.21, y: 0.19 });
  });
});
