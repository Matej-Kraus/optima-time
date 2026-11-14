import { describe, expect, it } from "vitest";
import { FIELD_ID_PATTERN, nextFieldId, rectFromPoints, type FieldConfig } from "./api";

describe("rectFromPoints", () => {
  it("normalizes any drag direction", () => {
    const r = rectFromPoints([0.6, 0.5], [0.2, 0.1]);
    for (const [k, v] of Object.entries({ x: 0.2, y: 0.1, w: 0.4, h: 0.4 })) {
      expect(r[k as keyof typeof r]).toBeCloseTo(v);
    }
  });
  it("clamps to the image", () => {
    const r = rectFromPoints([-0.2, 0.5], [0.3, 1.4]);
    expect(r).toEqual({ x: 0, y: 0.5, w: 0.3, h: 0.5 });
  });
});

describe("field ids", () => {
  it("follows the XML name rule like the backend", () => {
    for (const ok of ["Time", "penaltyh1", "score_h", "a.b-c", "_x"]) expect(FIELD_ID_PATTERN.test(ok)).toBe(true);
    for (const bad of ["1score", "score h", "", "skóre"]) expect(FIELD_ID_PATTERN.test(bad)).toBe(false);
  });
  it("picks the next free id", () => {
    const fields = [{ id: "field1" }, { id: "field3" }] as FieldConfig[];
    expect(nextFieldId(fields)).toBe("field2");
  });
});
