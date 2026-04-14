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

  const activeFilterCount = Number(organizeMode !== null) + Number(sortBy !== null) + Number(showMode !== null);
  const allCollapsed = expandedWorkspaceIds.length === 0;
  const primaryThreadsAction = allCollapsed
    ? hasPreviousConversation
      ? { label: "Reopen previous", onClick: onReopenPreviousConversation, icon: <ReopenPreviousIcon /> }
      : { label: "Expand all", onClick: onExpandAllWorkspaces, icon: <ExpandAllIcon /> }
    : { label: "Collapse all", onClick: onCollapseAllWorkspaces, icon: <CollapseAllIcon /> };

  const filteredThreadGroups = useMemo(() => {
    const isRelevant = (updatedAt: string) => !updatedAt.endsWith("mo");

    const groups = threadGroups
      .map((group) => {
        let threads = [...group.threads];

        if (showMode === "relevant") {
          threads = threads.filter((thread) => isRelevant(thread.updatedAt));
        }

        if (sortBy === "created") {
          threads = [...threads].sort((a, b) => a.title.localeCompare(b.title));
        }

        if (sortBy === "updated") {
          threads = [...threads].sort((a, b) => a.updatedAt.localeCompare(b.updatedAt));
        }

        return { ...group, threads };
      })
      .filter((group) => group.threads.length > 0 || showMode !== "relevant");

    if (organizeMode === "time") {
      return [...groups].sort((a, b) => {
        const left = a.threads[0]?.updatedAt ?? "";
        const right = b.threads[0]?.updatedAt ?? "";
        return left.localeCompare(right);
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

  return (
    <motion.aside
      initial={false}
      animate={{
        width: isCollapsed ? 0 : 300,
        opacity: isCollapsed ? 0 : 1,
        x: isCollapsed ? -20 : 0,
      }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r bg-surface-sidebar"
      style={{ borderColor: "hsl(var(--border-primary))" }}
      aria-hidden={isCollapsed}
    >
      <div className="px-5 pb-2 pt-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-3">
            <h1 className="font-brand text-[22px] font-normal tracking-[-0.01em] text-txt-primary">Khwarizm</h1>
            <WorkspaceModeSwitch mode={workspaceMode} onChange={onWorkspaceModeChange} />
          </div>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <button
                onClick={onToggleCollapse}
                className="p-1 text-txt-secondary transition-colors hover:text-txt-primary"
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

      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
        className="flex items-center justify-between px-5 pb-2 pt-5"
      >
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
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1], delay: 0.24 }}
        className="hide-scrollbar min-h-0 flex-1 overflow-y-auto px-3 pb-4"
      >
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
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                whileDrag={{ scale: 1.015, boxShadow: "0 14px 28px rgba(52,42,28,0.12)" }}
                transition={{
                  layout: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
                  duration: 0.22,
                  ease: [0.22, 1, 0.36, 1],
                  delay: 0.28 + orderedThreadGroups.findIndex((item) => item.id === group.id) * 0.035,
                }}
                className="rounded-[16px] px-1.5 py-1"
                onDragStart={() => setDraggedWorkspaceId(group.id)}
                onDragEnd={() => {
                  setDraggedWorkspaceId(null);
                  setHoveredWorkspaceHeaderId(null);
                  setHoveredWorkspaceThreadsId(null);
                }}
              >
                <motion.div
                  layout
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
                          <DropdownMenuItem className="rounded-xl text-sm text-[#9f5c53] focus:bg-[#faece8] focus:text-[#9f5c53]" onClick={() => onRemoveWorkspace(group.id)}>Remove project</DropdownMenuItem>
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
                </motion.div>

                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      key={`${group.id}-threads`}
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
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
                                        <DropdownMenuItem className="rounded-xl text-sm text-[#9f5c53] focus:bg-[#faece8] focus:text-[#9f5c53]" onClick={() => onRemoveThread(thread.id)}>Remove</DropdownMenuItem>
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
                    </motion.div>
                  )}
                </AnimatePresence>
              </Reorder.Item>
            );
          })}
        </Reorder.Group>
      </motion.div>

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
    </motion.aside>
  );
}
