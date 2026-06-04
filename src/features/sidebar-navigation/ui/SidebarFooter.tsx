import { Settings02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";

export function SidebarFooter({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <div className="border-t px-3 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <button
        type="button"
        onClick={onOpenSettings}
        className="flex h-10 w-full items-center gap-2.5 rounded-lg px-3 text-left text-sm font-medium text-txt-secondary transition-colors hover:bg-muted hover:text-txt-primary"
        aria-label="Open settings"
      >
        <HugeiconsIcon
          icon={Settings02Icon}
          size={18}
          strokeWidth={1.8}
          color="currentColor"
          aria-hidden="true"
          focusable="false"
        />
        <span className="truncate">Settings</span>
      </button>
    </div>
  );
}
