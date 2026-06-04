import { Settings02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";

export function SidebarFooter({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <div className="px-5 py-4">
      <button
        type="button"
        onClick={onOpenSettings}
        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-txt-primary transition-colors hover:bg-secondary"
        aria-label="Open settings"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-txt-secondary">
          <HugeiconsIcon
            icon={Settings02Icon}
            size={18}
            strokeWidth={1.8}
            color="currentColor"
            aria-hidden="true"
            focusable="false"
          />
        </span>
        <span className="truncate">Settings</span>
      </button>
    </div>
  );
}
