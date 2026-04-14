import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, Reorder, motion } from "framer-motion";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Ellipsis,
  FolderPlus,
  PanelLeftClose,
  PenSquare,
  SlidersHorizontal,
} from "lucide-react";
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
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Loader } from "@/shared/ui/Loader";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ShowMore } from "@/components/ui/show-more";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SidebarFooter } from "@/features/sidebar-navigation/ui/SidebarFooter";
import { WorkspaceModeSwitch } from "@/shared/ui/WorkspaceModeSwitch";
import type { WorkspaceMode } from "@/shared/types/app";
import { BrandModeHeading } from "@/shared/ui/BrandModeHeading";
import type { BuilderThreadGroup } from "../../model/mockBuilderAgent";
import { BuilderCommandMenu } from "../BuilderCommandMenu";
import { AnimatedThreadTitle } from "./AnimatedThreadTitle";
import {
  CollapseAllIcon,
  ExpandAllIcon,
  ReopenPreviousIcon,
  SidebarFolderIcon,
} from "./BuilderSidebarIcons";
import { BuilderSidebarSearchButton } from "./BuilderSidebarSearchButton";
import { buildFilterSections } from "./sidebarFilters";

interface BuilderSidebarProps {
  activeConversationId: string | null;
  busyConversationIds: string[];
  currentWorkspaceId: string | null;
  expandedWorkspaceIds: string[];
  hasPreviousConversation: boolean;
  isCollapsed: boolean;
  onAddWorkspace: () => void;
  onArchiveThread: (threadId: string) => void;
  onArchiveWorkspaceThreads: (workspaceId: string) => void;
  onCollapseAllWorkspaces: () => void;
  onCreatePermanentWorktree: (workspaceId: string) => void;
  onCreateWorkspaceThread: (workspaceId: string) => void;
  onExpandAllWorkspaces: () => void;
  onOpenConversation: (conversationId: string) => void;
  onOpenSettings: () => void;
  onOpenWorkspaceInExplorer: (workspaceId: string) => void;
  onRemoveWorkspace: (workspaceId: string) => void;
  onRemoveThread: (threadId: string) => void;
  onReorderWorkspaces: (orderedWorkspaceIds: string[]) => void;
  onRenameWorkspace: (workspaceId: string) => void;
  onRenameThread: (threadId: string) => void;
  onReopenPreviousConversation: () => void;
  onToggleCollapse: () => void;
  onToggleWorkspace: (workspaceId: string) => void;
  onToggleWorkspaceShowAll: (workspaceId: string) => void;
  onWorkspaceModeChange: (mode: WorkspaceMode) => void;
  showAllWorkspaceIds: string[];
  threadGroups: BuilderThreadGroup[];
  workspaceMode: WorkspaceMode;
}

type PendingDeleteTarget =
  | { type: "thread"; id: string; label: string }
  | { type: "workspace"; id: string; label: string };

