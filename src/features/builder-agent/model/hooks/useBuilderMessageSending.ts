import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  sendBuilderMessage,
  sendBuilderMessageStream,
} from "../builderApi";
import type { BuilderMessage } from "../mockBuilderAgent";
import type { BuilderContextState } from "../lib/context-window";
import type { BuilderComposerSettings } from "../lib/types";
import { mapMessage } from "../lib/mappers";
import {
  builderStreamConfig,
  resolveStreamRevealBatchSize,
  resolveStreamingCharsPerSecond,
  splitStreamDisplayUnits,
} from "../lib/streaming";

const PREPARE_RESPONSE_DURATION_MS = 240;
const PREPARE_RESPONSE_TICK_MS = 16;

interface UseBuilderMessageSendingParams {
  activeConversationId: string | null;
  composerSettings: BuilderComposerSettings;
  currentWorkspaceId: string | null;
  currentWorkspace: { id: string } | null;
  draft: string;
  refreshWorkspaces: () => Promise<void>;
  setActiveConversationId: Dispatch<SetStateAction<string | null>>;
  setContextStateMap: Dispatch<SetStateAction<Record<string, BuilderContextState | null>>>;
  setCurrentWorkspaceId: Dispatch<SetStateAction<string | null>>;
  setDraft: Dispatch<SetStateAction<string>>;
  setMessageMap: Dispatch<SetStateAction<Record<string, BuilderMessage[]>>>;
}

