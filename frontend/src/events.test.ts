import { describe, expect, it } from "vitest";
import { translateDetail } from "./events";

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
