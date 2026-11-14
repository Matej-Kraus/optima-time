import { clamp01, type Point, type Roi } from "./api";

/** What a drag on a rectangle does: move it, or resize it by one corner. */
export type DragMode = "move" | "nw" | "ne" | "sw" | "se";

const MIN = 0.01; // smallest width/height (relative)

/** The rectangle after dragging from `start` to `now` (relative coordinates), kept inside the
 * image and never smaller than MIN. */
export function applyDrag(orig: Roi, mode: DragMode, start: Point, now: Point): Roi {
  const dx = now[0] - start[0];
  const dy = now[1] - start[1];
  if (mode === "move") {
    const x = Math.min(Math.max(0, orig.x + dx), 1 - orig.w);
    const y = Math.min(Math.max(0, orig.y + dy), 1 - orig.h);
    return { x, y, w: orig.w, h: orig.h };
  }
  let x0 = orig.x;
  let y0 = orig.y;
  let x1 = orig.x + orig.w;
  let y1 = orig.y + orig.h;
  if (mode === "nw" || mode === "sw") x0 = Math.min(clamp01(x0 + dx), x1 - MIN);
  if (mode === "ne" || mode === "se") x1 = Math.max(clamp01(x1 + dx), x0 + MIN);
  if (mode === "nw" || mode === "ne") y0 = Math.min(clamp01(y0 + dy), y1 - MIN);
  if (mode === "sw" || mode === "se") y1 = Math.max(clamp01(y1 + dy), y0 + MIN);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** Move a rectangle by whole pixels of an image of `size` (arrow keys). */
export function nudge(orig: Roi, dxPx: number, dyPx: number, size: [number, number]): Roi {
  return applyDrag(orig, "move", [0, 0], [dxPx / size[0], dyPx / size[1]]);
}

export function corners(r: Roi): [DragMode, number, number][] {
  return [
    ["nw", r.x, r.y],
    ["ne", r.x + r.w, r.y],
    ["sw", r.x, r.y + r.h],
    ["se", r.x + r.w, r.y + r.h],
  ];
}
