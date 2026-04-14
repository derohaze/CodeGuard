import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchWithStartupRetry } from "@/shared/api/network";

describe("fetchWithStartupRetry", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("retries transient GET network failures during backend startup", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const requestPromise = fetchWithStartupRetry("http://127.0.0.1:8000/api/v1/health/live");
    await vi.runAllTimersAsync();
    const response = await requestPromise;

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("waits for one shared readiness probe before hitting API resources", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);

    const [settingsResponse, sessionsResponse] = await Promise.all([
      fetchWithStartupRetry("http://127.0.0.1:8000/api/v1/settings/runtime"),
      fetchWithStartupRetry("http://127.0.0.1:8000/api/v1/sessions"),
    ]);

    expect(settingsResponse.ok).toBe(true);
    expect(sessionsResponse.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]?.toString()).toContain("/api/v1/health/live");
  });

  it("does not retry non-idempotent requests", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchWithStartupRetry("http://127.0.0.1:8000/api/v1/scans", {
        method: "POST",
      }),
    ).rejects.toThrow("Failed to fetch");

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
