import { describe, expect, it } from "vitest";
import { estimateBuilderContextUsage, resolveBuilderContextUsage } from "./context-window";

describe("estimateBuilderContextUsage", () => {
  it("keeps empty local context close to zero", () => {
    const usage = estimateBuilderContextUsage({
      composerSettings: {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      },
      draft: "",
      messages: [],
    });

    expect(usage.maxTokens).toBe(24000);
    expect(usage.usedTokens).toBeLessThanOrEqual(160);
    expect(usage.percentage).toBe(1);
  });

  it("increases usage when draft text grows", () => {
    const base = estimateBuilderContextUsage({
      composerSettings: {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      },
      draft: "",
      messages: [],
    });
    const withDraft = estimateBuilderContextUsage({
      composerSettings: {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      },
      draft: "Build a memory-aware context manager with rolling summaries and retrieved memory.",
      messages: [],
    });

    expect(withDraft.usedTokens).toBeGreaterThan(base.usedTokens);
    expect(withDraft.percentage).toBeGreaterThanOrEqual(base.percentage);
  });

  it("accounts for long conversations, summaries, and attachments", () => {
    const usage = estimateBuilderContextUsage({
      composerSettings: {
        permissionMode: "full-access",
        planMode: true,
        responseSpeed: "normal",
        attachedFiles: ["D:/workspace/a.ts", "D:/workspace/b.ts"],
      },
      draft: "Refactor this flow safely.",
      messages: Array.from({ length: 12 }, (_, index) => ({
        id: `m-${index}`,
        role: index % 2 === 0 ? "user" : "assistant",
        text: "This is a longer builder message carrying planning context, decisions, and follow-up notes.",
      })),
    });

    expect(usage.usedTokens).toBeGreaterThan(1000);
    expect(usage.percentage).toBeGreaterThan(4);
  });

  it("prefers backend context state when the thread is idle", () => {
    const usage = resolveBuilderContextUsage({
      backendContextState: {
        percentage: 41,
        usedTokens: 9840,
        maxTokens: 24000,
        rollingSummary: "Stable summary.",
        recentMessageCount: 4,
        memoryCount: 2,
        memoryItems: [],
        updatedAt: "2026-04-14T00:00:00Z",
      },
      composerSettings: {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      },
      draft: "",
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          text: "Stable reply",
        },
      ],
    });

    expect(usage.usedTokens).toBe(9840);
    expect(usage.percentage).toBe(41);
  });

  it("falls back to local estimation while the user is still typing", () => {
    const params = {
      composerSettings: {
        permissionMode: "full-access" as const,
        planMode: false,
        responseSpeed: "normal" as const,
        attachedFiles: [],
      },
      draft: "Drafting a larger prompt right now.",
      messages: [],
    };
    const usage = resolveBuilderContextUsage({
      backendContextState: {
        percentage: 15,
        usedTokens: 3600,
        maxTokens: 24000,
        rollingSummary: "Older summary.",
        recentMessageCount: 2,
        memoryCount: 0,
        memoryItems: [],
        updatedAt: "2026-04-14T00:00:00Z",
      },
      ...params,
    });
    const expectedLocalUsage = estimateBuilderContextUsage(params);

    expect(usage).toEqual(expectedLocalUsage);
  });

  it("returns zero usage for a brand-new empty chat", () => {
    const usage = resolveBuilderContextUsage({
      composerSettings: {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      },
      draft: "",
      messages: [],
    });

    expect(usage).toEqual({
      maxTokens: 24000,
      percentage: 0,
      usedTokens: 0,
    });
  });
});
