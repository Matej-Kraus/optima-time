import { describe, expect, it } from "vitest";
import { magnifierOffset } from "./magnifier";

describe("magnifier", () => {
  it("centers the point under the cursor", () => {
    // image 800x450 shown, zoom 4 -> 3200x1800; point (0.25, 0.5) is at (800, 900) zoomed
    const [bx, by] = magnifierOffset([0.25, 0.5], 800, 450, 4, 160);
    expect(800 + bx).toBe(80); // lands in the middle of the 160 px lens
    expect(900 + by).toBe(80);
  });
});
