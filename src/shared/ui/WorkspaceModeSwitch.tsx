import { motion } from "framer-motion";
import { Shield } from "lucide-react";
import type { WorkspaceMode } from "@/shared/types/app";

interface WorkspaceModeSwitchProps {
  mode?: WorkspaceMode;
  onChange?: (mode: WorkspaceMode) => void;
}

export function WorkspaceModeSwitch({ mode = "security", onChange }: WorkspaceModeSwitchProps) {
  const Icon = Shield;

  return (
    <div
      className="inline-flex rounded-[18px] border bg-[#ebe6d8] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]"
      style={{ borderColor: "hsl(var(--border-soft))" }}
      aria-label="Security workspace"
    >
      <button
        className="relative inline-flex h-9 min-w-[56px] items-center justify-center rounded-[14px] px-3 text-txt-primary"
        type="button"
        onClick={() => onChange?.(mode)}
        aria-label="Security"
      >
        <motion.span
          layoutId="workspace-mode-thumb"
          className="absolute inset-0 rounded-[14px] bg-white shadow-[0_4px_12px_rgba(0,0,0,0.12)]"
          transition={{ type: "spring", stiffness: 560, damping: 42, mass: 0.68 }}
        />
        <span className="relative z-10 inline-flex items-center justify-center">
          <Icon size={16} strokeWidth={2.1} />
        </span>
      </button>
    </div>
  );
}
