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
  sendBuilderMessage,
  sendBuilderMessageStream,
  type BuilderThreadDto,
  type BuilderWorkspaceDto,
} from "./builderApi";
import {
  builderPromptSuggestions,
  type BuilderConversation,
  type BuilderMessage,
  type BuilderThreadGroup,
} from "./mockBuilderAgent";

const BUILDER_COMPOSER_SETTINGS_KEY = "builder-composer-settings";

type PermissionMode = "default" | "full-access";
type ResponseSpeed = "normal" | "speed";

interface BuilderComposerSettings {
  permissionMode: PermissionMode;
  planMode: boolean;
  responseSpeed: ResponseSpeed;
  attachedFiles: string[];
}

function formatRelativeTime(isoValue: string): string {
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) {
    return "now";
  }
  const diffMs = Date.now() - parsed.getTime();
  if (diffMs <= 60_000) return "now";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d`;
  const months = Math.floor(days / 30);
  return `${Math.max(months, 1)}mo`;
}

function mapMessage(message: BuilderThreadDto["messages"][number]): BuilderMessage {
  return {
    id: message.id,
    role: message.role,
    text: message.text,
    isStreaming: false,
  };
}

function mapWorkspace(workspace: BuilderWorkspaceDto): BuilderThreadGroup {
  return {
    id: workspace.id,
    label: workspace.label,
    path: workspace.path,
    threads: workspace.threads.map((thread) => ({
      id: thread.id,
      title: thread.title,
      updatedAt: formatRelativeTime(thread.updatedAt),
    })),
  };
}

function loadComposerSettings(): BuilderComposerSettings {
  if (typeof window === "undefined") {
    return {
      permissionMode: "full-access",
      planMode: false,
      responseSpeed: "normal",
      attachedFiles: [],
    };
  }

  try {
    const stored = window.localStorage.getItem(BUILDER_COMPOSER_SETTINGS_KEY);
    if (!stored) {
      return {
        permissionMode: "full-access",
        planMode: false,
        responseSpeed: "normal",
        attachedFiles: [],
      };
    }
    const parsed = JSON.parse(stored) as Partial<BuilderComposerSettings>;
    return {
      permissionMode: parsed.permissionMode === "default" ? "default" : "full-access",
      planMode: Boolean(parsed.planMode),
      responseSpeed: parsed.responseSpeed === "speed" ? "speed" : "normal",
      attachedFiles: Array.isArray(parsed.attachedFiles) ? parsed.attachedFiles : [],
    };
  } catch {
    return {
      permissionMode: "full-access",
      planMode: false,
      responseSpeed: "normal",
      attachedFiles: [],
    };
  }
}

export function useBuilderAgent() {
  const [threadGroups, setThreadGroups] = useState<BuilderThreadGroup[]>([]);
  const [messageMap, setMessageMap] = useState<Record<string, BuilderMessage[]>>({});
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [currentWorkspaceId, setCurrentWorkspaceId] = useState<string | null>(null);
  const [previousConversationId, setPreviousConversationId] = useState<string | null>(null);
  const [expandedWorkspaceIds, setExpandedWorkspaceIds] = useState<string[]>([]);
  const [showAllWorkspaceIds, setShowAllWorkspaceIds] = useState<string[]>([]);
  const [sortMode, setSortMode] = useState<"recent" | "alphabetical">("recent");
  const [isStreaming, setIsStreaming] = useState(false);
  const [composerSettings, setComposerSettings] = useState<BuilderComposerSettings>(() => loadComposerSettings());
  const activeSendAbortRef = useRef<AbortController | null>(null);
  const activeStreamThreadIdRef = useRef<string | null>(null);
  const activeStreamAssistantIdRef = useRef<string | null>(null);
  const streamUnitsRef = useRef<string[]>([]);
  const streamVisibleTextRef = useRef("");
  const streamSourceCompletedRef = useRef(true);
  const streamDrainStartedRef = useRef(false);
  const streamDrainFrameRef = useRef<number | null>(null);
  const streamWarmupTimeoutRef = useRef<number | null>(null);
  const streamDrainResolverRef = useRef<(() => void) | null>(null);

  const persistComposerSettings = useCallback((nextSettings: BuilderComposerSettings) => {
    setComposerSettings(nextSettings);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(BUILDER_COMPOSER_SETTINGS_KEY, JSON.stringify(nextSettings));
    }
  }, []);

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

  useEffect(() => {
    return () => {
      if (activeSendAbortRef.current) {
        activeSendAbortRef.current.abort();
      }
      if (streamDrainFrameRef.current !== null) {
        window.cancelAnimationFrame(streamDrainFrameRef.current);
      }
      if (streamWarmupTimeoutRef.current !== null) {
        window.clearTimeout(streamWarmupTimeoutRef.current);
      }
    };
  }, []);

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

  const markAssistantStopped = useCallback((threadId?: string | null, assistantId?: string | null) => {
    const resolvedThreadId = threadId ?? activeStreamThreadIdRef.current;
    const resolvedAssistantId = assistantId ?? activeStreamAssistantIdRef.current;
    const visibleText = streamVisibleTextRef.current;
    if (!resolvedThreadId || !resolvedAssistantId) {
      return;
    }
    setMessageMap((current) => ({
      ...current,
      [resolvedThreadId]: (current[resolvedThreadId] ?? []).map((item) => (
        item.id === resolvedAssistantId
          ? {
              ...item,
              text: visibleText || item.text,
              isStreaming: false,
            }
          : item
      )),
    }));
  }, []);

  const markActiveAssistantStopped = useCallback(() => {
    const threadId = activeStreamThreadIdRef.current;
    const assistantId = activeStreamAssistantIdRef.current;
    if (!threadId || !assistantId) {
      return;
    }
    markAssistantStopped(threadId, assistantId);
  }, [markAssistantStopped]);

  const stopActiveStream = useCallback(() => {
    if (activeSendAbortRef.current) {
      activeSendAbortRef.current.abort();
      activeSendAbortRef.current = null;
    }
    if (streamDrainFrameRef.current !== null) {
      window.cancelAnimationFrame(streamDrainFrameRef.current);
      streamDrainFrameRef.current = null;
    }
    if (streamWarmupTimeoutRef.current !== null) {
      window.clearTimeout(streamWarmupTimeoutRef.current);
      streamWarmupTimeoutRef.current = null;
    }
    streamSourceCompletedRef.current = true;
    streamDrainStartedRef.current = false;
    streamUnitsRef.current = [];
    markActiveAssistantStopped();
    if (streamDrainResolverRef.current) {
      streamDrainResolverRef.current();
      streamDrainResolverRef.current = null;
    }
    setIsStreaming(false);
  }, [markActiveAssistantStopped]);

  const openConversation = useCallback(async (conversationId: string) => {
    if (activeConversationId && activeConversationId !== conversationId) {
      setPreviousConversationId(activeConversationId);
    }
    const conversation = conversations.find((item) => item.id === conversationId);
    setActiveConversationId(conversationId);
    if (conversation) {
      setCurrentWorkspaceId(conversation.groupId);
      setExpandedWorkspaceIds((current) => (current.includes(conversation.groupId) ? current : [...current, conversation.groupId]));
    }
    if (!messageMap[conversationId]) {
      try {
        const detail = await getBuilderThread(conversationId);
        setMessageMap((current) => ({
          ...current,
          [conversationId]: detail.messages.map(mapMessage),
        }));
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to open conversation", error);
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

  const toggleWorkspace = (workspaceId: string) => {
    setExpandedWorkspaceIds((current) => (
      current.includes(workspaceId)
        ? current.filter((id) => id !== workspaceId)
        : [...current, workspaceId]
    ));
  };

  const toggleWorkspaceShowAll = (workspaceId: string) => {
    setShowAllWorkspaceIds((current) => (
      current.includes(workspaceId)
        ? current.filter((id) => id !== workspaceId)
        : [...current, workspaceId]
    ));
  };

  const collapseAllWorkspaces = () => setExpandedWorkspaceIds([]);
  const expandAllWorkspaces = () => setExpandedWorkspaceIds(threadGroups.map((group) => group.id));

  const reopenPreviousConversation = () => {
    if (!previousConversationId) return;
    void openConversation(previousConversationId);
  };

  const toggleSortMode = () => {
    setSortMode((current) => (current === "recent" ? "alphabetical" : "recent"));
  };

  const addWorkspace = () => {
    void (async () => {
      const canBrowse = typeof window !== "undefined" && typeof window.electronAPI?.pickPath === "function";
      const picked = canBrowse ? await window.electronAPI?.pickPath?.("folder") : window.prompt("Project folder path")?.trim() ?? null;
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
  };

  const renameWorkspace = (workspaceId: string) => {
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
  };

  const archiveWorkspaceThreads = (workspaceId: string) => {
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
        if (activeConversationId && threadIds.includes(activeConversationId)) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to archive workspace threads", error);
      }
    })();
  };

  const removeWorkspace = (workspaceId: string) => {
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
        if (activeConversationId && threadIds.includes(activeConversationId)) {
          setActiveConversationId(null);
          setDraft("");
        }
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to remove workspace", error);
      }
    })();
  };

  const openWorkspaceInExplorer = (workspaceId: string) => {
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
  };

  const createPermanentWorktree = (_workspaceId: string) => {
    // Future backend capability.
  };

  const createWorkspaceThread = (workspaceId: string) => {
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
        setDraft("");
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to create workspace thread", error);
      }
    })();
  };

  const reorderWorkspaces = (orderedWorkspaceIds: string[]) => {
    const index = new Map(threadGroups.map((group) => [group.id, group]));
    const nextGroups = orderedWorkspaceIds
      .map((workspaceId) => index.get(workspaceId) ?? null)
      .filter((group): group is BuilderThreadGroup => group !== null);
    if (nextGroups.length !== threadGroups.length) return;
    setThreadGroups(nextGroups);
  };

  const addAttachment = () => {
    void (async () => {
      const canBrowse = typeof window !== "undefined" && typeof window.electronAPI?.pickPath === "function";
      const picked = canBrowse ? await window.electronAPI?.pickPath?.("file") : window.prompt("File path")?.trim() ?? null;
      if (!picked) return;
      const normalizedPath = picked.trim();
      if (!normalizedPath) return;

      const nextFiles = composerSettings.attachedFiles.includes(normalizedPath)
        ? composerSettings.attachedFiles
        : [...composerSettings.attachedFiles, normalizedPath];
      persistComposerSettings({
        ...composerSettings,
        attachedFiles: nextFiles,
      });
    })();
  };

  const removeAttachment = (filePath: string) => {
    persistComposerSettings({
      ...composerSettings,
      attachedFiles: composerSettings.attachedFiles.filter((item) => item !== filePath),
    });
  };

  const setPermissionMode = (permissionMode: PermissionMode) => {
    persistComposerSettings({
      ...composerSettings,
      permissionMode,
    });
  };

  const setPlanMode = (planMode: boolean) => {
    persistComposerSettings({
      ...composerSettings,
      planMode,
    });
  };

  const setResponseSpeed = (responseSpeed: ResponseSpeed) => {
    persistComposerSettings({
      ...composerSettings,
      responseSpeed,
    });
  };

  const renameThread = (threadId: string) => {
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
        await refreshWorkspaces();
      } catch (error) {
        console.error("[CodeGuard Builder] Failed to rename thread", error);
      }
    })();
  };

  const removeThread = (threadId: string) => {
    void (async () => {
      try {
        await deleteBuilderThread(threadId);
        setMessageMap((current) => {
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
  };

  const archiveThread = (threadId: string) => {
    void (async () => {
      try {
        await archiveBuilderThread(threadId);
        setMessageMap((current) => {
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
  };

  const sendMessage = () => {
    void (async () => {
      const prompt = draft.trim();
      if (!prompt || !currentWorkspace) return;

      let threadId = activeConversationId;
      if (!threadId) {
        try {
          const created = await createBuilderThread(currentWorkspace.id, prompt.slice(0, 96));
          threadId = created.id;
          setActiveConversationId(created.id);
          setCurrentWorkspaceId(created.workspaceId);
          setMessageMap((current) => ({
            ...current,
            [created.id]: created.messages.map(mapMessage),
          }));
        } catch (error) {
          console.error("[CodeGuard Builder] Failed to bootstrap chat thread", error);
          return;
        }
      }
      if (!threadId) return;

      const optimisticUserMessage: BuilderMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        text: prompt,
      };
      const optimisticAssistantId = `local-assistant-${Date.now() + 1}`;
      setMessageMap((current) => ({
        ...current,
        [threadId!]: [
          ...(current[threadId!] ?? []),
          optimisticUserMessage,
          {
            id: optimisticAssistantId,
            role: "assistant",
            text: "",
            isStreaming: true,
          },
        ],
      }));
      setDraft("");

      const abortController = new AbortController();
      activeSendAbortRef.current = abortController;
      activeStreamThreadIdRef.current = threadId;
      activeStreamAssistantIdRef.current = optimisticAssistantId;
      setIsStreaming(true);
      streamUnitsRef.current = [];
      streamVisibleTextRef.current = "";
      streamSourceCompletedRef.current = false;
      streamDrainStartedRef.current = false;

      try {
        const payload = {
          workspaceId: currentWorkspace.id,
          threadId,
          message: prompt,
          permissionMode: composerSettings.permissionMode,
          planMode: composerSettings.planMode,
          responseSpeed: composerSettings.responseSpeed,
        } as const;

        const pushVisibleText = (nextText: string) => {
          streamVisibleTextRef.current = nextText;
          setMessageMap((current) => ({
            ...current,
            [threadId!]: (current[threadId!] ?? []).map((item) => (
              item.id === optimisticAssistantId
                ? { ...item, text: nextText }
                : item
            )),
          }));
        };

        const clearWarmupTimer = () => {
          if (streamWarmupTimeoutRef.current !== null) {
            window.clearTimeout(streamWarmupTimeoutRef.current);
            streamWarmupTimeoutRef.current = null;
          }
        };

        const resolveDrainWaiter = () => {
          if (streamDrainResolverRef.current) {
            streamDrainResolverRef.current();
            streamDrainResolverRef.current = null;
          }
        };

        const finishDrainIfIdle = () => {
          if (streamUnitsRef.current.length > 0) {
            return;
          }
          if (!streamSourceCompletedRef.current) {
            return;
          }
          if (streamDrainFrameRef.current !== null) {
            return;
          }
          clearWarmupTimer();
          resolveDrainWaiter();
        };

        const drainBufferedText = () => {
          streamDrainFrameRef.current = null;

          if (abortController.signal.aborted || activeSendAbortRef.current !== abortController) {
            finishDrainIfIdle();
            return;
          }

          const bufferLength = streamUnitsRef.current.length;
          if (!streamDrainStartedRef.current) {
            const shouldStart =
              streamSourceCompletedRef.current || bufferLength >= STREAM_REVEAL_START_BUFFER;
            if (!shouldStart) {
              return;
            }
            streamDrainStartedRef.current = true;
          }

          if (bufferLength === 0) {
            if (streamSourceCompletedRef.current) {
              finishDrainIfIdle();
              return;
            }
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
            return;
          }

          const batchSize = resolveStreamRevealBatchSize(bufferLength, streamSourceCompletedRef.current);
          const nextChunk = streamUnitsRef.current.splice(0, batchSize).join("");
          if (nextChunk) {
            pushVisibleText(streamVisibleTextRef.current + nextChunk);
          }

          if (streamUnitsRef.current.length === 0 && streamSourceCompletedRef.current) {
            finishDrainIfIdle();
            return;
          }

          streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
        };

        const startDrain = () => {
          clearWarmupTimer();
          streamDrainStartedRef.current = true;
          if (streamDrainFrameRef.current === null) {
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
          }
        };

        const ensureWarmup = () => {
          if (streamDrainStartedRef.current || streamWarmupTimeoutRef.current !== null) {
            return;
          }
          streamWarmupTimeoutRef.current = window.setTimeout(() => {
            streamWarmupTimeoutRef.current = null;
            if (abortController.signal.aborted || activeSendAbortRef.current !== abortController) {
              return;
            }
            startDrain();
          }, STREAM_REVEAL_WARMUP_MS);
        };

        const enqueueToken = (token: string) => {
          streamUnitsRef.current.push(...splitStreamDisplayUnits(token));
          if (!streamDrainStartedRef.current) {
            if (streamUnitsRef.current.length >= STREAM_REVEAL_START_BUFFER) {
              startDrain();
            } else {
              ensureWarmup();
            }
            return;
          }
          if (streamDrainFrameRef.current === null) {
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
          }
        };

        const waitForDrain = async () => {
          streamSourceCompletedRef.current = true;
          clearWarmupTimer();
          if (!streamDrainStartedRef.current) {
            startDrain();
          } else if (streamDrainFrameRef.current === null) {
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
          }
          if (streamUnitsRef.current.length === 0 && streamDrainFrameRef.current === null) {
            return;
          }
          await new Promise<void>((resolve) => {
            streamDrainResolverRef.current = resolve;
          });
        };

        let result = await sendBuilderMessageStream(
          payload,
          {
            onToken: (token) => {
              enqueueToken(token);
            },
            onReasoning: () => {
              // Builder chat should stream only the visible assistant answer.
            },
          },
          abortController.signal,
        );
        await waitForDrain();

        if (!result) {
          result = await sendBuilderMessage(payload, abortController.signal);
        }

        setMessageMap((current) => ({
          ...current,
          [result.thread.id]: result.thread.messages.map(mapMessage),
        }));
        setActiveConversationId(result.thread.id);
        setCurrentWorkspaceId(result.thread.workspaceId);
        await refreshWorkspaces();
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }
        try {
          const result = await sendBuilderMessage(
            {
              workspaceId: currentWorkspace.id,
              threadId,
              message: prompt,
              permissionMode: composerSettings.permissionMode,
              planMode: composerSettings.planMode,
              responseSpeed: composerSettings.responseSpeed,
            },
            abortController.signal,
          );
          setMessageMap((current) => ({
            ...current,
            [result.thread.id]: result.thread.messages.map(mapMessage),
          }));
          setActiveConversationId(result.thread.id);
          setCurrentWorkspaceId(result.thread.workspaceId);
          await refreshWorkspaces();
        } catch (fallbackError) {
          console.error("[CodeGuard Builder] Failed to send message", fallbackError ?? error);
        }
      } finally {
        if (streamDrainFrameRef.current !== null) {
          window.cancelAnimationFrame(streamDrainFrameRef.current);
          streamDrainFrameRef.current = null;
        }
        if (streamWarmupTimeoutRef.current !== null) {
          window.clearTimeout(streamWarmupTimeoutRef.current);
          streamWarmupTimeoutRef.current = null;
        }
        streamUnitsRef.current = [];
        streamSourceCompletedRef.current = true;
        streamDrainStartedRef.current = false;
        if (streamDrainResolverRef.current) {
          streamDrainResolverRef.current();
          streamDrainResolverRef.current = null;
        }
        markAssistantStopped(threadId, optimisticAssistantId);
        streamVisibleTextRef.current = "";
        if (
          activeStreamThreadIdRef.current === threadId &&
          activeStreamAssistantIdRef.current === optimisticAssistantId
        ) {
          activeStreamThreadIdRef.current = null;
          activeStreamAssistantIdRef.current = null;
        }
        if (activeSendAbortRef.current === abortController) {
          activeSendAbortRef.current = null;
          setIsStreaming(false);
        }
      }
    })();
  };

  return {
    activeConversation,
    activeConversationId,
    currentWorkspace,
    draft,
    expandedWorkspaceIds,
    isStreaming,
    messages,
    composerSettings,
    promptSuggestions: builderPromptSuggestions,
    showAllWorkspaceIds,
    sortMode,
    threadGroups: sortedThreadGroups,
    addAttachment,
    addWorkspace,
    archiveWorkspaceThreads,
    archiveThread,
    collapseAllWorkspaces,
    createPermanentWorktree,
    createWorkspaceThread,
    expandAllWorkspaces,
    hasPreviousConversation: previousConversationId !== null,
    openConversation,
    openWorkspaceInExplorer,
    removeWorkspace,
    removeThread,
    reorderWorkspaces,
    renameWorkspace,
    renameThread,
    reopenPreviousConversation,
    removeAttachment,
    sendMessage,
    stopStreaming: stopActiveStream,
    setPermissionMode,
    setPlanMode,
    setResponseSpeed,
    setDraft,
    startNewChat,
    toggleSortMode,
    toggleWorkspace,
    toggleWorkspaceShowAll,
  };
}

function splitStreamDisplayUnits(text: string): string[] {
  if (typeof Intl !== "undefined" && typeof Intl.Segmenter !== "undefined") {
    const segmenter = new Intl.Segmenter(undefined, { granularity: "grapheme" });
    return Array.from(segmenter.segment(text), (item) => item.segment);
  }
  return Array.from(text);
}

const STREAM_REVEAL_START_BUFFER = 32;
const STREAM_REVEAL_WARMUP_MS = 160;

function resolveStreamRevealBatchSize(bufferLength: number, sourceCompleted: boolean): number {
  if (sourceCompleted) {
    if (bufferLength > 160) return 10;
    if (bufferLength > 96) return 7;
    if (bufferLength > 48) return 5;
    if (bufferLength > 24) return 3;
    if (bufferLength > 10) return 2;
    return 1;
  }
  if (bufferLength > 160) return 4;
  if (bufferLength > 96) return 3;
  if (bufferLength > 40) return 2;
  return 1;
}
