import { describe, expect, it } from "vitest";
import { eventLevel, eventMatches, translateDetail } from "./events";

describe("event details", () => {
  it("translates longer phrases first", () => {
    expect(translateDetail("unexpected, 3 reads")).toBe("neočekávaná změna, 3 čtení");
    expect(translateDetail("expected, 1 reads")).toBe("očekávaná změna, 1 čtení");
    expect(translateDetail("unexpected: replaced by 5")).toBe("neočekávaná změna: nahrazeno 5");
  });
  it("leaves unknown text alone", () => {
    expect(translateDetail("scores [0.2]")).toBe("scores [0.2]");
  });
});

describe("event log filter", () => {
  const ev = (kind: string, field = "", text = "", detail = "") => ({ kind, field, text, detail });
  it("classifies kinds", () => {
    expect(eventLevel("changed")).toBe("change");
    expect(eventLevel("source_lost")).toBe("bad");
    expect(eventLevel("something_new")).toBe("info");
  });
  it("filters by group and search text", () => {
    expect(eventMatches(ev("changed", "Time", "19:59"), "change", "")).toBe(true);
    expect(eventMatches(ev("guard_lost"), "change", "")).toBe(false);
    expect(eventMatches(ev("guard_lost"), "guard", "")).toBe(true);
    expect(eventMatches(ev("rejected", "scoreh"), "warn", "")).toBe(true);
    expect(eventMatches(ev("changed", "scoreh", "3"), "all", "SCOREH")).toBe(true);
    expect(eventMatches(ev("changed", "scoreh", "3", "unexpected"), "all", "neočekávaná")).toBe(true);
    expect(eventMatches(ev("changed", "scoreh", "3"), "all", "Time")).toBe(false);
  });
});
