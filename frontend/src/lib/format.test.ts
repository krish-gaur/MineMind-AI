import { describe, expect, it } from "vitest";
import {
  addDays,
  formatDate,
  formatHours,
  formatMonth,
  formatNumber,
  formatPercent,
  formatSignedPercent,
  formatSignedTonnes,
  formatTonnes,
} from "./format";

describe("number formatting", () => {
  it("groups thousands and rounds to the requested digits", () => {
    expect(formatNumber(5278130.9)).toBe("5,278,131");
    expect(formatNumber(1234.567, 2)).toBe("1,234.57");
  });

  it("uses a true minus sign for negative values and never shows -0", () => {
    expect(formatSignedTonnes(-597725.9, 0)).toBe("\u2212597,726 t");
    expect(formatSignedTonnes(0.2, 0)).toBe("0 t");
    expect(formatSignedPercent(-11.32)).toBe("\u221211.3%");
    expect(formatSignedPercent(4.04)).toBe("+4.0%");
  });

  it("returns n/a for missing or non-finite values instead of inventing numbers", () => {
    expect(formatNumber(null)).toBe("n/a");
    expect(formatNumber(undefined)).toBe("n/a");
    expect(formatNumber(Number.NaN)).toBe("n/a");
    expect(formatTonnes(null)).toBe("n/a");
    expect(formatPercent(null)).toBe("n/a");
    expect(formatHours(undefined)).toBe("n/a");
  });

  it("formats tonnes, percentages and hours with units", () => {
    expect(formatTonnes(4680405)).toBe("4,680,405 t");
    expect(formatPercent(88.68)).toBe("88.7%");
    expect(formatHours(3.1456, 2)).toBe("3.15 h");
  });
});

describe("date formatting", () => {
  it("formats ISO dates without timezone shifts", () => {
    expect(formatDate("2026-09-30")).toBe("30 Sep 2026");
    expect(formatDate("2026-01-01")).toBe("01 Jan 2026");
    expect(formatDate(null)).toBe("n/a");
  });

  it("formats month keys and adds days across month boundaries", () => {
    expect(formatMonth("2026-09")).toBe("Sep 2026");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(addDays("2026-09-30", 30)).toBe("2026-10-30");
  });
});
