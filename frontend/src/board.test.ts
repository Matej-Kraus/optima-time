import { describe, expect, it } from "vitest";
import type { FieldConfig } from "./api";
import { boardLayout } from "./board";

const f = (id: string, type: FieldConfig["type"], label = ""): FieldConfig => ({
  id, type, label, enabled: true, roi: { x: 0, y: 0, w: 1, h: 1 },
});

describe("board layout", () => {
  it("places the production field names", () => {
    const b = boardLayout([
      f("Time", "clock"), f("period", "period"), f("scoreh", "number"), f("scorea", "number"),
      f("penaltyh1", "clock"), f("penaltyh2", "clock"), f("penaltya1", "clock"), f("penaltya2", "clock"),
    ]);
    expect(b.clock?.id).toBe("Time");
    expect(b.period?.id).toBe("period");
    expect([b.home?.id, b.away?.id]).toEqual(["scoreh", "scorea"]);
    expect(b.homePenalties.map((x) => x.id)).toEqual(["penaltyh1", "penaltyh2"]);
    expect(b.awayPenalties.map((x) => x.id)).toEqual(["penaltya1", "penaltya2"]);
    expect(b.other).toEqual([]);
  });

  it("falls back to order and lists the rest", () => {
    const b = boardLayout([f("goly1", "number"), f("goly2", "number"), f("strely", "number")]);
    expect([b.home?.id, b.away?.id]).toEqual(["goly1", "goly2"]);
    expect(b.other.map((x) => x.id)).toEqual(["strely"]);
    expect(b.clock).toBeNull();
  });
});
