import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const hasElectronTitlebar = typeof window !== "undefined" && typeof window.electronAPI?.versions?.electron === "string";

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface">
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative flex h-full min-h-0 w-full min-w-0 max-w-none overflow-hidden bg-surface"
      >
        {hasElectronTitlebar ? <div className="app-drag absolute left-0 right-[138px] top-0 z-0 h-8" /> : null}
        {children}
      </motion.div>
    </div>
  );
}
