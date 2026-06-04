import * as DialogPrimitive from "@radix-ui/react-dialog";
import { motion, useDragControls } from "framer-motion";
import {
  Clock3,
  FolderOpen,
  FolderPlus,
  MessageSquarePlus,
  PanelLeftClose,
  PlugZap,
  Search,
  Settings2,
} from "lucide-react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { Dialog, DialogOverlay, DialogPortal } from "@/components/ui/dialog";
import type { BuilderThreadGroup } from "../model/mockBuilderAgent";

interface BuilderCommandMenuProps {
  currentWorkspaceId: string | null;
  isOpen: boolean;
  onAddWorkspace: () => void;
  onClose: () => void;
  onCreateWorkspaceThread: (workspaceId: string) => void;
  onOpenConversation: (conversationId: string) => void;
  onOpenSettings: () => void;
  onToggleCollapse: () => void;
  threadGroups: BuilderThreadGroup[];
}

export function BuilderCommandMenu({
  currentWorkspaceId,
  isOpen,
  onAddWorkspace,
  onClose,
  onCreateWorkspaceThread,
  onOpenConversation,
  onOpenSettings,
  onToggleCollapse,
  threadGroups,
}: BuilderCommandMenuProps) {
  const currentWorkspace = threadGroups.find((group) => group.id === currentWorkspaceId) ?? threadGroups[0] ?? null;
  const dragControls = useDragControls();

  const run = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay className="bg-transparent" />
        <DialogPrimitive.Content asChild>
          <motion.div
            drag
            dragControls={dragControls}
            dragListener={false}
            dragMomentum={false}
            className="fixed left-1/2 top-[19%] z-50 w-[min(540px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-[22px] border border-border-soft bg-[#f7f3eb] p-0 shadow-[0_18px_44px_rgba(0,0,0,0.14)] outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-top-[16%] data-[state=open]:slide-in-from-top-[18%]"
          >
        <Command className="bg-[#f7f3eb] text-txt-primary">
          <div
            onPointerDown={(event) => dragControls.start(event)}
            className="flex h-4 cursor-grab items-center justify-center border-b border-border-soft active:cursor-grabbing"
          >
            <span className="h-1 w-14 rounded-full bg-[#ddd2c2]" />
          </div>
          <CommandInput
            placeholder="Type command or search chats"
            className="h-11 text-[13px] placeholder:text-[#9a9184]"
          />
          <CommandList className="hide-scrollbar max-h-[340px] px-2 pb-2">
            <CommandEmpty className="py-7 text-sm text-txt-secondary">No results found.</CommandEmpty>

            <CommandGroup heading="Suggested" className="pt-2">
              <CommandItem
                value="new-chat"
                onSelect={() => currentWorkspace && run(() => onCreateWorkspaceThread(currentWorkspace.id))}
                className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]"
              >
                <MessageSquarePlus className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>New chat</span>
                <CommandShortcut>Ctrl+N</CommandShortcut>
              </CommandItem>
              <CommandItem
                value="open-folder"
                onSelect={() => run(onAddWorkspace)}
                className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]"
              >
                <FolderPlus className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Open folder</span>
                <CommandShortcut>Ctrl+O</CommandShortcut>
              </CommandItem>
              <CommandItem
                value="settings"
                onSelect={() => run(onOpenSettings)}
                className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]"
              >
                <Settings2 className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Settings</span>
              </CommandItem>
            </CommandGroup>

            <CommandGroup heading="Navigation" className="pt-1">
              <CommandItem className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]">
                <Search className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Search</span>
                <CommandShortcut>Ctrl+K</CommandShortcut>
              </CommandItem>
              <CommandItem className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]">
                <PlugZap className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Plugins</span>
              </CommandItem>
              <CommandItem className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]">
                <Clock3 className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Automations</span>
              </CommandItem>
              <CommandItem
                value="toggle-sidebar"
                onSelect={() => run(onToggleCollapse)}
                className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]"
              >
                <PanelLeftClose className="mr-3 h-4 w-4 text-[#8a8276]" />
                <span>Toggle sidebar</span>
                <CommandShortcut>Ctrl+B</CommandShortcut>
              </CommandItem>
            </CommandGroup>

            <CommandGroup heading="Chats" className="pt-1">
              {threadGroups.flatMap((group) =>
                group.threads.map((thread) => (
                  <CommandItem
                    key={thread.id}
                    value={`${thread.title} ${group.label}`}
                    onSelect={() => run(() => onOpenConversation(thread.id))}
                    className="rounded-[16px] px-3 py-2.5 text-[13px] data-[selected=true]:bg-[#ebe3d5]"
                  >
                    <FolderOpen className="mr-3 h-4 w-4 text-[#8a8276]" />
                    <span className="min-w-0 flex-1 truncate">{thread.title}</span>
                    <span className="max-w-[140px] truncate text-[11px] text-[#9a9184]">{group.label}</span>
                  </CommandItem>
                )),
              )}
            </CommandGroup>
          </CommandList>
        </Command>
          </motion.div>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
