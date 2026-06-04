import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { ShinyText } from "@/components/ui/shiny-text";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { BuilderMessage } from "../../model/mockBuilderAgent";
import { BuilderConversationMenu } from "./BuilderConversationMenu";
import { BuilderMessageText } from "./BuilderMessageText";

interface BuilderConversationViewProps {
  activeConversationId: string | null;
  currentWorkspaceId: string | null;
  currentWorkspacePath: string | null;
  conversationSubtitle: string;
  conversationTitle: string;
  messages: BuilderMessage[];
  onArchiveConversation: (conversationId: string) => void;
  onCreatePermanentWorktree: (workspaceId: string) => void;
  onOpenWorkspaceInExplorer: (workspaceId: string) => void;
  onRenameConversation: (conversationId: string) => void;
  registerScrollToLatest: (callback: () => void) => void;
}

export function BuilderConversationView({
  activeConversationId,
  currentWorkspaceId,
  currentWorkspacePath,
  conversationSubtitle,
  conversationTitle,
  messages,
  onArchiveConversation,
  onCreatePermanentWorktree,
  onOpenWorkspaceInExplorer,
  onRenameConversation,
  registerScrollToLatest,
}: BuilderConversationViewProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const followOutputRef = useRef(true);
  const scrollFrameRef = useRef<number | null>(null);
  const scrollTargetRef = useRef<number>(0);
  const lastScrollTopRef = useRef(0);
  const programmaticScrollRef = useRef(false);
  const pendingInitialPositionRef = useRef(false);
  const lastConversationIdRef = useRef<string | null>(null);
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);

  const setFollowOutput = useCallback((shouldFollow: boolean) => {
    followOutputRef.current = shouldFollow;
    setShowJumpToBottom((current) => (current === !shouldFollow ? current : !shouldFollow));
  }, []);

  const animateScrollToBottom = useCallback((options?: { forceFollow?: boolean; speed?: number; maxStep?: number; minStep?: number }) => {
    const container = scrollRef.current;
    if (!container) return;

    const forceFollow = options?.forceFollow ?? true;
    const speed = options?.speed ?? 0.1;
    const maxStep = options?.maxStep ?? 14;
    const minStep = options?.minStep ?? 0.65;

    if (forceFollow) {
      setFollowOutput(true);
    } else if (!followOutputRef.current) {
      return;
    }
    scrollTargetRef.current = Math.max(0, container.scrollHeight - container.clientHeight);
    if (scrollFrameRef.current !== null) {
      return;
    }

    const step = () => {
      const activeContainer = scrollRef.current;
      if (!activeContainer) {
        scrollFrameRef.current = null;
        return;
      }

      if (!followOutputRef.current) {
        scrollFrameRef.current = null;
        return;
      }

      const target = scrollTargetRef.current;
      const current = activeContainer.scrollTop;
      const distance = target - current;

      if (Math.abs(distance) <= 0.8) {
        activeContainer.scrollTop = target;
        setFollowOutput(true);
        lastScrollTopRef.current = target;
        scrollFrameRef.current = null;
        return;
      }

      const nextTop =
        current + Math.sign(distance) * Math.min(maxStep, Math.max(minStep, Math.abs(distance) * speed));
      programmaticScrollRef.current = true;
      activeContainer.scrollTop = distance > 0 ? Math.min(target, nextTop) : Math.max(target, nextTop);
      scrollFrameRef.current = window.requestAnimationFrame(step);
    };

    scrollFrameRef.current = window.requestAnimationFrame(step);
  }, [setFollowOutput]);

  const startSmoothScrollToBottom = useCallback(() => {
    animateScrollToBottom({
      forceFollow: false,
      speed: 0.095,
      maxStep: 13,
      minStep: 0.6,
    });
  }, [animateScrollToBottom]);

  const scrollToLatestFromComposer = useCallback(() => {
    animateScrollToBottom({
      forceFollow: true,
      speed: 0.18,
      maxStep: 22,
      minStep: 1.2,
    });
  }, [animateScrollToBottom]);

  const jumpToBottomQuick = useCallback(() => {
    const container = scrollRef.current;
    if (!container) return;

    setFollowOutput(true);
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = null;
    }
    const target = Math.max(0, container.scrollHeight - container.clientHeight);
    programmaticScrollRef.current = true;
    container.scrollTop = target;
    lastScrollTopRef.current = target;
  }, [setFollowOutput]);

  useEffect(() => {
    registerScrollToLatest(scrollToLatestFromComposer);
    return () => {
      registerScrollToLatest(() => {});
    };
  }, [registerScrollToLatest, scrollToLatestFromComposer]);

  useEffect(() => {
    if (activeConversationId !== lastConversationIdRef.current) {
      lastConversationIdRef.current = activeConversationId;
      pendingInitialPositionRef.current = true;
    }
  }, [activeConversationId]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !pendingInitialPositionRef.current) {
      return;
    }

    const target = Math.max(0, container.scrollHeight - container.clientHeight);
    programmaticScrollRef.current = true;
    container.scrollTop = target;
    lastScrollTopRef.current = target;

    const hasStreamingMessage = messages.some((message) => message.isStreaming);
    setFollowOutput(hasStreamingMessage);
    pendingInitialPositionRef.current = false;
  }, [messages, setFollowOutput]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    lastScrollTopRef.current = container.scrollTop;

    const updateFollowMode = () => {
      const currentTop = container.scrollTop;
      const wasProgrammatic = programmaticScrollRef.current;
      programmaticScrollRef.current = false;

      const distanceFromBottom = container.scrollHeight - currentTop - container.clientHeight;
      const isNearBottom = distanceFromBottom <= 48;

      if (isNearBottom) {
        setFollowOutput(true);
      } else if (!wasProgrammatic || currentTop < lastScrollTopRef.current) {
        setFollowOutput(false);
        if (currentTop < lastScrollTopRef.current && scrollFrameRef.current !== null) {
          window.cancelAnimationFrame(scrollFrameRef.current);
          scrollFrameRef.current = null;
        }
      }

      lastScrollTopRef.current = currentTop;
    };

    updateFollowMode();
    container.addEventListener("scroll", updateFollowMode);

    return () => {
      container.removeEventListener("scroll", updateFollowMode);
    };
  }, [setFollowOutput]);

  useEffect(() => {
    if (!followOutputRef.current) return;
    startSmoothScrollToBottom();
  }, [messages, startSmoothScrollToBottom]);

  useEffect(() => {
    const container = scrollRef.current;
    const content = contentRef.current;
    if (!container || !content) {
      return;
    }

    let lastObservedHeight = content.getBoundingClientRect().height;
    const handleContentGrowth = (nextHeight: number) => {
      if (Math.abs(nextHeight - lastObservedHeight) <= 0.5) {
        return;
      }

      lastObservedHeight = nextHeight;
      if (followOutputRef.current) {
        startSmoothScrollToBottom();
      }
    };

    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver((entries) => {
            const entry = entries[0];
            if (!entry) return;
            handleContentGrowth(entry.contentRect.height);
          })
        : null;

    const mutationObserver =
      typeof MutationObserver !== "undefined"
        ? new MutationObserver(() => {
            const nextHeight = content.getBoundingClientRect().height;
            handleContentGrowth(nextHeight);
          })
        : null;

    resizeObserver?.observe(content);
    mutationObserver?.observe(content, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
    });

    return () => {
      resizeObserver?.disconnect();
      mutationObserver?.disconnect();
    };
  }, [startSmoothScrollToBottom]);

  useEffect(() => () => {
    if (scrollFrameRef.current !== null) {
      window.cancelAnimationFrame(scrollFrameRef.current);
    }
    programmaticScrollRef.current = false;
  }, []);

  return (
    <>
      <div className="app-no-drag relative z-20 bg-surface px-8 py-3.5">
        <div className="flex items-center gap-3">
          <div className="min-w-0 flex items-center gap-2.5">
            <h2 className="truncate text-[14px] font-semibold tracking-[-0.02em] text-txt-primary">
              {conversationTitle}
            </h2>
            {currentWorkspaceId && currentWorkspacePath ? (
              <Tooltip delayDuration={500}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => onOpenWorkspaceInExplorer(currentWorkspaceId)}
                    className="truncate text-[13px] text-txt-secondary transition-colors hover:text-txt-primary"
                  >
                    {conversationSubtitle}
                  </button>
                </TooltipTrigger>
                <TooltipContent
                  side="bottom"
                  align="start"
                  sideOffset={8}
                  className="rounded-xl border border-[#3a3732] bg-[#2a2723] px-3 py-1.5 text-xs text-white shadow-md"
                >
                  <button
                    type="button"
                    onClick={() => onOpenWorkspaceInExplorer(currentWorkspaceId)}
                    className="text-left font-medium text-white"
                  >
                    Open folder&nbsp; {currentWorkspacePath}
                  </button>
                </TooltipContent>
              </Tooltip>
            ) : (
              <span className="truncate text-[13px] text-txt-secondary">{conversationSubtitle}</span>
            )}
            <BuilderConversationMenu
              activeConversationId={activeConversationId}
              currentWorkspaceId={currentWorkspaceId}
              currentWorkspacePath={currentWorkspacePath}
              onArchiveConversation={onArchiveConversation}
              onCreatePermanentWorktree={onCreatePermanentWorktree}
              onRenameConversation={onRenameConversation}
            />
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="hide-scrollbar relative flex-1 overflow-y-auto dotted-bg px-8 py-8">
        <div ref={contentRef} className="mx-auto flex w-full max-w-[980px] flex-col gap-4">
          {messages.map((message) =>
            message.role === "user" ? (
              <div
                key={message.id}
                className="ml-auto max-w-[70%] rounded-[22px] border border-[#1e1b18] bg-[#1e1b18] px-[18px] py-3.5 text-[14px] leading-[1.65rem] text-white shadow-card"
              >
                <BuilderMessageText text={message.text} isStreaming={false} tone="inverted" />
              </div>
            ) : (
              <div key={message.id} className="max-w-[90%] px-2 py-1 text-[14px] leading-7 text-txt-primary">
                <div className="space-y-2">
                  {message.isStreaming && !message.text && (
                    <div className="inline-flex items-center px-1 py-1 text-[13px] text-[#6d655c]">
                      <ShinyText
                        text="Thinking"
                        className="leading-none"
                        color="#737373"
                        shineColor="#ffffff"
                        speed={2.2}
                        spread={70}
                        direction="left"
                        yoyo={false}
                      />
                    </div>
                  )}
                  {message.text && (
                    <BuilderMessageText text={message.text} isStreaming={Boolean(message.isStreaming)} />
                  )}
                </div>
              </div>
            ),
          )}
        </div>
        {showJumpToBottom && (
          <div className="pointer-events-none sticky bottom-4 z-10 mt-6 flex justify-center">
            <button
              type="button"
              onClick={jumpToBottomQuick}
              aria-label="Jump to latest message"
              className="pointer-events-auto inline-flex h-11 w-11 items-center justify-center rounded-full border bg-card text-txt-primary shadow-[0_12px_24px_rgba(0,0,0,0.12)] transition-colors hover:bg-surface"
              style={{ borderColor: "hsl(var(--border-soft))" }}
            >
              <ChevronDown size={18} />
            </button>
          </div>
        )}
      </div>
    </>
  );
}
