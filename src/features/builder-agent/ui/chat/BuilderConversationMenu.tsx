import {
  Archive,
  Copy,
  Ellipsis,
  FolderTree,
  GitFork,
  Link2,
  PencilLine,
  PinOff,
  TimerReset,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface BuilderConversationMenuProps {
  activeConversationId: string | null;
  currentWorkspaceId: string | null;
  currentWorkspacePath: string | null;
  onArchiveConversation: (conversationId: string) => void;
  onCreatePermanentWorktree: (workspaceId: string) => void;
  onRenameConversation: (conversationId: string) => void;
}

export function BuilderConversationMenu({
  activeConversationId,
  currentWorkspaceId,
  currentWorkspacePath,
  onArchiveConversation,
  onCreatePermanentWorktree,
  onRenameConversation,
}: BuilderConversationMenuProps) {
  const handleCopy = async (value: string | null) => {
    if (!value || typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Ignore clipboard failures in the mock frontend flow.
    }
  };

  const deeplink = activeConversationId ? `khwarizm://builder/${activeConversationId}` : null;

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
