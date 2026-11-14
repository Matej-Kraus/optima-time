import type { Point } from "./api";

/** Background offset (px) that puts the image point `at` in the middle of the magnifier. */
export function magnifierOffset(at: Point, hostWidth: number, hostHeight: number, zoom: number, size: number): [number, number] {
  return [size / 2 - at[0] * hostWidth * zoom, size / 2 - at[1] * hostHeight * zoom];
}

