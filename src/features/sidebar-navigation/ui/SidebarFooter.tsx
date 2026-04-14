import { useState } from "react";
import { Grape, LogOut, Settings } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function SidebarFooter({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [isSettingsMenuOpen, setIsSettingsMenuOpen] = useState(false);

  return (
    <div className="flex items-center gap-3 px-5 py-4">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-full"
        style={{ backgroundColor: "hsl(102 22% 86%)" }}
      >
        <Grape size={16} className="text-[#728561]" strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-txt-primary">Sarah Chen</p>
        <p className="truncate text-xs text-txt-tertiary">sarah.chen@khwarizm.app</p>
      </div>
      <Popover open={isSettingsMenuOpen} onOpenChange={setIsSettingsMenuOpen}>
        <PopoverTrigger asChild>
          <button
            className="ml-auto p-1 text-txt-secondary transition-colors hover:text-txt-primary"
            aria-label="Open settings menu"
          >
            <Settings size={15} strokeWidth={1.9} />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          side="top"
          sideOffset={10}
          className="w-[248px] rounded-[18px] border border-border-soft bg-surface p-2 text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-3 rounded-xl px-2 py-2">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full"
                style={{ backgroundColor: "hsl(102 22% 86%)" }}
              >
                <Grape size={15} className="text-[#728561]" strokeWidth={1.8} />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-txt-primary">Sarah Chen</p>
                <p className="truncate text-xs text-txt-tertiary">sarah.chen@khwarizm.app</p>
              </div>
            </div>

            <div className="mx-2 my-1 border-t border-border-soft" />

            {[
              {
                label: "Settings",
                icon: Settings,
                onSelect: () => {
                  setIsSettingsMenuOpen(false);
                  onOpenSettings();
                },
              },
              { label: "Log out", icon: LogOut },
            ].map((item) => {
              const Icon = item.icon;

              return (
                <button
                  key={item.label}
                  onClick={item.onSelect}
                  className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm text-txt-primary transition-colors hover:bg-secondary"
                >
                  <Icon size={15} className="text-txt-secondary" strokeWidth={1.9} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
