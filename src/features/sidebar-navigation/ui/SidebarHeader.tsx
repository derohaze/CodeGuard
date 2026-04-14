import { PanelLeftClose } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { WorkspaceModeSwitch } from "@/shared/ui/WorkspaceModeSwitch";
import type { WorkspaceMode } from "@/shared/types/app";

export function SidebarHeader({
  mode,
  onModeChange,
  onToggleCollapse,
}: {
  mode: WorkspaceMode;
  onModeChange: (mode: WorkspaceMode) => void;
  onToggleCollapse: () => void;
}) {
  return (
    <div className="px-5 pb-2 pt-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <h1 className="font-brand text-[22px] font-normal tracking-[-0.01em] text-txt-primary">
              Khwarizm
            </h1>
          </div>
          <WorkspaceModeSwitch mode={mode} onChange={onModeChange} />
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
        <TooltipContent
          side="bottom"
          align="end"
          sideOffset={8}
          className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md"
        >
          Hide sidebar
        </TooltipContent>
      </Tooltip>
      </div>
    </div>
  );
}
