import { afterEach, describe, expect, it, vi } from "vitest";
import { generateFix, getRepoHotspots, getTeamPostureSummary } from "./security";

describe("security API error handling", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("preserves backend detail messages for remediation failures", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: vi.fn().mockResolvedValue({
        detail: "Khwarizm could not complete remediation analysis because the AI runtime was temporarily unavailable. Retry shortly.",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(
      generateFix({
        sessionId: "session-1",
        findingId: "finding-1",
      }),
    ).rejects.toThrow(
      "Khwarizm could not complete remediation analysis because the AI runtime was temporarily unavailable. Retry shortly.",
    );
  });

  it("falls back to the HTTP status message when the response body is not usable", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: vi.fn().mockRejectedValue(new Error("invalid json")),
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(
      generateFix({
        sessionId: "session-1",
        findingId: "finding-1",
      }),
    ).rejects.toThrow("Request failed with status 503");
  });

  it("maps repo hotspot feed responses into frontend-friendly items", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: vi.fn().mockReturnValue("application/json"),
      },
      json: vi.fn().mockResolvedValue({
        items: [
          {
            session_id: "session-1",
            repo: "secure-scan-studio-main",
            hotspot_class: "identity-zone",
            priority: "critical",
            label: "Critical identity zone",
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getRepoHotspots()).resolves.toEqual([
      {
        sessionId: "session-1",
        repo: "secure-scan-studio-main",
        hotspotClass: "identity-zone",
        priority: "critical",
        label: "Critical identity zone",
      },
    ]);
  });

  it("maps team posture summary responses into camel-case fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: vi.fn().mockReturnValue("application/json"),
      },
      json: vi.fn().mockResolvedValue({
        session_count: 10,
        hotspot_count: 4,
        critical_hotspots: 2,
        control_drag: 3,
        risk_drag: 4,
        coverage_drag: 1,
        throughput_drag: 2,
        top_hotspot_label: "critical - auth-service",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTeamPostureSummary()).resolves.toEqual({
      sessionCount: 10,
      hotspotCount: 4,
      criticalHotspots: 2,
      controlDrag: 3,
      riskDrag: 4,
      coverageDrag: 1,
      throughputDrag: 2,
      topHotspotLabel: "critical - auth-service",
    });
  });
});
