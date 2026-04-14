import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatRelativeTime } from "./mappers";

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-14T21:55:00.000+03:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("treats naive ISO timestamps from the backend as UTC", () => {
    expect(formatRelativeTime("2026-04-14T18:54:40.000")).toMatch(/^\d{2}:\d{2}(?:\s?[AP]M)?$/u);
  });

  it("formats older timestamps as calendar dates instead of relative labels", () => {
    expect(formatRelativeTime("2026-04-12T18:56:10.000Z")).toBe("Apr 12");
  });
});
