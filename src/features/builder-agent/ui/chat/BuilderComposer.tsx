import { useEffect, useRef, useState } from "react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Loader } from "@/shared/ui/Loader";
import {
  ArrowUp,
  ChevronDown,
  CircleAlert,
  FilePlus2,
  ListTodo,
  Mic,
  Plus,
  Shield,
  ShieldAlert,
  Square,
  X,
} from "lucide-react";
import { ProgressCircle } from "@/components/ui/progress-circle";
import type { BuilderComposerSettings } from "../../model/lib/types";
import type { BuilderContextUsage } from "../../model/lib/context-window";

interface BuilderComposerProps {
  composerSettings: BuilderComposerSettings;
  contextUsage: BuilderContextUsage;
  draft: string;
  prepareProgress: number;
  isPreparingResponse: boolean;
  isStreaming: boolean;
  onDraftChange: (value: string) => void;
  onPermissionModeChange: (mode: "default" | "full-access") => void;
  onPickAttachment: () => void;
  onPlanModeChange: (enabled: boolean) => void;
  onRemoveAttachment: (path: string) => void;
  onSend: () => void;
  onStopStreaming: () => void;
}

export function BuilderComposer({
  composerSettings,
  contextUsage,
  draft,
  prepareProgress,
  isPreparingResponse,
  isStreaming,
  onDraftChange,
  onPermissionModeChange,
  onPickAttachment,
  onPlanModeChange,
  onRemoveAttachment,
  onSend,
  onStopStreaming,
}: BuilderComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [pendingPermissionMode, setPendingPermissionMode] = useState<"default" | "full-access" | null>(null);
  const [isPermissionDialogOpen, setIsPermissionDialogOpen] = useState(false);
  const contextIndicatorColor =
    contextUsage.percentage >= 90
      ? "#b55349"
      : contextUsage.percentage >= 70
        ? "#c08b22"
        : "#3f8f63";

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
      "When Khwarizm runs with full access, it can edit files across your computer and run commands with network access without asking first.\n\nUse this only if you trust the current project. Full access increases the risk of unwanted edits, leaks, or data loss.",
    confirm: "Yes, continue anyway",
  };

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

  return (
    <>
      <div className="bg-surface px-8 py-3">
        <div className="mx-auto flex w-full max-w-[980px] flex-col gap-1.5">
          <div className="w-full rounded-[28px] border bg-card px-4 py-2.5 shadow-[0_14px_28px_rgba(52,42,28,0.05)]" style={{ borderColor: "hsl(var(--border-soft))" }}>
            {composerSettings.attachedFiles.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {composerSettings.attachedFiles.map((filePath) => (
                  <div key={filePath} className="inline-flex max-w-full items-center gap-1.5 rounded-full border bg-surface px-2.5 py-1 text-[12px] text-txt-primary" style={{ borderColor: "hsl(var(--border-soft))" }}>
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
              placeholder="Ask Khwarizm Builder anything..."
              rows={1}
              className="min-h-[22px] max-h-[152px] resize-none overflow-y-auto border-0 bg-transparent px-0 py-0 text-[14px] leading-6 text-txt-primary shadow-none outline-none ring-0 placeholder:text-txt-secondary focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />

            <div className="mt-2.5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 text-txt-secondary">
                <Popover>
                  <PopoverTrigger asChild>
                    <button type="button" className="inline-flex h-7 w-7 items-center justify-center rounded-[10px] transition-colors hover:bg-muted" aria-label="Composer tools">
                      <Plus size={16} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="top" align="start" sideOffset={12} className="w-[220px] rounded-[18px] border border-border-soft bg-card p-1.5 text-txt-primary shadow-[0_16px_30px_rgba(52,42,28,0.12)]">
                    <button type="button" onClick={onPickAttachment} className="flex w-full items-center gap-2.5 rounded-[14px] border border-border-soft bg-surface px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-muted">
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
                      onClick={isStreaming || isPreparingResponse ? onStopStreaming : onSend}
                      disabled={!isStreaming && !isPreparingResponse && !draft.trim()}
                      aria-label={isStreaming || isPreparingResponse ? "Stop response" : "Send message"}
                    >
                      {isPreparingResponse ? (
                        <Loader
                          variant="spin"
                          className="size-4 text-current"
                          aria-label="Preparing response"
                        />
                      ) : isStreaming ? (
                        <Square size={14} fill="currentColor" />
                      ) : (
                        <ArrowUp size={16} />
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" align="center" sideOffset={10} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                    {isPreparingResponse ? `Preparing response ${prepareProgress}%` : isStreaming ? "Stop response" : "Send"}
                  </TooltipContent>
                </Tooltip>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-2 text-[12px] text-txt-secondary">
              <DropdownMenu>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <button className={`inline-flex h-6 items-center gap-1.5 rounded-full px-2 transition-colors hover:bg-muted ${composerSettings.permissionMode === "full-access" ? "text-[#bf6e21]" : "text-txt-secondary"}`}>
                        {composerSettings.permissionMode === "full-access" ? <CircleAlert size={13} /> : <Shield size={13} />}
                        <span>{composerSettings.permissionMode === "full-access" ? "Full access" : "Default permissions"}</span>
                        <ChevronDown size={12} />
                      </button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="top" align="center" sideOffset={10} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                    Change permissions
                  </TooltipContent>
                </Tooltip>
                <DropdownMenuContent side="top" align="start" sideOffset={10} className="w-[200px] rounded-[16px] border border-border-soft bg-card p-1.5 text-txt-primary shadow-[0_16px_30px_rgba(52,42,28,0.12)]">
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
                  className="inline-flex h-6 w-6 items-center justify-center"
                  aria-label="Context window usage"
                >
                  <ProgressCircle
                    aria-label="Context window usage"
                    value={contextUsage.percentage}
                    size={18}
                    strokeWidth={3}
                    trackColor="rgba(147, 128, 99, 0.24)"
                    indicatorColor={contextIndicatorColor}
                  />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" align="end" sideOffset={10} className="rounded-2xl border border-border-soft bg-surface px-3 py-2 text-center text-xs text-txt-primary shadow-md">
                <p>Context window</p>
                <p className="font-medium">{contextUsage.percentage}% full</p>
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
              <AlertDialogCancel onClick={handleCancelPermissionModeChange} className="mt-0 rounded-2xl border border-border-soft bg-surface px-6 py-2.5 text-[15px] font-medium text-txt-primary hover:bg-muted">
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirmPermissionModeChange} className="rounded-2xl border-0 bg-[#6a4036] px-6 py-2.5 text-[15px] font-medium text-[#fff4f0] hover:bg-[#7a4b3f]">
                {permissionDialogCopy.confirm}
              </AlertDialogAction>
            </AlertDialogFooter>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function basename(filePath: string) {
  const normalized = filePath.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? filePath;
}
