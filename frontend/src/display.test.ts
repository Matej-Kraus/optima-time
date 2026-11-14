import { describe, expect, it } from "vitest";
import { chartPaths, splitTenths } from "./display";

describe("display helpers", () => {
  it("splits tenths off the clock", () => {
    expect(splitTenths("18:42.4")).toEqual(["18:42", ".4"]);
    expect(splitTenths("0:42")).toEqual(["0:42", ""]);
    expect(splitTenths("")).toEqual(["", ""]);
  });
  it("draws the anchor chart newest on the right and breaks on gaps", () => {
    const pts = [
      { ago: 0, score: 1, state: "ok" },
      { ago: 1, score: 0.75, state: "ok" },
      { ago: 2, score: null, state: "lost" },
      { ago: 3, score: 1, state: "ok" },
      { ago: 4, score: 1, state: "ok" },
    ];
    const paths = chartPaths(pts, 240, 100);
    expect(paths).toHaveLength(2);
    expect(paths[1]).toBe("230.0,50.0 240.0,0.0");
  });
});
