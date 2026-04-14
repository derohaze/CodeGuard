import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Archive,
  ArrowUp,
  ChevronDown,
  Check,
  CircleAlert,
  Copy,
  Ellipsis,
  FilePlus2,
  FolderTree,
  GitFork,
  Link2,
  ListTodo,
  Mic,
  PencilLine,
  PinOff,
  Plus,
  Sparkles,
  Square,
  Shield,
  ShieldAlert,
  TimerReset,
  X,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { BuilderMessage, BuilderPromptSuggestion } from "../model/mockBuilderAgent";

interface BuilderChatScreenProps {
  activeConversationId: string | null;
  composerSettings: {
    permissionMode: "default" | "full-access";
    planMode: boolean;
    responseSpeed: "normal" | "speed";
    attachedFiles: string[];
  };
  currentWorkspaceId: string | null;
  currentWorkspacePath: string | null;
  conversationTitle: string;
  conversationSubtitle: string;
  draft: string;
  isNewChat: boolean;
  isStreaming: boolean;
  messages: BuilderMessage[];
  promptSuggestions: BuilderPromptSuggestion[];
  onArchiveConversation: (conversationId: string) => void;
  onOpenWorkspaceInExplorer: (workspaceId: string) => void;
  onPermissionModeChange: (mode: "default" | "full-access") => void;
  onPickAttachment: () => void;
  onPlanModeChange: (enabled: boolean) => void;
  onRenameConversation: (conversationId: string) => void;
  onDraftChange: (value: string) => void;
  onRemoveAttachment: (path: string) => void;
  onSend: () => void;
  onStopStreaming: () => void;
  onCreatePermanentWorktree: (workspaceId: string) => void;
}

