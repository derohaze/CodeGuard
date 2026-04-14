import { motion } from "framer-motion";
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
    <div
      className="relative h-full shrink-0 overflow-hidden"
      style={{ width: isCollapsed ? 0 : 300 }}
      aria-hidden={isCollapsed}
    >
      <motion.aside
        className="absolute inset-y-0 left-0 flex w-[300px] min-h-0 flex-col overflow-hidden border-r bg-surface-sidebar"
        style={{ borderColor: "hsl(var(--border-primary))" }}
        initial={false}
        animate={{
          x: isCollapsed ? -300 : 0,
          opacity: isCollapsed ? 0 : 1,
        }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
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
      </motion.aside>
    </div>
  );
}
