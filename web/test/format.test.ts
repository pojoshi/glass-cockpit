import { describe, expect, it } from "vitest";
import { driftLabel, formatCents, formatTokens, kindLabel, timeAgo } from "../src/format";

describe("formatCents", () => {
  it("renders fractional cents, since a single step costs less than one", () => {
    expect(formatCents(0.63)).toBe("$0.006");
    expect(formatCents(250)).toBe("$2.500");
  });
});

describe("formatTokens", () => {
  it("abbreviates past 1000", () => {
    expect(formatTokens(180)).toBe("180");
    expect(formatTokens(2100)).toBe("2.1k");
  });
});

describe("driftLabel", () => {
  it("buckets the 0-1 score into readable labels", () => {
    expect(driftLabel(0)).toBe("clean");
    expect(driftLabel(0.2)).toBe("minor");
    expect(driftLabel(0.4)).toBe("elevated");
    expect(driftLabel(0.8)).toBe("high");
  });
});

describe("timeAgo", () => {
  const now = new Date("2026-01-01T12:00:00Z").getTime();

  it("handles null as never ticked", () => {
    expect(timeAgo(null, now)).toBe("never");
  });

  it("buckets by seconds, minutes, and hours", () => {
    expect(timeAgo("2026-01-01T11:59:58Z", now)).toBe("just now");
    expect(timeAgo("2026-01-01T11:59:15Z", now)).toBe("45s ago");
    expect(timeAgo("2026-01-01T11:55:00Z", now)).toBe("5m ago");
    expect(timeAgo("2026-01-01T10:00:00Z", now)).toBe("2h ago");
  });
});

describe("kindLabel", () => {
  it("maps known event kinds and passes through unknown ones", () => {
    expect(kindLabel("reasoning")).toBe("thinking");
    expect(kindLabel("executed")).toBe("executed");
    expect(kindLabel("mystery")).toBe("mystery");
  });
});
