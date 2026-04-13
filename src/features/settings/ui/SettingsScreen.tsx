import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Cog, Palette, Scale, ShieldCheck, Zap } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

interface SettingsScreenProps {
  onBack: () => void;
}

const sections = [
  { id: "general", label: "General", icon: Cog },
  { id: "appearance", label: "Appearance", icon: Palette },
];

const scanModes = ["Balanced", "Strict", "Fast"];
const motionModes = ["Fluid", "Reduced", "Instant"];
const scanPresets = [
  {
    id: "Safe mode",
    label: "Safe mode",
    description: "Prioritize high-confidence findings and calmer defaults for steady review flows.",
    icon: ShieldCheck,
  },
  {
    id: "Balanced",
    label: "Balanced",
    description: "Keep security coverage broad without turning every analyst run into a noisy sweep.",
    icon: Scale,
  },
  {
    id: "Aggressive",
    label: "Aggressive",
    description: "Push deeper heuristics and stricter checks to surface more risky edges earlier.",
    icon: Zap,
  },
] as const;

export function SettingsScreen({ onBack }: SettingsScreenProps) {
  const [activeSection, setActiveSection] = useState<"general" | "appearance">("general");
  const [scanMode, setScanMode] = useState("Balanced");
  const [scanPreset, setScanPreset] = useState<(typeof scanPresets)[number]["id"]>("Balanced");
  const [motionMode, setMotionMode] = useState("Fluid");
  const [autoOpenResults, setAutoOpenResults] = useState(true);
  const [rememberSidebar, setRememberSidebar] = useState(true);
  const [softContrast, setSoftContrast] = useState(true);

  return (
    <motion.div
      key="settings-screen"
      initial={{ opacity: 0, x: 18, scale: 0.995 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: -14, scale: 0.995 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className="flex min-h-0 flex-1 bg-surface"
    >
      <aside className="flex w-[272px] shrink-0 flex-col border-r bg-[#f7f2eb]" style={{ borderColor: "hsl(var(--border-soft))" }}>
        <div className="app-drag h-8 border-b" style={{ borderColor: "hsl(var(--border-soft))" }} />
        <div className="flex h-12 items-center border-b px-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
          <button
            onClick={onBack}
            className="app-no-drag inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-txt-secondary transition-colors hover:bg-secondary hover:text-txt-primary"
          >
            <ArrowLeft size={15} />
            <span>Back to app</span>
          </button>
        </div>

        <div className="space-y-1 px-3 py-4">
          {sections.map((section, index) => {
            const Icon = section.icon;
            const active = activeSection === section.id;

            return (
              <motion.button
                key={section.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.03 * index, duration: 0.18 }}
                onClick={() => setActiveSection(section.id as "general" | "appearance")}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                  active ? "bg-card text-txt-primary shadow-sm" : "text-txt-secondary hover:bg-card/80 hover:text-txt-primary"
                }`}
              >
                <Icon size={16} className={active ? "text-txt-primary" : "text-txt-secondary"} />
                <span className="font-medium">{section.label}</span>
              </motion.button>
            );
          })}
        </div>
      </aside>

      <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto bg-[#fbf7f1]">
        <div className="mx-auto flex w-full max-w-[920px] flex-col gap-6 px-10 py-10">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, delay: 0.04 }}
            className="flex items-center justify-between gap-6"
          >
            <div>
              <h2 className="text-[32px] font-semibold tracking-[-0.03em] text-txt-primary">
                {activeSection === "general" ? "General" : "Appearance"}
              </h2>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.08 }}
            className="overflow-hidden rounded-[26px] border bg-card shadow-[0_18px_48px_rgba(52,42,28,0.08)]"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            {activeSection === "general" ? (
              <>
                <div className="border-b px-5 py-5" style={{ borderColor: "hsl(var(--border-soft))" }}>
                  <div className="mb-4">
                    <p className="text-[15px] font-medium text-txt-primary">Analyst preset</p>
                    <p className="mt-1 text-sm leading-6 text-txt-secondary">
                      Choose the overall posture CodeGuard should apply before fine-tuning individual settings.
                    </p>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    {scanPresets.map((preset) => {
                      const Icon = preset.icon;
                      const active = scanPreset === preset.id;

                      return (
                        <button
                          key={preset.id}
                          onClick={() => {
                            setScanPreset(preset.id);
                            setScanMode(preset.id === "Safe mode" ? "Strict" : preset.id === "Aggressive" ? "Fast" : "Balanced");
                          }}
                          className={`rounded-2xl border px-4 py-4 text-left transition-colors ${
                            active ? "bg-[#f8f2e9]" : "bg-[#fcf8f2] hover:bg-[#f8f2e9]"
                          }`}
                          style={{ borderColor: active ? "rgba(196, 161, 118, 0.42)" : "hsl(var(--border-soft))" }}
                        >
                          <div className="flex items-center gap-2 text-txt-primary">
                            <div className={`flex h-8 w-8 items-center justify-center rounded-xl ${active ? "bg-card" : "bg-white/70"}`}>
                              <Icon size={16} strokeWidth={1.9} />
                            </div>
                            <span className="text-sm font-medium">{preset.label}</span>
                          </div>
                          <p className="mt-3 text-[13px] leading-6 text-txt-secondary">{preset.description}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <SettingsRow
                  title="Default analysis mode"
                  description="Set how new security analysis sessions start."
                  control={
                    <Select value={scanMode} onValueChange={setScanMode}>
                      <SelectTrigger className="h-11 w-[154px] rounded-xl border bg-[#f6f1ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0" style={{ borderColor: "hsl(var(--border-soft))" }}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                        {scanModes.map((mode) => (
                          <SelectItem key={mode} value={mode} className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary">
                            {mode}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  }
                />

                <SettingsRow
                  title="Auto-open results"
                  description="Open findings automatically after analysis completion."
                  control={<Switch checked={autoOpenResults} onCheckedChange={setAutoOpenResults} />}
                />

                <SettingsRow
                  title="Motion profile"
                  description="Adjust how transitions feel across the app."
                  control={
                    <Select value={motionMode} onValueChange={setMotionMode}>
                      <SelectTrigger className="h-11 w-[154px] rounded-xl border bg-[#f6f1ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0" style={{ borderColor: "hsl(var(--border-soft))" }}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                        {motionModes.map((mode) => (
                          <SelectItem key={mode} value={mode} className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary">
                            {mode}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  }
                />

                <SettingsRow
                  title="Sidebar behavior"
                  description="Remember the last open or collapsed state."
                  control={<Switch checked={rememberSidebar} onCheckedChange={setRememberSidebar} />}
                  border={false}
                />
              </>
            ) : (
              <>
                <SettingsRow
                  title="Theme"
                  description="Keep the interface aligned with your current light system."
                  control={
                    <Select value="Light">
                      <SelectTrigger className="h-11 w-[154px] rounded-xl border bg-[#f6f1ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0" style={{ borderColor: "hsl(var(--border-soft))" }}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                        <SelectItem value="Light" className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary">
                          Light
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  }
                />

                <SettingsRow
                  title="Surface contrast"
                  description="Use softer panels for a cleaner light workspace."
                  control={<Switch checked={softContrast} onCheckedChange={setSoftContrast} />}
                  border={false}
                />
              </>
            )}
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}

function SettingsRow({
  title,
  description,
  control,
  border = true,
}: {
  title: string;
  description: string;
  control: React.ReactNode;
  border?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between gap-6 px-5 py-5 ${border ? "border-b" : ""}`} style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="min-w-0">
        <p className="text-[15px] font-medium text-txt-primary">{title}</p>
        <p className="mt-1 text-sm leading-6 text-txt-secondary">{description}</p>
      </div>
      {control}
    </div>
  );
}
