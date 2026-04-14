import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  archiveBuilderThread,
  archiveBuilderWorkspaceThreads,
  createBuilderThread,
  createBuilderWorkspace,
  deleteBuilderThread,
  deleteBuilderWorkspace,
  getBuilderThread,
  listBuilderWorkspaces,
  renameBuilderThread,
  renameBuilderWorkspace,
} from "../builderApi";
import {
  type BuilderConversation,
  type BuilderMessage,
  type BuilderThreadGroup,
} from "../mockBuilderAgent";
import type { BuilderContextState } from "../lib/context-window";
import { mapMessage, mapWorkspace } from "../lib/mappers";

export function useBuilderWorkspaceState() {
  const [threadGroups, setThreadGroups] = useState<BuilderThreadGroup[]>([]);
  const [messageMap, setMessageMap] = useState<Record<string, BuilderMessage[]>>({});
  const [contextStateMap, setContextStateMap] = useState<Record<string, BuilderContextState | null>>({});
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(null);
  const [previousConversationId, setPreviousConversationId] = useState<string | null>(null);
  const [expandedWorkspaceIds, setExpandedWorkspaceIds] = useState<string[]>([]);
  const [showAllWorkspaceIds, setShowAllWorkspaceIds] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<"recent" | "alphabetical">("recent");
  const pendingConversationOpenRef = useRef<string | null>(null);

  const refreshWorkspaces = useCallback(async () => {
    const workspaces = await listBuilderWorkspaces();
    const mapped = workspaces.map(mapWorkspace);
    setThreadGroups(mapped);
    setExpandedWorkspaceIds((current) => {
      if (current.length === 0) {
        return mapped.map((workspace) => workspace.id);
      }
      const existing = new Set(mapped.map((workspace) => workspace.id));
      const filtered = current.filter((item) => existing.has(item));
      return filtered.length > 0 ? filtered : mapped.map((workspace) => workspace.id);
    });
    setCurrentWorkspaceId((current) => {
      if (current && mapped.some((workspace) => workspace.id === current)) {
        return current;
      }
      return mapped[0]?.id ?? null;
    });
  }, []);

  useEffect(() => {
    void refreshWorkspaces().catch((error) => {
      console.error("[CodeGuard Builder] Failed to load workspaces", error);
      setThreadGroups([]);
    });
  }, [refreshWorkspaces]);

  const conversations = useMemo<BuilderConversation[]>(() => {
    return threadGroups.flatMap((group) =>
      group.threads.map((thread) => ({
        id: thread.id,
        title: thread.title,
        subtitle: group.label,
        groupId: group.id,
        updatedAt: thread.updatedAt,
      })),
    );
  }, [threadGroups]);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeConversationId) ?? null,
    [activeConversationId, conversations],
  );

  const currentWorkspace = useMemo(
    () =>
      threadGroups.find((group) => group.id === (activeConversation?.groupId ?? currentWorkspaceId)) ??
      threadGroups[0] ??
      null,
    [activeConversation?.groupId, currentWorkspaceId, threadGroups],
  );

  const sortedThreadGroups = useMemo(() => {
    if (sortMode !== "alphabetical") {
      return threadGroups;
    }
    return threadGroups.map((group) => ({
      ...group,
      threads: [...group.threads].sort((left, right) => left.title.localeCompare(right.title)),
    }));
  }, [sortMode, threadGroups]);

  const messages = activeConversationId ? messageMap[activeConversationId] ?? [] : [];

  const openConversation = useCallback(async (conversationId: string) => {
    if (activeConversationId && activeConversationId !== conversationId) {
      setPreviousConversationId(activeConversationId);
    }
    const conversation = conversations.find((item) => item.id === conversationId);
    if (conversation) {
      setCurrentWorkspaceId(conversation.groupId);
      setExpandedWorkspaceIds((current) => (current.includes(conversation.groupId) ? current : [...current, conversation.groupId]));
    }

    if (messageMap[conversationId]) {
      pendingConversationOpenRef.current = null;
      setActiveConversationId(conversationId);
      return;
    }

    pendingConversationOpenRef.current = conversationId;
    try {
      const detail = await getBuilderThread(conversationId);
      if (pendingConversationOpenRef.current !== conversationId) {
        return;
      }
      setMessageMap((current) => ({
        ...current,
        [conversationId]: detail.messages.map(mapMessage),
      }));
      setContextStateMap((current) => ({
        ...current,
        [conversationId]: detail.contextState ?? null,
      }));
      setActiveConversationId(conversationId);
    } catch (error) {
      if (pendingConversationOpenRef.current === conversationId) {
        setActiveConversationId(conversationId);
      }
      console.error("[CodeGuard Builder] Failed to open conversation", error);
    } finally {
      if (pendingConversationOpenRef.current === conversationId) {
        pendingConversationOpenRef.current = null;
      }
    }
  }, [activeConversationId, conversations, messageMap]);

  const startNewChat = useCallback((workspaceId?: string) => {
    if (activeConversationId) {
      setPreviousConversationId(activeConversationId);
    }
    const targetWorkspaceId = workspaceId ?? currentWorkspace?.id ?? threadGroups[0]?.id ?? null;
    if (targetWorkspaceId) {
      setCurrentWorkspaceId(targetWorkspaceId);
      setExpandedWorkspaceIds((current) => (current.includes(targetWorkspaceId) ? current : [...current, targetWorkspaceId]));
    }
    setActiveConversationId(null);
    setDraft("");
  }, [activeConversationId, currentWorkspace?.id, threadGroups]);

  const toggleWorkspace = useCallback((workspaceId: string) => {
    setExpandedWorkspaceIds((current) => (
      current.includes(workspaceId)
        ? current.filter((id) => id !== workspaceId)
        : [...current, workspaceId]
    ));
  }, []);

  const toggleWorkspaceShowAll = useCallback((workspaceId: string) => {
    setShowAllWorkspaceIds((current) => (
      current.includes(workspaceId)
        ? current.filter((id) => id !== workspaceId)
        : [...current, workspaceId]
    ));
  }, []);

  const collapseAllWorkspaces = useCallback(() => setExpandedWorkspaceIds([]), []);
  const expandAllWorkspaces = useCallback(() => setExpandedWorkspaceIds(threadGroups.map((group) => group.id)), [threadGroups]);

  const reopenPreviousConversation = useCallback(() => {
    if (!previousConversationId) return;
    void openConversation(previousConversationId);
  }, [openConversation, previousConversationId]);

  const toggleSortMode = useCallback(() => {
    setSortMode((current) => (current === "recent" ? "alphabetical" : "recent"));
  }, []);

  const addWorkspace = useCallback(() => {
    void (async () => {
      const picked = await pickWorkspacePath();
      if (!picked) return;
      const normalizedPath = picked.trim();
      if (!normalizedPath) return;

      try {
        const workspace = await createBuilderWorkspace(normalizedPath);
        await refreshWorkspaces();
        setCurrentWorkspaceId(workspace.id);
        setExpandedWorkspaceIds((current) => (current.includes(workspace.id) ? current : [...current, workspace.id]));
        setActiveConversationId(null);
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to create workspace", error);
      }
    })();
  }, [refreshWorkspaces]);

  const renameWorkspace = useCallback((workspaceId: string) => {
    const workspace = threadGroups.find((group) => group.id === workspaceId);
    if (!workspace) return;
    const nextLabel = window.prompt("Rename workspace", workspace.label)?.trim();
    if (!nextLabel) return;

    void (async () => {
      try {
        await renameBuilderWorkspace(workspaceId, nextLabel);
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to rename workspace", error);
      }
    })();
  }, [refreshWorkspaces, threadGroups]);

  const archiveWorkspaceThreads = useCallback((workspaceId: string) => {
    void (async () => {
      try {
        const workspace = threadGroups.find((group) => group.id === workspaceId);
        const threadIds = workspace ? workspace.threads.map((thread) => thread.id) : [];
        await archiveBuilderWorkspaceThreads(workspaceId);
        setMessageMap((current) => {
          const next = { ...current };
          for (const threadId of threadIds) {
            delete next[threadId];
          }
          return next;
        });
        setContextStateMap((current) => {
          const next = { ...current };
          for (const threadId of threadIds) {
            delete next[threadId];
          }
          return next;
        });
        if (activeConversationId && threadIds.includes(activeConversationId)) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to archive workspace threads", error);
      }
    })();
  }, [activeConversationId, refreshWorkspaces, threadGroups]);

  const removeWorkspace = useCallback((workspaceId: string) => {
    void (async () => {
      try {
        const workspace = threadGroups.find((group) => group.id === workspaceId);
        const threadIds = workspace ? workspace.threads.map((thread) => thread.id) : [];
        await deleteBuilderWorkspace(workspaceId);
        setMessageMap((current) => {
          const next = { ...current };
          for (const threadId of threadIds) {
            delete next[threadId];
          }
          return next;
        });
        setContextStateMap((current) => {
          const next = { ...current };
          for (const threadId of threadIds) {
            delete next[threadId];
          }
          return next;
        });
        if (activeConversationId && threadIds.includes(activeConversationId)) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to remove workspace", error);
      }
    })();
  }, [activeConversationId, refreshWorkspaces, threadGroups]);

  const openWorkspaceInExplorer = useCallback((workspaceId: string) => {
    const workspace = threadGroups.find((group) => group.id === workspaceId);
    if (!workspace || typeof window === "undefined") return;

    const normalized = workspace.path.replace(/\\/g, "/");
    const fileUrl = normalized.startsWith("/") ? `file://${normalized}` : `file:///${normalized}`;

    try {
      window.open(fileUrl, "_blank", "noopener,noreferrer");
    } catch {
      if (navigator.clipboard) {
        void navigator.clipboard.writeText(workspace.path);
      }
    }
  }, [threadGroups]);

  const createPermanentWorktree = useCallback((_workspaceId: string) => {
    // Future backend capability.
  }, []);

  const createWorkspaceThread = useCallback((workspaceId: string) => {
    void (async () => {
      try {
        const detail = await createBuilderThread(workspaceId);
        setCurrentWorkspaceId(workspaceId);
        setActiveConversationId(detail.id);
        setExpandedWorkspaceIds((current) => (current.includes(workspaceId) ? current : [...current, workspaceId]));
        setMessageMap((current) => ({
          ...current,
          [detail.id]: detail.messages.map(mapMessage),
        }));
        setContextStateMap((current) => ({
          ...current,
          [detail.id]: detail.contextState ?? null,
        }));
        setDraft("");
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to create workspace thread", error);
      }
    })();
  }, [refreshWorkspaces]);

  const reorderWorkspaces = useCallback((orderedWorkspaceIds: string[]) => {
    const index = new Map(threadGroups.map((group) => [group.id, group]));
    const nextGroups = orderedWorkspaceIds
      .map((workspaceId) => index.get(workspaceId) ?? null)
      .filter((group): group is BuilderThreadGroup => group !== null);
    if (nextGroups.length !== threadGroups.length) return;
    setThreadGroups(nextGroups);
  }, [threadGroups]);

  const renameThread = useCallback((threadId: string) => {
    const thread = conversations.find((item) => item.id === threadId);
    if (!thread) return;
    const nextTitle = window.prompt("Rename chat", thread.title)?.trim();
    if (!nextTitle) return;

    void (async () => {
      try {
        const detail = await renameBuilderThread(threadId, nextTitle);
        setMessageMap((current) => ({
          ...current,
          [detail.id]: detail.messages.map(mapMessage),
        }));
        setContextStateMap((current) => ({
          ...current,
          [detail.id]: detail.contextState ?? null,
        }));
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to rename thread", error);
      }
    })();
  }, [conversations, refreshWorkspaces]);

  const removeThread = useCallback((threadId: string) => {
    void (async () => {
      try {
        await deleteBuilderThread(threadId);
        setMessageMap((current) => {
          const next = { ...current };
          delete next[threadId];
          return next;
        });
        setContextStateMap((current) => {
          const next = { ...current };
          delete next[threadId];
          return next;
        });
        if (activeConversationId === threadId) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to delete thread", error);
      }
    })();
  }, [activeConversationId, refreshWorkspaces]);

  const archiveThread = useCallback((threadId: string) => {
    void (async () => {
      try {
        await archiveBuilderThread(threadId);
        setMessageMap((current) => {
          const next = { ...current };
          delete next[threadId];
          return next;
        });
        setContextStateMap((current) => {
          const next = { ...current };
          delete next[threadId];
          return next;
        });
        if (activeConversationId === threadId) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to archive thread", error);
      }
    })();
  }, [activeConversationId, refreshWorkspaces]);

  return {
    addWorkspace,
    activeConversation,
    activeConversationId,
    archiveThread,
    archiveWorkspaceThreads,
    collapseAllWorkspaces,
    conversations,
    createPermanentWorktree,
    createWorkspaceThread,
    currentWorkspace,
    currentWorkspaceId,
    contextStateMap,
    draft,
    expandedWorkspaceIds,
    expandAllWorkspaces,
    hasPreviousConversation: previousConversationId !== null,
    messageMap,
    messages,
    openConversation,
    openWorkspaceInExplorer,
    previousConversationId,
    refreshWorkspaces,
    removeThread,
    removeWorkspace,
    renameThread,
    renameWorkspace,
    reorderWorkspaces,
    reopenPreviousConversation,
    setActiveConversationId,
    setCurrentWorkspaceId,
    setDraft,
    setContextStateMap,
    setExpandedWorkspaceIds,
    setMessageMap,
    setShowAllWorkspaceIds,
    showAllWorkspaceIds,
    sortMode,
    sortedThreadGroups,
    startNewChat,
    threadGroups,
    toggleSortMode,
    toggleWorkspace,
    toggleWorkspaceShowAll,
  };
}

async function pickWorkspacePath(): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }

  if (typeof window.electronAPI?.pickPath === "function") {
    try {
      const picked = await window.electronAPI.pickPath("folder");
      const normalized = typeof picked === "string" ? picked.trim() : "";
      if (normalized) {
        return normalized;
      }
      return null;
    } catch (error) {
      console.error("[CodeGuard Builder] Native folder picker failed", error);
    }
  }

  const manualPath = window.prompt("Project folder path")?.trim() ?? null;
  return manualPath && manualPath.trim() ? manualPath.trim() : null;
}