export function BuilderSidebar({
  activeConversationId,
  busyConversationIds,
  currentWorkspaceId,
  expandedWorkspaceIds,
  hasPreviousConversation,
  isCollapsed,
  onAddWorkspace,
  onArchiveThread,
  onArchiveWorkspaceThreads,
  onCollapseAllWorkspaces,
  onCreatePermanentWorktree,
  onCreateWorkspaceThread,
  onExpandAllWorkspaces,
  onOpenConversation,
  onOpenSettings,
  onOpenWorkspaceInExplorer,
  onRemoveWorkspace,
  onRemoveThread,
  onReorderWorkspaces,
  onRenameWorkspace,
  onRenameThread,
  onReopenPreviousConversation,
  onToggleCollapse,
  onToggleWorkspace,
  onToggleWorkspaceShowAll,
  onWorkspaceModeChange,
  showAllWorkspaceIds,
  threadGroups,
  workspaceMode,
}: BuilderSidebarProps) {
  const [hoveredWorkspaceHeaderId, setHoveredWorkspaceHeaderId] = useState<string | null>(null);
  const [hoveredWorkspaceThreadsId, setHoveredWorkspaceThreadsId] = useState<string | null>(null);
  const [draggedWorkspaceId, setDraggedWorkspaceId] = useState<string | null>(null);
  const [orderedWorkspaceIds, setOrderedWorkspaceIds] = useState<string[]>([]);
  const [isCommandMenuOpen, setIsCommandMenuOpen] = useState(false);
  const [organizeMode, setOrganizeMode] = useState<"workspace" | "time" | null>(null);
  const [sortBy, setSortBy] = useState<"created" | "updated" | null>(null);
  const [showMode, setShowMode] = useState<"all" | "relevant" | null>(null);
  const [pendingDeleteTarget, setPendingDeleteTarget] = useState<PendingDeleteTarget | null>(null);

  const activeFilterCount = Number(organizeMode !== null) + Number(sortBy !== null) + Number(showMode !== null);
  const allCollapsed = expandedWorkspaceIds.length === 0;
  const primaryThreadsAction = allCollapsed
    ? hasPreviousConversation
      ? { label: "Reopen previous", onClick: onReopenPreviousConversation, icon: <ReopenPreviousIcon /> }
      : { label: "Expand all", onClick: onExpandAllWorkspaces, icon: <ExpandAllIcon /> }
    : { label: "Collapse all", onClick: onCollapseAllWorkspaces, icon: <CollapseAllIcon /> };

  const filteredThreadGroups = useMemo(() => {
    const isRelevant = (updatedAt: string, rawUpdatedAt?: string) => {
      const parsedTimestamp = resolveThreadSortTimestamp(updatedAt, rawUpdatedAt);
      if (parsedTimestamp === Number.NEGATIVE_INFINITY) {
        return true;
      }

      const now = Date.now();
      const thirtyDaysInMilliseconds = 30 * 24 * 60 * 60 * 1000;
      return now - parsedTimestamp < thirtyDaysInMilliseconds;
    };

    const groups = threadGroups
      .map((group) => {
        let threads = [...group.threads];

        if (showMode === "relevant") {
          threads = threads.filter((thread) => isRelevant(thread.updatedAt, thread.rawUpdatedAt));
        }

        if (sortBy === "created") {
          threads = [...threads].sort((a, b) => a.title.localeCompare(b.title));
        }

        if (sortBy === "updated") {
          threads = [...threads].sort(
            (a, b) => resolveThreadSortTimestamp(b.updatedAt, b.rawUpdatedAt) - resolveThreadSortTimestamp(a.updatedAt, a.rawUpdatedAt),
          );
        }

        return { ...group, threads };
      })
      .filter((group) => group.threads.length > 0 || showMode !== "relevant");

    if (organizeMode === "time") {
      return [...groups].sort((a, b) => {
        const left = a.threads[0];
        const right = b.threads[0];
        return resolveThreadSortTimestamp(right?.updatedAt ?? "", right?.rawUpdatedAt)
          - resolveThreadSortTimestamp(left?.updatedAt ?? "", left?.rawUpdatedAt);
      });
    }

    return groups;
  }, [organizeMode, showMode, sortBy, threadGroups]);

  useEffect(() => {
    setOrderedWorkspaceIds(filteredThreadGroups.map((group) => group.id));
  }, [filteredThreadGroups]);

  const orderedThreadGroups = orderedWorkspaceIds
    .map((workspaceId) => filteredThreadGroups.find((group) => group.id === workspaceId) ?? null)
    .filter((group): group is BuilderThreadGroup => group !== null);

  const handleConfirmDelete = () => {
    if (!pendingDeleteTarget) {
      return;
    }

    if (pendingDeleteTarget.type === "thread") {
      onRemoveThread(pendingDeleteTarget.id);
    } else {
      onRemoveWorkspace(pendingDeleteTarget.id);
    }

    setPendingDeleteTarget(null);
  };

  return (
    <div
      className="relative h-full shrink-0 overflow-hidden"
      style={{ width: isCollapsed ? 0 : 300 }}
      aria-hidden={isCollapsed}
    >
      <motion.aside
        className="absolute inset-y-0 left-0 flex w-[300px] min-h-0 flex-col overflow-hidden border-r bg-surface-sidebar"
        style={{ borderColor: "hsl(var(--border-primary))" }}
        initial={false}
        animate={{
          x: isCollapsed ? -300 : 0,
          opacity: isCollapsed ? 0 : 1,
        }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="px-5 pb-2 pt-5">
          <div className="relative">
            <div className="space-y-3 pr-8">
              <BrandModeHeading mode={workspaceMode} />
              <WorkspaceModeSwitch mode={workspaceMode} onChange={onWorkspaceModeChange} />
            </div>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <button
                  onClick={onToggleCollapse}
                  className="absolute right-0 top-0 p-1 text-txt-secondary transition-colors hover:text-txt-primary"
                  aria-label="Hide sidebar"
                >
                  <PanelLeftClose size={17} />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" align="end" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                Hide sidebar
              </TooltipContent>
            </Tooltip>
          </div>
        </div>

        <BuilderSidebarSearchButton onOpen={() => setIsCommandMenuOpen(true)} />

        <div className="flex items-center justify-between px-5 pb-2 pt-5">
          <span className="text-xs font-medium text-txt-tertiary">Threads</span>
          <div className="flex items-center gap-1">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button type="button" onClick={primaryThreadsAction.onClick} className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[#8a8276] transition-colors hover:bg-muted hover:text-txt-primary" aria-label={primaryThreadsAction.label}>
                {primaryThreadsAction.icon}
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
              {primaryThreadsAction.label}
            </TooltipContent>
          </Tooltip>

          <Popover>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <PopoverTrigger asChild>
                  <button
                    className={`relative inline-flex h-8 w-8 items-center justify-center rounded-xl transition-colors ${
                      activeFilterCount > 0 ? "bg-secondary text-txt-primary" : "text-[#8a8276] hover:bg-muted hover:text-txt-primary"
                    }`}
                    aria-label="Filter, sort, and organize chats"
                  >
                    <SlidersHorizontal size={14} />
                    {activeFilterCount > 0 && (
                      <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-accent-foreground">
                        {activeFilterCount}
                      </span>
                    )}
                  </button>
                </PopoverTrigger>
              </TooltipTrigger>
              <TooltipContent side="top" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                Filter, sort, and organize chats
              </TooltipContent>
            </Tooltip>
            <PopoverContent align="end" sideOffset={10} className="w-[230px] rounded-[16px] border border-border-soft bg-surface p-1.5 shadow-[0_16px_36px_rgba(52,42,28,0.1)]">
              <div className="px-1 py-1">
                {buildFilterSections({
                  organizeMode,
                  setOrganizeMode,
                  showMode,
                  setShowMode,
                  sortBy,
                  setSortBy,
                }).map((section, sectionIndex) => (
                  <div key={section.title}>
                    {sectionIndex > 0 && <div className="mx-1 my-1 border-t border-border-soft" />}
                    <div className="px-2 pb-1 pt-1.5 text-[11px] font-medium text-txt-tertiary">{section.title}</div>
                    <div className="space-y-0.5 pb-1">
                      {section.items.map((item) => {
                        const Icon = item.icon;
                        return (
                          <button
                            key={item.label}
                            onClick={item.onSelect}
                            className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors ${
                              item.selected ? "bg-secondary text-txt-primary" : "text-txt-primary hover:bg-secondary/65"
                            }`}
                          >
                            <Icon size={14} className="shrink-0 text-txt-secondary" />
                            <span className="min-w-0 flex-1 truncate font-medium">{item.label}</span>
                            {item.selected && <Check size={14} className="shrink-0 text-txt-primary" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>

          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button type="button" onClick={onAddWorkspace} className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[#8a8276] transition-colors hover:bg-muted hover:text-txt-primary" aria-label="Add new project">
                <FolderPlus size={15} />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
              Add new project
            </TooltipContent>
          </Tooltip>
          </div>
        </div>

        <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <Reorder.Group axis="y" values={orderedWorkspaceIds} onReorder={(nextOrder) => {
          setOrderedWorkspaceIds(nextOrder);
          onReorderWorkspaces(nextOrder);
        }} className="space-y-1.5">
          {orderedThreadGroups.map((group) => {
            const isExpanded = expandedWorkspaceIds.includes(group.id);
            const showAll = showAllWorkspaceIds.includes(group.id);
            const visibleThreads = showAll ? group.threads : group.threads.slice(0, 3);
            const hasOverflow = group.threads.length > 3;
            const showWorkspaceHeaderControls = hoveredWorkspaceHeaderId === group.id;
            const showExpandIcon = hoveredWorkspaceHeaderId === group.id;

            return (
              <Reorder.Item
                key={group.id}
                value={group.id}
                whileDrag={{ scale: 1.015, boxShadow: "0 14px 28px rgba(52,42,28,0.12)" }}
                transition={{ layout: { duration: 0 } }}
                className="rounded-[16px] px-1.5 py-1"
                onDragStart={() => setDraggedWorkspaceId(group.id)}
                onDragEnd={() => {
                  setDraggedWorkspaceId(null);
                  setHoveredWorkspaceHeaderId(null);
                  setHoveredWorkspaceThreadsId(null);
                }}
              >
                <div
                  onMouseEnter={() => setHoveredWorkspaceHeaderId(group.id)}
                  onMouseLeave={() => setHoveredWorkspaceHeaderId((current) => (current === group.id ? null : current))}
                  className={`flex items-center gap-2 rounded-[12px] px-1.5 py-1 transition-colors ${
                    hoveredWorkspaceHeaderId === group.id || draggedWorkspaceId === group.id ? "bg-card" : ""
                  } ${draggedWorkspaceId === group.id ? "cursor-grabbing opacity-80" : "cursor-pointer active:cursor-grabbing"}`}
                >
                  <button type="button" onClick={() => onToggleWorkspace(group.id)} className={`inline-flex h-[14px] w-[14px] items-center justify-center text-[#8a8276] ${draggedWorkspaceId === group.id ? "cursor-grabbing" : "cursor-pointer active:cursor-grabbing"}`} aria-label={isExpanded ? `Collapse ${group.label}` : `Expand ${group.label}`}>
                    {showExpandIcon ? (isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />) : <SidebarFolderIcon className="h-[14px] w-[14px]" />}
                  </button>

                  <Tooltip delayDuration={1000}>
                    <div className="min-w-0 flex-1">
                      <TooltipTrigger asChild>
                        <button type="button" onClick={() => onToggleWorkspace(group.id)} className={`inline-block max-w-full truncate text-left text-[14px] text-[#7d7467] ${draggedWorkspaceId === group.id ? "cursor-grabbing" : "cursor-pointer active:cursor-grabbing"}`}>
                          {group.label}
                        </button>
                      </TooltipTrigger>
                    </div>
                    <TooltipContent side="top" align="start" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                      {group.path}
                    </TooltipContent>
                  </Tooltip>

                  <div className="flex w-[48px] items-center justify-end gap-0.5">
                    <div className={`flex items-center gap-0.5 transition-opacity ${showWorkspaceHeaderControls ? "opacity-100" : "pointer-events-none opacity-0"}`}>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button type="button" className="inline-flex h-6 w-6 items-center justify-center rounded-full text-[#8a8276] transition-colors hover:bg-card" aria-label={`Workspace actions for ${group.label}`}>
                            <Ellipsis size={14} />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" sideOffset={8} className="w-[220px] rounded-[18px] border border-border-soft bg-surface p-2 text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                          <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onOpenWorkspaceInExplorer(group.id)}>Open in Explorer</DropdownMenuItem>
                          <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onCreatePermanentWorktree(group.id)}>Create permanent worktree</DropdownMenuItem>
                          <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onRenameWorkspace(group.id)}>Edit name</DropdownMenuItem>
                          <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onArchiveWorkspaceThreads(group.id)}>Archive chats</DropdownMenuItem>
                          <DropdownMenuSeparator className="bg-border-soft" />
                          <DropdownMenuItem
                            className="rounded-xl text-sm text-[#9f5c53] focus:bg-[#faece8] focus:text-[#9f5c53]"
                            onClick={() => setPendingDeleteTarget({ type: "workspace", id: group.id, label: group.label })}
                          >
                            Delete project
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <button type="button" onClick={() => onCreateWorkspaceThread(group.id)} className="inline-flex h-6 w-6 items-center justify-center rounded-full text-[#8a8276] transition-colors hover:bg-card" aria-label={`Start new chat in ${group.label}`}>
                            <PenSquare size={13} />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="top" sideOffset={8} className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md">
                          Start new chat in workspace
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                </div>

                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <div
                      key={`${group.id}-threads`}
                      className="overflow-hidden"
                    >
                      <div className="pb-1 pl-6 pr-1.5 pt-0.5" onMouseEnter={() => setHoveredWorkspaceThreadsId(group.id)} onMouseLeave={() => setHoveredWorkspaceThreadsId((current) => (current === group.id ? null : current))}>
                        <div className="space-y-1.5">
                          {visibleThreads.map((thread) => {
                            const active = activeConversationId === thread.id;
                            const busy = busyConversationIds.includes(thread.id);
                            const showThreadControls = active || hoveredWorkspaceThreadsId === group.id;
                            return (
                              <div key={thread.id} className={`flex items-center gap-2 rounded-xl px-2.5 py-2 transition-colors ${active ? "bg-card" : "hover:bg-card/70"}`}>
                                <button onClick={() => onOpenConversation(thread.id)} className="flex min-w-0 flex-1 items-center justify-between gap-3 text-left">
                                    <AnimatedThreadTitle title={thread.title} />
                                    {busy ? (
                                      <span className="inline-flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-[#a76924]">
                                        <Loader variant="spin" className="size-3 text-current" aria-hidden="true" />
                                        <span>Working</span>
                                      </span>
                                    ) : (
                                    <span className="shrink-0 text-xs text-txt-tertiary">{thread.updatedAt}</span>
                                  )}
                                </button>
                                <div className="flex w-7 justify-end">
                                  <div className={`transition-opacity ${showThreadControls ? "opacity-100" : "pointer-events-none opacity-0"}`}>
                                    <DropdownMenu>
                                      <DropdownMenuTrigger asChild>
                                        <button type="button" className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[#8a8276] transition-colors hover:bg-[#f3ede3]" aria-label={`Chat actions for ${thread.title}`}>
                                          <Ellipsis size={14} />
                                        </button>
                                      </DropdownMenuTrigger>
                                      <DropdownMenuContent align="end" sideOffset={8} className="w-[200px] rounded-[18px] border border-border-soft bg-surface p-2 text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                                        <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onRenameThread(thread.id)}>Edit name</DropdownMenuItem>
                                        <DropdownMenuItem className="rounded-xl text-sm focus:bg-secondary focus:text-txt-primary" onClick={() => onArchiveThread(thread.id)}>Archive chat</DropdownMenuItem>
                                        <DropdownMenuSeparator className="bg-border-soft" />
                                        <DropdownMenuItem
                                          className="rounded-xl text-sm text-[#9f5c53] focus:bg-[#faece8] focus:text-[#9f5c53]"
                                          onClick={() => setPendingDeleteTarget({ type: "thread", id: thread.id, label: thread.title })}
                                        >
                                          Delete
                                        </DropdownMenuItem>
                                      </DropdownMenuContent>
                                    </DropdownMenu>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {hasOverflow && (
                          <ShowMore
                            className="mt-2 [&>button]:gap-1.5 [&>button]:px-2.5 [&>button]:py-1 [&>button]:text-xs [&>button_svg]:size-3.5"
                            onClick={() => onToggleWorkspaceShowAll(group.id)}
                          >
                            {() => (
                              <>
                                <span>{showAll ? "Show fewer chats" : `Show ${group.threads.length - 3} more chats`}</span>
                                <ChevronDown className={`size-4 transition-transform duration-200 ${showAll ? "rotate-180" : ""}`} />
                              </>
                            )}
                          </ShowMore>
                        )}
                      </div>
                    </div>
                  )}
                </AnimatePresence>
              </Reorder.Item>
            );
          })}
        </Reorder.Group>
        </div>

        <SidebarFooter onOpenSettings={onOpenSettings} />
        <BuilderCommandMenu
          currentWorkspaceId={currentWorkspaceId}
          isOpen={isCommandMenuOpen}
          onAddWorkspace={onAddWorkspace}
          onClose={() => setIsCommandMenuOpen(false)}
          onCreateWorkspaceThread={onCreateWorkspaceThread}
          onOpenConversation={onOpenConversation}
          onOpenSettings={onOpenSettings}
          onToggleCollapse={onToggleCollapse}
          threadGroups={threadGroups}
        />
        <AlertDialog open={pendingDeleteTarget !== null} onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteTarget(null);
          }
        }}>
          <AlertDialogContent className="max-w-[420px] rounded-[28px] border border-border-soft bg-surface p-0 shadow-[0_28px_80px_rgba(52,42,28,0.14)]">
            <div className="space-y-5 p-6">
              <AlertDialogHeader className="space-y-2 text-left">
                <AlertDialogTitle className="font-brand text-[26px] font-medium tracking-[-0.02em] text-txt-primary">
                  {pendingDeleteTarget?.type === "workspace" ? "Delete this project?" : "Delete this chat?"}
                </AlertDialogTitle>
                <AlertDialogDescription className="text-sm leading-6 text-txt-secondary">
                  {pendingDeleteTarget?.type === "workspace"
                    ? `This will permanently remove "${pendingDeleteTarget.label}" and its chats from the builder sidebar.`
                    : `This will permanently remove "${pendingDeleteTarget?.label ?? "this chat"}" from the builder sidebar.`}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter className="gap-2 sm:justify-start sm:space-x-0">
                <AlertDialogCancel className="mt-0 rounded-full border border-[#ddd1bf] bg-[#f6efe6] px-5 !text-[#1e1b16] hover:bg-[#eee3d5]">
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={(event) => {
                    event.preventDefault();
                    handleConfirmDelete();
                  }}
                  className="rounded-full bg-[#1e1b16] px-5 text-white hover:bg-[#29241d]"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </div>
          </AlertDialogContent>
        </AlertDialog>
      </motion.aside>
    </div>
  );
}

function resolveThreadSortTimestamp(updatedAt: string, rawUpdatedAt?: string): number {
  if (rawUpdatedAt) {
    const parsed = Date.parse(rawUpdatedAt);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  const relativeMatch = updatedAt.trim().match(/^(\d+)(m|h|d|mo)$/u);
  if (!relativeMatch) {
    return Number.NEGATIVE_INFINITY;
  }

  const [, amountText, unit] = relativeMatch;
  const amount = Number(amountText);
  const unitInMilliseconds = unit === "m"
    ? 60 * 1000
    : unit === "h"
      ? 60 * 60 * 1000
      : unit === "d"
        ? 24 * 60 * 60 * 1000
        : 30 * 24 * 60 * 60 * 1000;
  return Date.now() - (amount * unitInMilliseconds);
}
