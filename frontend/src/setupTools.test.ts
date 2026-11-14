import { describe, expect, it } from "vitest";
import type { FieldConfig, LiveState, Profile } from "./api";
import { addTemplate, compareNames, FLOORBALL, readiness, xmlLeafNames } from "./setupTools";

describe("floorball template", () => {
  it("adds only the missing fields, ignoring case", () => {
    const have = [{ ...FLOORBALL[0], id: "time" }] as FieldConfig[];
    const { fields, added } = addTemplate(have);
    expect(added).toHaveLength(7);
    expect(added).not.toContain("Time");
    expect(fields).toHaveLength(8);
    expect(addTemplate(fields).added).toEqual([]);
  });
  it("has the usual ids and penalties clear when empty", () => {
    expect(FLOORBALL.map((f) => f.id)).toEqual(["Time", "period", "scoreh", "scorea", "penaltyh1", "penaltyh2", "penaltya1", "penaltya2"]);
    expect(FLOORBALL.filter((f) => f.blank === "clear")).toHaveLength(4);
  });
});

describe("XML names", () => {
  it("lists value elements of a vMix data file", () => {
    const xml = '<?xml version="1.0" encoding="utf-8"?>\r\n<root>\r\n  <Time>19:59</Time>\r\n  <penaltya1/>\r\n  <scoreh>3</scoreh>\r\n  <!-- <old>x</old> -->\r\n</root>';
    expect(xmlLeafNames(xml)).toEqual(["Time", "penaltya1", "scoreh"]);
    expect(xmlLeafNames("<root/>")).toEqual(["root"]);
    expect(xmlLeafNames("nonsense")).toEqual([]);
  });
  it("finds case mismatches, missing and extra fields", () => {
    const r = compareNames(["Time", "scoreh", "Period", "shots"], ["Time", "scoreh", "period", "scorea"]);
    expect(r.ok).toEqual(["Time", "scoreh"]);
    expect(r.caseOnly).toEqual([{ ours: "period", theirs: "Period" }]);
    expect(r.missing).toEqual(["shots"]);
    expect(r.extra).toEqual(["scorea"]);
  });
});

describe("readiness", () => {
  const profile = {
    name: "hala",
    fields: [{ ...FLOORBALL[2] }],
    guard: { anchors: [{ roi: { x: 0, y: 0, w: 0.1, h: 0.1 }, template: "" }] },
    outputs: { xml_file: { path: "C:/t.xml" } },
  } as unknown as Profile;
  const live = {
    source: { state: "ok" },
    guard: { state: "ok", scores: [0.95] },
    outputs: { mode: "live", workers: { xml_file: { ok: true } } },
    fields: { scoreh: { status: "same", read_status: "valid" } },
    last_test_wall: 1,
    locked: false,
  } as unknown as LiveState;
  it("is all green for a finished setup except the recommended lock", () => {
    const items = readiness(profile, live);
    expect(items.filter((i) => !i.ok).map((i) => i.key)).toEqual(["lock"]);
    expect(items.find((i) => i.key === "lock")?.required).toBe(false);
  });
  it("flags what's missing", () => {
    const bad = { ...live, last_test_wall: null, outputs: { mode: "paused", workers: {} } } as unknown as LiveState;
    const missing = readiness(profile, bad).filter((i) => !i.ok).map((i) => i.key);
    expect(missing).toEqual(["xml", "test", "live", "lock"]);
    expect(readiness(profile, null).every((i) => !i.ok || i.key === "fields" || i.key === "profile")).toBe(true);
  });
});
