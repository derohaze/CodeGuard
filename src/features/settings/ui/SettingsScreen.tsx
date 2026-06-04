import type { ReactNode } from "react";
import { ArrowLeft, Cog, Scale, ShieldCheck, Zap } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { RuntimeSettings, UpdateRuntimeSettingsPayload } from "@/shared/api/security";

interface SettingsScreenProps {
  onBack: () => void;
  settings: RuntimeSettings;
  isSaving: boolean;
  onPatchSettings: (patch: UpdateRuntimeSettingsPayload) => void | Promise<void>;
}

const sections = [
  { id: "general", label: "General", icon: Cog },
];

const scanModes = [
  { value: "deep", label: "Deep analysis" },
  { value: "fast", label: "Fast analysis" },
] as const;
const scanPresets = [
  {
    id: "safe",
    label: "Safe mode",
    description: "Prioritize high-confidence findings and calmer defaults for steady review flows.",
    icon: ShieldCheck,
    defaultMode: "deep",
  },
  {
    id: "balanced",
    label: "Balanced",
    description: "Keep security coverage broad without turning every analyst run into a noisy sweep.",
    icon: Scale,
    defaultMode: "deep",
  },
  {
    id: "aggressive",
    label: "Aggressive",
    description: "Push deeper heuristics and stricter checks to surface more risky edges earlier.",
    icon: Zap,
    defaultMode: "fast",
  },
] as const;

const remediationAttemptOptions = [1, 2, 3, 4, 5];
const ingestionRpsOptions = [2, 5, 10, 15, 20, 30];
const ingestionRetryOptions = [1, 2, 3, 4, 5, 6];

export function SettingsScreen({ onBack, settings, onPatchSettings, isSaving }: SettingsScreenProps) {
  const hasElectronTitlebar = typeof window !== "undefined" && typeof window.electronAPI?.versions?.electron === "string";

  return (
    <div key="settings-screen" className="flex min-h-0 flex-1 bg-surface">
      <aside className="flex w-[272px] shrink-0 flex-col border-r bg-[#f7f2eb]" style={{ borderColor: "hsl(var(--border-soft))" }}>
        {hasElectronTitlebar ? <div className="app-drag h-8 border-b" style={{ borderColor: "hsl(var(--border-soft))" }} /> : null}
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
          {sections.map((section) => {
            const Icon = section.icon;

            return (
              <button
                key={section.id}
                className="flex w-full items-center gap-3 rounded-xl bg-card px-3 py-2.5 text-left text-sm text-txt-primary shadow-sm"
              >
                <Icon size={16} className="text-txt-primary" />
                <span className="font-medium">{section.label}</span>
              </button>
            );
          })}
        </div>
      </aside>

      <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto bg-[#fbf7f1]">
        <div className="mx-auto flex w-full max-w-[960px] flex-col gap-6 px-10 py-10">
          <div className="flex items-center justify-between gap-6">
            <div>
              <h2 className="text-[32px] font-semibold tracking-[-0.03em] text-txt-primary">General</h2>
              {isSaving ? <p className="mt-1 text-xs text-txt-tertiary">Saving settings...</p> : null}
            </div>
          </div>

          <div
            className="overflow-hidden rounded-[26px] border bg-card shadow-[0_18px_48px_rgba(52,42,28,0.08)]"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="border-b px-5 py-5" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <div className="mb-4">
                <p className="text-[15px] font-medium text-txt-primary">Analyst preset</p>
                <p className="mt-1 text-sm leading-6 text-txt-secondary">
                  Choose the default posture for new analysis sessions.
                </p>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {scanPresets.map((preset) => {
                  const Icon = preset.icon;
                  const active = settings.defaultPreset === preset.id;

                  return (
                    <button
                      key={preset.id}
                      onClick={() => {
                        void onPatchSettings({
                          defaultPreset: preset.id,
                          defaultScanMode: preset.defaultMode,
                        });
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
                <Select
                  value={settings.defaultScanMode}
                  onValueChange={(value) => void onPatchSettings({ defaultScanMode: value as RuntimeSettings["defaultScanMode"] })}
                >
                  <SelectTrigger className={selectClassName}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className={selectContentClassName}>
                    {scanModes.map((mode) => (
                      <SelectItem key={mode.value} value={mode.value} className={selectItemClassName}>
                        {mode.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              }
            />

            <SettingsRow
              title="Auto-open results"
              description="Open findings automatically after analysis completion."
              control={
                <Switch
                  checked={settings.autoOpenResults}
                  onCheckedChange={(checked) => void onPatchSettings({ autoOpenResults: checked })}
                />
              }
            />

            <SettingsRow
              title="Sidebar behavior"
              description="Remember the last open or collapsed state."
              control={
                <Switch
                  checked={settings.rememberSidebarState}
                  onCheckedChange={(checked) => void onPatchSettings({ rememberSidebarState: checked })}
                />
              }
            />

            <SettingsRow
              title="Remediation retries"
              description="Maximum tuning attempts per remediation run."
              control={
                <Select
                  value={String(settings.remediationMaxAttempts)}
                  onValueChange={(value) => void onPatchSettings({ remediationMaxAttempts: Number(value) })}
                >
                  <SelectTrigger className={selectClassName}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className={selectContentClassName}>
                    {remediationAttemptOptions.map((value) => (
                      <SelectItem key={value} value={String(value)} className={selectItemClassName}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              }
            />

            <SettingsRow
              title="Reuse explanation on retry"
              description="Reduce provider requests by reusing the first explanation across retries."
              control={
                <Switch
                  checked={settings.remediationReuseExplanation}
                  onCheckedChange={(checked) => void onPatchSettings({ remediationReuseExplanation: checked })}
                />
              }
            />

            <SettingsRow
              title="External ingestion max RPS"
              description="Rate limit for external security knowledge fetch runs."
              control={
                <Select
                  value={String(settings.externalIngestionMaxRps)}
                  onValueChange={(value) => void onPatchSettings({ externalIngestionMaxRps: Number(value) })}
                >
                  <SelectTrigger className={selectClassName}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className={selectContentClassName}>
                    {ingestionRpsOptions.map((value) => (
                      <SelectItem key={value} value={String(value)} className={selectItemClassName}>
                        {value} req/s
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              }
            />

            <SettingsRow
              title="External ingestion retries"
              description="Retry attempts for transient external source failures."
              control={
                <Select
                  value={String(settings.externalIngestionRetryAttempts)}
                  onValueChange={(value) => void onPatchSettings({ externalIngestionRetryAttempts: Number(value) })}
                >
                  <SelectTrigger className={selectClassName}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className={selectContentClassName}>
                    {ingestionRetryOptions.map((value) => (
                      <SelectItem key={value} value={String(value)} className={selectItemClassName}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              }
              border={false}
            />
          </div>
        </div>
      </div>
    </div>
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
  control: ReactNode;
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

const selectClassName =
  "h-11 w-[178px] rounded-xl border bg-[#f6f1ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0";

const selectContentClassName =
  "rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]";

const selectItemClassName = "rounded-lg text-sm focus:bg-secondary focus:text-txt-primary";
