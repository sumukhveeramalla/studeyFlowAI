import { describe, expect, it } from "vitest";
import { fmtDuration, PRIORITY_STYLES, EVENT_COLORS } from "../lib/format";

describe("format utilities", () => {
  it("formats durations", () => {
    expect(fmtDuration(90)).toBe("1h 30m");
    expect(fmtDuration(60)).toBe("1h");
    expect(fmtDuration(45)).toBe("45m");
  });

  it("has styles for every priority", () => {
    expect(PRIORITY_STYLES.high).toBeTruthy();
    expect(PRIORITY_STYLES.medium).toBeTruthy();
    expect(PRIORITY_STYLES.low).toBeTruthy();
  });

  it("has colors for every event kind", () => {
    for (const kind of [
      "class",
      "exam",
      "assignment",
      "study",
      "personal",
      "meeting",
    ] as const) {
      expect(EVENT_COLORS[kind].dot).toBeTruthy();
    }
  });
});
