import { describe, expect, it } from "vitest";
import { cs } from "./cs";

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (value && typeof value === "object") return Object.values(value).flatMap(strings);
  return [];
}

describe("cs texts", () => {
  it("has no empty strings, also in nested groups", () => {
    const all = strings(cs);
    expect(all.length).toBeGreaterThan(20);
    for (const value of all) expect(value.trim()).not.toBe("");
  });
});
