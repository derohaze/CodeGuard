import { Shield } from "lucide-react";
import type { AppScreen } from "@/shared/types/app";

export function SidebarActions({
  currentScreen,
  onNavigate,
}: {
  currentScreen: AppScreen;
  onNavigate: (screen: AppScreen) => void;
}) {
  const isScanActive = currentScreen === "home" || currentScreen === "scan-empty";

  return (
    <div className="space-y-0.5 px-3 py-2">
      <button
        onClick={() => onNavigate("home")}
        className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors ${
          isScanActive ? "bg-muted font-medium text-txt-primary" : "text-txt-primary hover:bg-muted"
        }`}
      >
        <Shield size={16} className="text-txt-secondary" />
        <span>Security Analyst</span>
      </button>
    </div>
  );
}
