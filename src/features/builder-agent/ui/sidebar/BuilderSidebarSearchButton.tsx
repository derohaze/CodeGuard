import { Search } from "lucide-react";

export function BuilderSidebarSearchButton({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="px-3 py-2">
      <button
        onClick={onOpen}
        className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-txt-primary transition-colors hover:bg-muted"
      >
        <Search size={16} className="text-txt-secondary" />
        <span>Search</span>
      </button>
    </div>
  );
}
