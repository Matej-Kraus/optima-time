import { describe, expect, it } from "vitest";
import { formatNames, parseNames } from "./periodNames";

describe("period names", () => {
  it("parses and formats", () => {
    const names = parseNames("1=1. tretina; 4 = predĺženie ;");
    expect(names).toEqual({ 1: "1. tretina", 4: "predĺženie" });
    expect(formatNames(names)).toBe("1=1. tretina; 4=predĺženie");
    expect(parseNames("")).toEqual({});
  });
  it("rejects nonsense", () => {
    expect(parseNames("prvni")).toBeNull();
    expect(parseNames("12=x")).toBeNull();
  });
});
