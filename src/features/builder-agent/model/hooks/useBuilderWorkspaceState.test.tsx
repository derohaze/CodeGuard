import { renderHook, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useBuilderWorkspaceState } from "./useBuilderWorkspaceState";

const listBuilderWorkspacesMock = vi.fn();
const createBuilderWorkspaceMock = vi.fn();
const getBuilderThreadMock = vi.fn();

vi.mock("../builderApi", async () => {
  const actual = await vi.importActual<object>("../builderApi");
  return {
    ...actual,
    createBuilderWorkspace: (...args: unknown[]) => createBuilderWorkspaceMock(...args),
    listBuilderWorkspaces: (...args: unknown[]) => listBuilderWorkspacesMock(...args),
    getBuilderThread: (...args: unknown[]) => getBuilderThreadMock(...args),
  };
});

describe("useBuilderWorkspaceState", () => {
  beforeEach(() => {
    listBuilderWorkspacesMock.mockReset();
    createBuilderWorkspaceMock.mockReset();
    getBuilderThreadMock.mockReset();
    vi.restoreAllMocks();
    window.electronAPI = {
      platform: "win32",
      versions: {
        node: "22.0.0",
        chrome: "123.0.0",
        electron: "33.0.0",
      },
      pickPath: vi.fn(),
    };
  });

  it("waits for first-load messages before activating a conversation", async () => {
    listBuilderWorkspacesMock.mockResolvedValue([
      {
        id: "workspace-1",
        label: "project x",
        path: "D:/workspace/project-x",
        updatedAt: "2026-04-14T00:00:00Z",
        threads: [
          {
            id: "thread-1",
            title: "The Latest Python",
            updatedAt: "2026-04-14T00:00:00Z",
          },
        ],
      },
    ]);

    let resolveThread: ((value: unknown) => void) | null = null;
    getBuilderThreadMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveThread = resolve;
        }),
    );

    const { result } = renderHook(() => useBuilderWorkspaceState());

    await waitFor(() => {
      expect(result.current.threadGroups).toHaveLength(1);
    });

    await act(async () => {
      const openPromise = result.current.openConversation("thread-1");
      expect(result.current.activeConversationId).toBeNull();
      expect(result.current.messages).toEqual([]);

      resolveThread?.({
        id: "thread-1",
        workspaceId: "workspace-1",
        title: "The Latest Python",
        updatedAt: "2026-04-14T00:00:01Z",
        contextState: {
          percentage: 28,
          usedTokens: 6720,
          maxTokens: 24000,
          rollingSummary: "Recent Python discussion.",
          recentMessageCount: 1,
          memoryCount: 1,
          memoryItems: [
            {
              id: "memory-1",
              memoryClass: "goal",
              title: "Python docs",
              content: "User wants Python guidance.",
              updatedAt: "2026-04-14T00:00:01Z",
            },
          ],
          updatedAt: "2026-04-14T00:00:01Z",
        },
        messages: [
          {
            id: "assistant-1",
            role: "assistant",
            text: "Ready.",
            createdAt: "2026-04-14T00:00:01Z",
            model: "route/glm-5.1",
          },
        ],
      });

      await openPromise;
    });

    await waitFor(() => {
      expect(result.current.activeConversationId).toBe("thread-1");
      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]?.text).toBe("Ready.");
      expect(result.current.contextStateMap["thread-1"]?.percentage).toBe(28);
    });
  });

  it("falls back to manual path entry if the native folder picker fails", async () => {
    listBuilderWorkspacesMock
      .mockResolvedValueOnce([
        {
          id: "workspace-1",
          label: "project x",
          path: "D:/workspace/project-x",
          updatedAt: "2026-04-14T00:00:00Z",
          threads: [],
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "workspace-1",
          label: "project x",
          path: "D:/workspace/project-x",
          updatedAt: "2026-04-14T00:00:00Z",
          threads: [],
        },
        {
          id: "workspace-2",
          label: "new repo",
          path: "D:/workspace/new-repo",
          updatedAt: "2026-04-14T00:00:01Z",
          threads: [],
        },
      ]);

    createBuilderWorkspaceMock.mockResolvedValue({
      id: "workspace-2",
      label: "new repo",
      path: "D:/workspace/new-repo",
      updatedAt: "2026-04-14T00:00:01Z",
      threads: [],
    });

    const pickPathMock = vi.fn().mockRejectedValue(new Error("picker failed"));
    window.electronAPI = {
      ...window.electronAPI,
      pickPath: pickPathMock,
    };

    vi.spyOn(window, "prompt").mockReturnValue("D:/workspace/new-repo");

    const { result } = renderHook(() => useBuilderWorkspaceState());

    await waitFor(() => {
      expect(result.current.threadGroups).toHaveLength(1);
    });

    await act(async () => {
      result.current.addWorkspace();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(pickPathMock).toHaveBeenCalledWith("folder");
      expect(createBuilderWorkspaceMock).toHaveBeenCalledWith("D:/workspace/new-repo");
      expect(result.current.currentWorkspaceId).toBe("workspace-2");
    });
  });
});
