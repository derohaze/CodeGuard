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
    expect(formatRelativeTime("2026-04-14T18:54:40.000")).toBe("now");
  });

  it("clamps future timestamps to now instead of showing negative drift", () => {
    expect(formatRelativeTime("2026-04-14T18:56:10.000Z")).toBe("now");
  });
});