export function useBuilderMessageSending({
  activeConversationId,
  composerSettings,
  currentWorkspace,
  draft,
  refreshWorkspaces,
  setActiveConversationId,
  setContextStateMap,
  setCurrentWorkspaceId,
  setDraft,
  setMessageMap,
}: UseBuilderMessageSendingParams) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPreparingResponse, setIsPreparingResponse] = useState(false);
  const [prepareProgress, setPrepareProgress] = useState(0);
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
  const streamRevealBudgetRef = useRef(0);
  const streamLastDrainAtRef = useRef<number | null>(null);

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
  }, [setMessageMap]);

  const markActiveAssistantStopped = useCallback(() => {
    const threadId = activeStreamThreadIdRef.current;
    const assistantId = activeStreamAssistantIdRef.current;
    if (!threadId || !assistantId) {
      return;
    }
    markAssistantStopped(threadId, assistantId);
  }, [markAssistantStopped]);

  const stopStreaming = useCallback(() => {
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
    streamRevealBudgetRef.current = 0;
    streamLastDrainAtRef.current = null;
    setIsPreparingResponse(false);
    setPrepareProgress(0);
    markActiveAssistantStopped();
    if (streamDrainResolverRef.current) {
      streamDrainResolverRef.current();
      streamDrainResolverRef.current = null;
    }
    setIsStreaming(false);
  }, [markActiveAssistantStopped]);

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

  const sendMessage = useCallback(() => {
    void (async () => {
      const prompt = draft.trim();
      if (!prompt || !currentWorkspace) return;

      const requestThreadId = activeConversationId;
      const startedInNewChat = !requestThreadId;
      const tempThreadId = startedInNewChat ? `local-thread-${Date.now()}` : null;
      let renderThreadId = requestThreadId ?? tempThreadId;
      if (!renderThreadId) return;

      const optimisticUserMessage: BuilderMessage = {
        id: `local-user-${Date.now()}`,
        role: "user",
        text: prompt,
      };
      const optimisticAssistantId = `local-assistant-${Date.now() + 1}`;
      const abortController = new AbortController();
      activeSendAbortRef.current = abortController;
      activeStreamThreadIdRef.current = renderThreadId;
      activeStreamAssistantIdRef.current = optimisticAssistantId;
      setIsPreparingResponse(true);
      setPrepareProgress(0);
      streamUnitsRef.current = [];
      streamVisibleTextRef.current = "";
      streamSourceCompletedRef.current = false;
      streamDrainStartedRef.current = false;
      streamRevealBudgetRef.current = 0;
      streamLastDrainAtRef.current = null;

      try {
        await new Promise<void>((resolve) => {
          const startedAt = Date.now();
          const timer = window.setInterval(() => {
            if (abortController.signal.aborted || activeSendAbortRef.current !== abortController) {
              window.clearInterval(timer);
              resolve();
              return;
            }

            const elapsed = Date.now() - startedAt;
            const nextProgress = Math.min(100, Math.round((elapsed / PREPARE_RESPONSE_DURATION_MS) * 100));
            setPrepareProgress(nextProgress);

            if (elapsed >= PREPARE_RESPONSE_DURATION_MS) {
              window.clearInterval(timer);
              setPrepareProgress(100);
              resolve();
            }
          }, PREPARE_RESPONSE_TICK_MS);
        });

        if (abortController.signal.aborted || activeSendAbortRef.current !== abortController) {
          return;
        }

        setMessageMap((current) => ({
          ...current,
          [renderThreadId!]: [
            ...(current[renderThreadId!] ?? []),
            optimisticUserMessage,
            {
              id: optimisticAssistantId,
              role: "assistant",
              text: "",
              isStreaming: true,
            },
          ],
        }));
        if (startedInNewChat) {
          setActiveConversationId(renderThreadId);
          setCurrentWorkspaceId(currentWorkspace.id);
          setContextStateMap((current) => ({
            ...current,
            [renderThreadId!]: null,
          }));
        }
        setDraft("");
        setIsPreparingResponse(false);
        setPrepareProgress(0);
        setIsStreaming(true);

        const payload = {
          workspaceId: currentWorkspace.id,
          threadId: requestThreadId,
          message: prompt,
          permissionMode: composerSettings.permissionMode,
          planMode: composerSettings.planMode,
          responseSpeed: composerSettings.responseSpeed,
        } as const;

        const moveOptimisticThread = (
          nextThreadId: string,
          nextWorkspaceId: string,
          contextState: BuilderContextState | null,
        ) => {
          const previousThreadId = renderThreadId;
          renderThreadId = nextThreadId;
          activeStreamThreadIdRef.current = nextThreadId;

          setMessageMap((current) => {
            if (previousThreadId === nextThreadId) {
              return current;
            }
            const next = { ...current };
            const previousMessages = next[previousThreadId];
            if (previousMessages) {
              next[nextThreadId] = previousMessages;
              delete next[previousThreadId];
            }
            return next;
          });
          setContextStateMap((current) => {
            if (previousThreadId === nextThreadId) {
              return {
                ...current,
                [nextThreadId]: contextState,
              };
            }
            const next = { ...current };
            const previousContext = next[previousThreadId] ?? null;
            next[nextThreadId] = contextState ?? previousContext;
            delete next[previousThreadId];
            return next;
          });
          setActiveConversationId(nextThreadId);
          setCurrentWorkspaceId(nextWorkspaceId);
        };

        const pushVisibleText = (nextText: string) => {
          streamVisibleTextRef.current = nextText;
          setMessageMap((current) => ({
            ...current,
            [renderThreadId!]: (current[renderThreadId!] ?? []).map((item) => (
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
          const now = typeof performance !== "undefined" ? performance.now() : Date.now();
          const lastDrainAt = streamLastDrainAtRef.current ?? now;
          streamLastDrainAtRef.current = now;

          if (!streamDrainStartedRef.current) {
            const shouldStart =
              streamSourceCompletedRef.current || bufferLength >= builderStreamConfig.startBuffer;
            if (!shouldStart) {
              return;
            }
            streamDrainStartedRef.current = true;
            streamLastDrainAtRef.current = now;
            streamRevealBudgetRef.current = Math.max(streamRevealBudgetRef.current, 1);
          }

          if (bufferLength === 0) {
            if (streamSourceCompletedRef.current) {
              finishDrainIfIdle();
              return;
            }
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
            return;
          }

          const charsPerSecond = streamSourceCompletedRef.current
            ? builderStreamConfig.completionCharsPerSecond
            : resolveStreamingCharsPerSecond(bufferLength);
          const elapsedMs = Math.max(0, now - lastDrainAt);
          streamRevealBudgetRef.current += (elapsedMs / 1000) * charsPerSecond;

          const batchSize = resolveStreamRevealBatchSize(
            bufferLength,
            streamSourceCompletedRef.current,
            streamRevealBudgetRef.current,
          );
          if (batchSize <= 0) {
            streamDrainFrameRef.current = window.requestAnimationFrame(drainBufferedText);
            return;
          }

          streamRevealBudgetRef.current = Math.max(0, streamRevealBudgetRef.current - batchSize);
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
          }, builderStreamConfig.warmupMs);
        };

        const enqueueToken = (token: string) => {
          streamUnitsRef.current.push(...splitStreamDisplayUnits(token));
          if (!streamDrainStartedRef.current) {
            if (streamUnitsRef.current.length >= builderStreamConfig.startBuffer) {
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
            onAck: ({ threadId: acknowledgedThreadId, workspaceId, contextState }) => {
              setIsPreparingResponse(false);
              if (startedInNewChat) {
                moveOptimisticThread(acknowledgedThreadId, workspaceId, contextState);
              }
            },
            onToken: (token) => {
              setIsPreparingResponse(false);
              enqueueToken(token);
            },
            onContextState: (contextState) => {
              setIsPreparingResponse(false);
              setContextStateMap((current) => ({
                ...current,
                [renderThreadId!]: contextState,
              }));
            },
            onReasoning: () => {
              setIsPreparingResponse(false);
              // Builder chat should stream only the visible assistant answer.
            },
          },
          abortController.signal,
        );
        await waitForDrain();

        if (!result) {
          result = await sendBuilderMessage(payload, abortController.signal);
        }
        setIsPreparingResponse(false);
        setPrepareProgress(0);

        setMessageMap((current) => {
          const next = { ...current };
          if (renderThreadId !== result.thread.id) {
            delete next[renderThreadId!];
          }
          next[result.thread.id] = result.thread.messages.map(mapMessage);
          return next;
        });
        setContextStateMap((current) => {
          const next = { ...current };
          if (renderThreadId !== result.thread.id) {
            delete next[renderThreadId!];
          }
          next[result.thread.id] = result.thread.contextState ?? null;
          return next;
        });
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
              threadId: requestThreadId,
              message: prompt,
              permissionMode: composerSettings.permissionMode,
              planMode: composerSettings.planMode,
              responseSpeed: composerSettings.responseSpeed,
            },
            abortController.signal,
          );
          setIsPreparingResponse(false);
          setPrepareProgress(0);
          setMessageMap((current) => {
            const next = { ...current };
            if (startedInNewChat && tempThreadId) {
              delete next[tempThreadId];
            }
            next[result.thread.id] = result.thread.messages.map(mapMessage);
            return next;
          });
          setContextStateMap((current) => {
            const next = { ...current };
            if (startedInNewChat && tempThreadId) {
              delete next[tempThreadId];
            }
            next[result.thread.id] = result.thread.contextState ?? null;
            return next;
          });
          setActiveConversationId(result.thread.id);
          setCurrentWorkspaceId(result.thread.workspaceId);
          await refreshWorkspaces();
        } catch (fallbackError) {
          setIsPreparingResponse(false);
          setPrepareProgress(0);
          if (startedInNewChat && tempThreadId) {
            setMessageMap((current) => {
              const next = { ...current };
              delete next[tempThreadId];
              return next;
            });
            setContextStateMap((current) => {
              const next = { ...current };
              delete next[tempThreadId];
              return next;
            });
            setActiveConversationId(null);
          }
          setDraft(prompt);
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
        streamRevealBudgetRef.current = 0;
        streamLastDrainAtRef.current = null;
        if (streamDrainResolverRef.current) {
          streamDrainResolverRef.current();
          streamDrainResolverRef.current = null;
        }
        markAssistantStopped(renderThreadId, optimisticAssistantId);
        streamVisibleTextRef.current = "";
        if (
          activeStreamThreadIdRef.current === renderThreadId &&
          activeStreamAssistantIdRef.current === optimisticAssistantId
        ) {
          activeStreamThreadIdRef.current = null;
          activeStreamAssistantIdRef.current = null;
        }
        if (activeSendAbortRef.current === abortController) {
          activeSendAbortRef.current = null;
          setIsPreparingResponse(false);
          setPrepareProgress(0);
          setIsStreaming(false);
        }
      }
    })();
  }, [
    activeConversationId,
    composerSettings.permissionMode,
    composerSettings.planMode,
    composerSettings.responseSpeed,
    currentWorkspace,
    draft,
    markAssistantStopped,
    refreshWorkspaces,
    setActiveConversationId,
    setContextStateMap,
    setCurrentWorkspaceId,
    setDraft,
    setMessageMap,
  ]);

  return {
    prepareProgress,
    isPreparingResponse,
    isStreaming,
    sendMessage,
    stopStreaming,
  };
}