export function BuilderChatScreen({
  activeConversationId,
  composerSettings,
  currentWorkspaceId,
  currentWorkspacePath,
  conversationTitle,
  conversationSubtitle,
  draft,
  isNewChat,
  isStreaming,
  messages,
  promptSuggestions,
  onArchiveConversation,
  onOpenWorkspaceInExplorer,
  onPermissionModeChange,
  onPickAttachment,
  onPlanModeChange,
  onRenameConversation,
  onDraftChange,
  onRemoveAttachment,
  onSend,
  onStopStreaming,
  onCreatePermanentWorktree,
}: BuilderChatScreenProps) {
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [pendingPermissionMode, setPendingPermissionMode] = useState<"default" | "full-access" | null>(null);
  const [isPermissionDialogOpen, setIsPermissionDialogOpen] = useState(false);
  const contextUsage = 85;

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (isStreaming) {
      onStopStreaming();
      return;
    }
    if (!draft.trim()) return;
    onSend();
  };

  useEffect(() => {
    const element = inputRef.current;
    if (!element) return;

    element.style.height = "0px";
    element.style.height = `${Math.min(Math.max(element.scrollHeight, 26), 168)}px`;
  }, [draft]);

  const getPermissionSeenKey = (mode: "default" | "full-access") => `builder-permission-confirmed:${mode}`;

  const requestPermissionModeChange = (mode: "default" | "full-access") => {
    if (mode === composerSettings.permissionMode) return;

    if (mode === "default") {
      onPermissionModeChange(mode);
      return;
    }

    const hasSeenDialog =
      typeof window !== "undefined" && window.localStorage.getItem(getPermissionSeenKey(mode)) === "true";

    if (hasSeenDialog) {
      onPermissionModeChange(mode);
      return;
    }

    setPendingPermissionMode(mode);
    setIsPermissionDialogOpen(true);
  };

  const handleConfirmPermissionModeChange = () => {
    if (!pendingPermissionMode) return;

    if (typeof window !== "undefined") {
      window.localStorage.setItem(getPermissionSeenKey(pendingPermissionMode), "true");
    }

    onPermissionModeChange(pendingPermissionMode);
    setIsPermissionDialogOpen(false);
    setPendingPermissionMode(null);
  };

  const handleCancelPermissionModeChange = () => {
    setIsPermissionDialogOpen(false);
    setPendingPermissionMode(null);
  };

  const permissionDialogCopy = {
    title: "Enable full access?",
    body:
      "When CodeGuard runs with full access, it can edit files across your computer and run commands with network access without asking first.\n\nUse this only if you trust the current project. Full access increases the risk of unwanted edits, leaks, or data loss.",
    confirm: "Yes, continue anyway",
  };

  return (
    <motion.div
      initial={false}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.14 }}
      className="flex min-h-0 flex-1 flex-col bg-surface"
    >
      {isNewChat ? (
        <BuilderNewChat promptSuggestions={promptSuggestions} workspaceLabel={conversationSubtitle} />
      ) : (
        <BuilderConversationView
          activeConversationId={activeConversationId}
          currentWorkspaceId={currentWorkspaceId}
          currentWorkspacePath={currentWorkspacePath}
          conversationSubtitle={conversationSubtitle}
          conversationTitle={conversationTitle}
          messages={messages}
          onArchiveConversation={onArchiveConversation}
          onCreatePermanentWorktree={onCreatePermanentWorktree}
          onOpenWorkspaceInExplorer={onOpenWorkspaceInExplorer}
          onRenameConversation={onRenameConversation}
        />
      )}

      <div className="bg-surface px-8 py-3">
        <div className="mx-auto flex w-full max-w-[980px] flex-col gap-1.5">
          <div
            className="w-full rounded-[28px] border bg-card px-4 py-2.5 shadow-[0_14px_28px_rgba(52,42,28,0.05)]"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            {composerSettings.attachedFiles.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {composerSettings.attachedFiles.map((filePath) => (
                  <div
                    key={filePath}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-full border bg-surface px-2.5 py-1 text-[12px] text-txt-primary"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    <span className="truncate">{basename(filePath)}</span>
                    <button
                      type="button"
                      className="inline-flex h-4 w-4 items-center justify-center rounded-full text-txt-secondary transition-colors hover:bg-muted hover:text-txt-primary"
                      onClick={() => onRemoveAttachment(filePath)}
                      aria-label={`Remove ${basename(filePath)}`}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <Textarea
              ref={inputRef}
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask CodeGuard Builder anything..."
              rows={1}
              className="min-h-[22px] max-h-[152px] resize-none overflow-y-auto border-0 bg-transparent px-0 py-0 text-[14px] leading-6 text-txt-primary shadow-none outline-none ring-0 placeholder:text-txt-secondary focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />

            <div className="mt-2.5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 text-txt-secondary">
                <Popover>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded-[10px] transition-colors hover:bg-muted"
                      aria-label="Composer tools"
                    >
                      <Plus size={16} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent
                    side="top"
                    align="start"
                    sideOffset={12}
                    className="w-[220px] rounded-[18px] border border-border-soft bg-card p-1.5 text-txt-primary shadow-[0_16px_30px_rgba(52,42,28,0.12)]"
                  >
                    <button
                      type="button"
                      onClick={onPickAttachment}
                      className="flex w-full items-center gap-2.5 rounded-[14px] border border-border-soft bg-surface px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-muted"
                    >
                      <FilePlus2 size={14} className="text-txt-secondary" />
                      <span>Add photos &amp; files</span>
                    </button>
                    <div className="mt-1 flex items-center justify-between rounded-[14px] px-2.5 py-2">
                      <div className="flex items-center gap-2.5">
                        <ListTodo size={14} className="text-txt-secondary" />
                        <p className="text-[13px] text-txt-primary">Plan mode</p>
                      </div>
                      <Switch
                        checked={composerSettings.planMode}
                        onCheckedChange={onPlanModeChange}
                        className="h-5 w-8 [&>span]:h-3.5 [&>span]:w-3.5 [&>span[data-state=checked]]:translate-x-3"
                      />
                    </div>
                  </PopoverContent>
                </Popover>
                {composerSettings.planMode && (
                  <div className="inline-flex h-7 items-center gap-1.5 rounded-full bg-[#edf4ff] px-2.5 text-[13px] font-medium text-[#3f6fb2]">
                    <ListTodo size={13} />
                    <span>Plan</span>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full text-txt-secondary transition-colors hover:bg-muted hover:text-txt-primary"
                  aria-label="Voice input"
                >
                  <Mic size={15} />
                </button>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <button
                      className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground transition-opacity hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-45"
                      type="button"
                      onClick={isStreaming ? onStopStreaming : onSend}
                      disabled={!isStreaming && !draft.trim()}
                      aria-label={isStreaming ? "Stop response" : "Send message"}
                    >
                      {isStreaming ? <Square size={14} fill="currentColor" /> : <ArrowUp size={16} />}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    align="center"
                    sideOffset={10}
                    className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md"
                  >
                    {isStreaming ? "Stop response" : "Send"}
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-2 text-[12px] text-txt-secondary">
              <button className="inline-flex h-6 items-center gap-1.5 rounded-full px-2 transition-colors hover:bg-muted">
                <span>Local</span>
                <ChevronDown size={12} />
              </button>
              <DropdownMenu>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <button
                        className={`inline-flex h-6 items-center gap-1.5 rounded-full px-2 transition-colors hover:bg-muted ${
                          composerSettings.permissionMode === "full-access" ? "text-[#bf6e21]" : "text-txt-secondary"
                        }`}
                      >
                        {composerSettings.permissionMode === "full-access" ? (
                          <CircleAlert size={13} />
                        ) : (
                          <Shield size={13} />
                        )}
                        <span>{composerSettings.permissionMode === "full-access" ? "Full access" : "Default permissions"}</span>
                        <ChevronDown size={12} />
                      </button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    align="center"
                    sideOffset={10}
                    className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md"
                  >
                    Change permissions
                  </TooltipContent>
                </Tooltip>
                <DropdownMenuContent
                  side="top"
                  align="start"
                  sideOffset={10}
                  className="w-[200px] rounded-[16px] border border-border-soft bg-card p-1.5 text-txt-primary shadow-[0_16px_30px_rgba(52,42,28,0.12)]"
                >
                  <DropdownMenuRadioGroup
                    value={composerSettings.permissionMode}
                    onValueChange={(value) => requestPermissionModeChange(value as "default" | "full-access")}
                  >
                    <DropdownMenuRadioItem value="default" className="rounded-[12px] text-[13px]">
                      <div className="flex items-center gap-2">
                        <Shield size={14} className="text-txt-secondary" />
                        <span>Default permissions</span>
                      </div>
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="full-access" className="rounded-[12px] text-[13px]">
                      <div className="flex items-center gap-2">
                        <ShieldAlert size={14} className="text-[#bf6e21]" />
                        <span>Full access</span>
                      </div>
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex h-5 w-5 items-center justify-center text-[#8e8577]"
                  aria-label="Context window usage"
                >
                  <ContextUsageRing value={contextUsage} />
                </button>
              </TooltipTrigger>
              <TooltipContent
                side="top"
                align="end"
                sideOffset={10}
                className="rounded-2xl border border-border-soft bg-surface px-3 py-2 text-center text-xs text-txt-primary shadow-md"
              >
                <p>Context window</p>
                <p className="font-medium">{contextUsage}% full</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>

      <AlertDialog open={isPermissionDialogOpen} onOpenChange={setIsPermissionDialogOpen}>
        <AlertDialogContent className="max-w-[660px] rounded-[28px] border border-border-soft bg-card p-0 text-txt-primary shadow-[0_24px_64px_rgba(52,42,28,0.12)] [&>button]:hidden [&>div[data-radix-alert-dialog-overlay]]:bg-transparent">
          <div className="px-9 py-8">
            <AlertDialogHeader className="space-y-4 text-left">
              <AlertDialogTitle className="text-[18px] font-semibold tracking-[-0.02em] text-txt-primary">
                {permissionDialogCopy.title}
              </AlertDialogTitle>
              <AlertDialogDescription className="whitespace-pre-line text-[15px] leading-8 text-txt-secondary">
                {permissionDialogCopy.body}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="mt-8 flex-row justify-end gap-3 space-x-0">
              <AlertDialogCancel
                onClick={handleCancelPermissionModeChange}
                className="mt-0 rounded-2xl border border-border-soft bg-surface px-6 py-2.5 text-[15px] font-medium text-txt-primary hover:bg-muted"
              >
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleConfirmPermissionModeChange}
                className="rounded-2xl border-0 bg-[#6a4036] px-6 py-2.5 text-[15px] font-medium text-[#fff4f0] hover:bg-[#7a4b3f]"
              >
                {permissionDialogCopy.confirm}
              </AlertDialogAction>
            </AlertDialogFooter>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </motion.div>
  );
}

function basename(filePath: string) {
  const normalized = filePath.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? filePath;
}

function BuilderMessageText({ text, isStreaming }: { text: string; isStreaming: boolean }) {
  return (
    <p
      dir="auto"
      className="whitespace-pre-wrap break-words text-start"
      style={{ unicodeBidi: "plaintext" }}
    >
      {text}
      {isStreaming && <span className="ml-0.5 inline-block h-5 w-[2px] animate-pulse align-[-2px] bg-current opacity-45" />}
    </p>
  );
}

function ContextUsageRing({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = 5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - clamped / 100);

  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <circle
        cx="7"
        cy="7"
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.22"
        strokeWidth="1.6"
      />
      <circle
        cx="7"
        cy="7"
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        transform="rotate(-90 7 7)"
      />
    </svg>
  );
}

function BuilderConversationView({
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
}: {
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
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const followOutputRef = useRef(true);
  const scrollFrameRef = useRef<number | null>(null);
  const scrollTargetRef = useRef<number>(0);
  const lastScrollTopRef = useRef(0);
  const programmaticScrollRef = useRef(false);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    lastScrollTopRef.current = container.scrollTop;

    const updateFollowMode = () => {
      const currentTop = container.scrollTop;
      const wasProgrammatic = programmaticScrollRef.current;
      programmaticScrollRef.current = false;

      const distanceFromBottom =
        container.scrollHeight - currentTop - container.clientHeight;
      const isNearBottom = distanceFromBottom <= 48;

      if (isNearBottom) {
        followOutputRef.current = true;
      } else if (!wasProgrammatic || currentTop < lastScrollTopRef.current) {
        followOutputRef.current = false;
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
  }, []);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !followOutputRef.current) return;

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

      if (Math.abs(distance) <= 1) {
        activeContainer.scrollTop = target;
        followOutputRef.current = true;
        lastScrollTopRef.current = target;
        scrollFrameRef.current = null;
        return;
      }

      const nextTop =
        current + Math.sign(distance) * Math.max(1, Math.abs(distance) * 0.16);
      programmaticScrollRef.current = true;
      activeContainer.scrollTop = distance > 0 ? Math.min(target, nextTop) : Math.max(target, nextTop);
      scrollFrameRef.current = window.requestAnimationFrame(step);
    };

    scrollFrameRef.current = window.requestAnimationFrame(step);
  }, [messages]);

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

      <div ref={scrollRef} className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8">
        <div className="mx-auto flex w-full max-w-[980px] flex-col gap-4">
          {messages.map((message) =>
            message.role === "user" ? (
              <div
                key={message.id}
                className="ml-auto max-w-[72%] rounded-[24px] border border-[#1e1b18] bg-[#1e1b18] px-5 py-4 text-[15px] leading-7 text-white shadow-card"
              >
                <BuilderMessageText text={message.text} isStreaming={false} />
              </div>
            ) : (
              <div
                key={message.id}
                className="max-w-[92%] px-2 py-1 text-[15px] leading-8 text-txt-primary"
              >
                <div className="space-y-2">
                  {message.isStreaming && !message.text && (
                    <div className="inline-flex items-center gap-2 rounded-full bg-[#f3ece0] px-3 py-1.5 text-[13px] text-[#6d655c]">
                      <span className="flex gap-1">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current [animation-delay:0ms]" />
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current [animation-delay:150ms]" />
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current [animation-delay:300ms]" />
                      </span>
                      <span>Thinking...</span>
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
      </div>
    </>
  );
}

function BuilderConversationMenu({
  activeConversationId,
  currentWorkspaceId,
  currentWorkspacePath,
  onArchiveConversation,
  onCreatePermanentWorktree,
  onRenameConversation,
}: {
  activeConversationId: string | null;
  currentWorkspaceId: string | null;
  currentWorkspacePath: string | null;
  onArchiveConversation: (conversationId: string) => void;
  onCreatePermanentWorktree: (workspaceId: string) => void;
  onRenameConversation: (conversationId: string) => void;
}) {
  const handleCopy = async (value: string | null) => {
    if (!value || typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Ignore clipboard failures in the mock frontend flow.
    }
  };

  const deeplink = activeConversationId ? `codeguard://builder/${activeConversationId}` : null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="app-no-drag inline-flex h-6 items-center justify-center px-1 text-txt-secondary transition-colors hover:text-txt-primary"
          aria-label="Conversation options"
        >
          <Ellipsis size={15} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        sideOffset={10}
        className="w-[300px] rounded-[18px] border border-border-soft bg-card p-1.5 text-txt-primary shadow-[0_18px_36px_rgba(52,42,28,0.14)]"
      >
        <DropdownMenuItem className="rounded-[12px] px-3 py-2.5 text-[13px]" disabled>
          <PinOff size={15} className="mr-2.5 text-txt-secondary" />
          <span>Unpin chat</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Alt+P</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!activeConversationId}
          onSelect={() => activeConversationId && onRenameConversation(activeConversationId)}
        >
          <PencilLine size={15} className="mr-2.5 text-txt-secondary" />
          <span>Rename chat</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Win+R</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!activeConversationId}
          onSelect={() => activeConversationId && onArchiveConversation(activeConversationId)}
        >
          <Archive size={15} className="mr-2.5 text-txt-secondary" />
          <span>Archive chat</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Shift+A</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!currentWorkspacePath}
          onSelect={() => void handleCopy(currentWorkspacePath)}
        >
          <FolderTree size={15} className="mr-2.5 text-txt-secondary" />
          <span>Copy working directory</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Shift+C</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!activeConversationId}
          onSelect={() => void handleCopy(activeConversationId)}
        >
          <Copy size={15} className="mr-2.5 text-txt-secondary" />
          <span>Copy session ID</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Alt+C</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!deeplink}
          onSelect={() => void handleCopy(deeplink)}
        >
          <Link2 size={15} className="mr-2.5 text-txt-secondary" />
          <span>Copy deeplink</span>
          <DropdownMenuShortcut className="text-[12px] tracking-normal opacity-100">Ctrl+Alt+L</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="rounded-[12px] px-3 py-2.5 text-[13px]" disabled>
          <GitFork size={15} className="mr-2.5 text-txt-secondary" />
          <span>Fork into local</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="rounded-[12px] px-3 py-2.5 text-[13px]"
          disabled={!currentWorkspaceId}
          onSelect={() => currentWorkspaceId && onCreatePermanentWorktree(currentWorkspaceId)}
        >
          <GitFork size={15} className="mr-2.5 text-txt-secondary" />
          <span>Fork into new worktree</span>
        </DropdownMenuItem>
        <DropdownMenuItem className="rounded-[12px] px-3 py-2.5 text-[13px]" disabled>
          <TimerReset size={15} className="mr-2.5 text-txt-secondary" />
          <span>Add automation...</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function BuilderNewChat({
  promptSuggestions,
  workspaceLabel,
}: {
  promptSuggestions: BuilderPromptSuggestion[];
  workspaceLabel: string;
}) {
  return (
    <div className="flex flex-1 items-center justify-center dotted-bg px-8 py-10">
      <div className="mx-auto flex w-full max-w-[980px] flex-col items-center">
        <h2 className="text-[42px] font-semibold tracking-[-0.05em] text-txt-primary">Let&apos;s build</h2>
        <p className="mt-2 text-[18px] text-txt-secondary">{workspaceLabel}</p>

        <div className="mt-12 grid w-full grid-cols-3 gap-4 max-[1100px]:grid-cols-1">
          {promptSuggestions.map((suggestion) => (
            <button
              key={suggestion.id}
              type="button"
              className="rounded-[24px] border bg-[#f5efe3] px-5 py-5 text-left shadow-[0_10px_24px_rgba(52,42,28,0.05)] transition-colors hover:bg-[#efe6d4]"
              style={{ borderColor: "hsl(var(--border-soft))" }}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-card text-[#8a775b]">
                <Sparkles size={16} />
              </div>
              <p className="mt-4 text-[18px] font-medium leading-7 text-txt-primary">{suggestion.title}</p>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">{suggestion.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
