import { describe, expect, it } from "vitest";
import { cs } from "./cs";

describe("cs texts", () => {
  it("has no empty strings", () => {
    for (const value of Object.values(cs)) {
      expect(value.trim()).not.toBe("");
    }
  });
});
