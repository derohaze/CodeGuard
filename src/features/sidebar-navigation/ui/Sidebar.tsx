import type { Session } from "@/entities/session/model/types";
import type { AppScreen, WorkspaceMode } from "@/shared/types/app";
import { SidebarActions } from "./SidebarActions";
import { SidebarFooter } from "./SidebarFooter";
import { SidebarHeader } from "./SidebarHeader";
import { SidebarSessionsList } from "./SidebarSessionsList";

interface SidebarProps {
  sessions: Session[];
  sessionOrder: string[];
  currentScreen: AppScreen;
  onNavigate: (screen: AppScreen) => void;
  activeSessionId?: string | null;
  onOpenSession: (session: Session) => void;
  onDeleteSession: (session: Session) => void;
  onDeleteAllSessions: () => void;
  onReorderSessions: (orderedSessionIds: string[]) => void;
  isCollapsed: boolean;
  mode: WorkspaceMode;
  onModeChange: (mode: WorkspaceMode) => void;
  onToggleCollapse: () => void;
  onOpenSettings: () => void;
}

export function Sidebar({
  sessions,
  sessionOrder,
  currentScreen,
  onNavigate,
  activeSessionId,
  onOpenSession,
  onDeleteSession,
  onDeleteAllSessions,
  onReorderSessions,
  isCollapsed,
  mode,
  onModeChange,
  onToggleCollapse,
  onOpenSettings,
}: SidebarProps) {
  return (
    <aside
      className="flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r bg-surface-sidebar"
      style={{
        borderColor: "hsl(var(--border-primary))",
        width: isCollapsed ? 0 : 300,
        opacity: isCollapsed ? 0 : 1,
      }}
      aria-hidden={isCollapsed}
    >
      <SidebarHeader mode={mode} onModeChange={onModeChange} onToggleCollapse={onToggleCollapse} />
      <SidebarActions currentScreen={currentScreen} onNavigate={onNavigate} />
      <SidebarSessionsList
        sessions={sessions}
        sessionOrder={sessionOrder}
        activeSessionId={activeSessionId}
        onOpenSession={onOpenSession}
        onDeleteSession={onDeleteSession}
        onDeleteAllSessions={onDeleteAllSessions}
        onReorderSessions={onReorderSessions}
      />
      <SidebarFooter onOpenSettings={onOpenSettings} />
    </aside>
  );
}
