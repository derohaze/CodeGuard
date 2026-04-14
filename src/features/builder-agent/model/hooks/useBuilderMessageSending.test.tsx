import { renderHook, waitFor, act } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BuilderMessage } from "../mockBuilderAgent";
import type { BuilderContextState } from "../lib/context-window";
import { useBuilderMessageSending } from "./useBuilderMessageSending";

const sendBuilderMessageMock = vi.fn();
const sendBuilderMessageStreamMock = vi.fn();

vi.mock("../builderApi", () => ({
  sendBuilderMessage: (...args: unknown[]) => sendBuilderMessageMock(...args),
  sendBuilderMessageStream: (...args: unknown[]) => sendBuilderMessageStreamMock(...args),
}));

describe("useBuilderMessageSending", () => {
  beforeEach(() => {
    sendBuilderMessageMock.mockReset();
    sendBuilderMessageStreamMock.mockReset();
  });

  it("streams immediately in a new chat without bootstrapping a thread first", async () => {
    sendBuilderMessageStreamMock.mockImplementation(async (_payload, handlers) => {
      await new Promise((resolve) => window.setTimeout(resolve, 10));
      handlers.onAck?.({
        threadId: "thread-1",
        workspaceId: "workspace-1",
        contextState: {
          percentage: 18,
          usedTokens: 4320,
          maxTokens: 24000,
          rollingSummary: "Builder thread created.",
          recentMessageCount: 1,
          memoryCount: 0,
          memoryItems: [],
          updatedAt: "2026-04-14T00:00:00Z",
        },
      });
      handlers.onContextState?.({
        percentage: 26,
        usedTokens: 6240,
        maxTokens: 24000,
        rollingSummary: "User opened a new chat.",
        recentMessageCount: 1,
        memoryCount: 0,
        memoryItems: [],
        updatedAt: "2026-04-14T00:00:00Z",
      });
      handlers.onToken("Streaming ");
      await new Promise((resolve) => window.setTimeout(resolve, 120));
      handlers.onToken("reply");
      await new Promise((resolve) => window.setTimeout(resolve, 120));
      return {
        thread: {
          id: "thread-1",
          workspaceId: "workspace-1",
          title: "Streaming reply",
          updatedAt: "2026-04-14T00:00:02Z",
          contextState: {
            percentage: 34,
            usedTokens: 8160,
            maxTokens: 24000,
            rollingSummary: "Streaming reply completed.",
            recentMessageCount: 2,
            memoryCount: 1,
            memoryItems: [
              {
                id: "memory-1",
                memoryClass: "goal",
                title: "Greeting",
                content: "User greeted the agent.",
                updatedAt: "2026-04-14T00:00:02Z",
              },
            ],
            updatedAt: "2026-04-14T00:00:02Z",
          },
          messages: [
            {
              id: "user-1",
              role: "user",
              text: "hello",
              createdAt: "2026-04-14T00:00:00Z",
              model: null,
            },
            {
              id: "assistant-1",
              role: "assistant",
              text: "Streaming reply",
              createdAt: "2026-04-14T00:00:02Z",
              model: "route/glm-5.1",
            },
          ],
        },
        assistantMessage: {
          id: "assistant-1",
          role: "assistant",
          text: "Streaming reply",
          createdAt: "2026-04-14T00:00:02Z",
          model: "route/glm-5.1",
        },
      };
    });

    const refreshWorkspaces = vi.fn(async () => {});

    const { result } = renderHook(() => {
      const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
      const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>("workspace-1");
      const [draft, setDraft] = useState("hello");
      const [messageMap, setMessageMap] = useState<Record<string, BuilderMessage[]>>({});
      const [contextStateMap, setContextStateMap] = useState<Record<string, BuilderContextState | null>>({});

      const sending = useBuilderMessageSending({
        activeConversationId,
        composerSettings: {
          permissionMode: "default",
          planMode: false,
          responseSpeed: "normal",
          attachedFiles: [],
        },
        currentWorkspaceId,
        currentWorkspace: { id: "workspace-1" },
        draft,
        refreshWorkspaces,
        setActiveConversationId,
        setContextStateMap,
        setCurrentWorkspaceId,
        setDraft,
        setMessageMap,
      });

      return {
        ...sending,
        activeConversationId,
        currentWorkspaceId,
        draft,
        contextStateMap,
        messageMap,
      };
    });

    act(() => {
      result.current.sendMessage();
    });

    expect(result.current.isPreparingResponse).toBe(true);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.draft).toBe("hello");
    expect(result.current.prepareProgress).toBe(0);

    await waitFor(() => {
      expect(result.current.prepareProgress).toBeGreaterThan(0);
    });

    expect(result.current.isPreparingResponse).toBe(true);
    expect(result.current.isStreaming).toBe(false);

    await waitFor(() => {
      expect(result.current.draft).toBe("");
      expect(result.current.isStreaming).toBe(true);
      expect(result.current.isPreparingResponse).toBe(false);
    });

    await waitFor(() => {
      expect(result.current.activeConversationId).toBe("thread-1");
      expect(result.current.isPreparingResponse).toBe(false);
    });

    await waitFor(() => {
      const assistant = result.current.messageMap["thread-1"]?.find((message) => message.role === "assistant");
      expect(assistant?.text.length ?? 0).toBeGreaterThan(0);
      expect(assistant?.text).not.toBe("Streaming reply");
    });

    await waitFor(() => {
      expect(result.current.contextStateMap["thread-1"]?.percentage).toBe(26);
    });

    await waitFor(() => {
      const assistant = result.current.messageMap["thread-1"]?.find((message) => message.role === "assistant");
      expect(assistant?.text).toBe("Streaming reply");
      expect(result.current.isStreaming).toBe(false);
      expect(result.current.contextStateMap["thread-1"]?.percentage).toBe(34);
    });

    expect(refreshWorkspaces).toHaveBeenCalledTimes(1);
    expect(sendBuilderMessageStreamMock).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: null,
      }),
      expect.any(Object),
      expect.any(AbortSignal),
    );
    expect(sendBuilderMessageMock).not.toHaveBeenCalled();
  });
});
