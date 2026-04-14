import { Clock3, FileCode2, FolderGit2, Play, ScanSearch, ShieldCheck, Trash2, X } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { basename } from "@/features/dashboard/model/home-screen.utils";
import { useHomeScreen } from "@/features/dashboard/model/useHomeScreen";
import type { StartScanPayload } from "@/shared/api/security";
import { Loader } from "@/shared/ui/Loader";

interface HomeScreenProps {
  onStartScan: (payload: StartScanPayload) => void | Promise<void>;
  defaultPreset?: "safe" | "balanced" | "aggressive";
  defaultScanMode?: "fast" | "deep";
}

export function HomeScreen({ onStartScan, defaultPreset, defaultScanMode }: HomeScreenProps) {
  const {
    canBrowse,
    clearRecentSources,
    inferredWorkspace,
    loading,
    pickPath,
    pickingPath,
    preset,
    recentSources,
    removeRecentSource,
    scanMode,
    scanPresets,
    scanSummary,
    selectedPreset,
    selectedTargetName,
    setLoading,
    setPreset,
    setScanMode,
    setTargetPath,
    setTargetType,
    targetPath,
    targetType,
  } = useHomeScreen({
    preset: defaultPreset ?? "balanced",
    scanMode: defaultScanMode ?? "deep",
  });

  const handleStart = () => {
    if (loading || !targetPath) return;
    setLoading(true);
    const payload: StartScanPayload = {
      sourcePath: targetPath,
      targetType,
      preset,
      scanMode,
    };
    setTimeout(() => {
      void Promise.resolve(onStartScan(payload)).finally(() => {
        setLoading(false);
      });
    }, 250);
  };

  return (
    <div className="hide-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto dotted-bg px-5 pb-4 pt-8 sm:px-6 lg:px-8">
      <div className="flex min-h-full w-full flex-1 flex-col gap-5">
        <div className="max-w-[760px]">
          <div className="flex items-center gap-2 text-[13px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">
            <ScanSearch size={15} className="text-txt-secondary" />
            Analyst setup
          </div>
          <h2 className="mt-3 text-[32px] font-semibold tracking-[-0.04em] text-txt-primary">
            Start a security analysis with a clear flow
          </h2>
          <p className="mt-3 text-[15px] leading-7 text-txt-secondary">
            Pick the source you want to analyze, choose whether it runs on a folder or a single file,
            then launch the exact review flow the backend powers now: analysis, findings,
            explanation, fix suggestion, and patch review.
          </p>
        </div>

        <div
          className="flex flex-1 flex-col rounded-[28px] border bg-card p-5 shadow-[0_12px_28px_rgba(52,42,28,0.03)]"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] items-start">
            <div className="min-w-0 space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <SetupField
                  label="Workspace"
                  description="This is inferred automatically from the source path you choose."
                >
                  <div
                    className="flex min-h-11 min-w-0 items-center rounded-[14px] border bg-[#f7f2ea] px-4 text-sm font-medium text-txt-primary"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    <span className="truncate whitespace-nowrap">{inferredWorkspace}</span>
                  </div>
                </SetupField>

                <SetupField
                  label="Analyst preset"
                  description="Pick the default behavior before the analysis starts."
                >
                  <Select value={preset} onValueChange={(value) => setPreset(value as typeof preset)}>
                    <SelectTrigger
                      className="h-11 rounded-[14px] border bg-[#f7f2ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0"
                      style={{ borderColor: "hsl(var(--border-soft))" }}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                      {scanPresets.map((item) => (
                        <SelectItem
                          key={item.id}
                          value={item.id}
                          className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary"
                        >
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </SetupField>

                <SetupField
                  label="Analysis mode"
                  description="Choose between a fast first pass and the full deep analysis pipeline."
                >
                  <Select value={scanMode} onValueChange={(value) => setScanMode(value as "fast" | "deep")}>
                    <SelectTrigger
                      className="h-11 rounded-[14px] border bg-[#f7f2ea] text-sm font-medium text-txt-primary focus:ring-0 focus:ring-offset-0"
                      style={{ borderColor: "hsl(var(--border-soft))" }}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-xl border border-border-soft bg-surface text-txt-primary shadow-[0_18px_40px_rgba(52,42,28,0.12)]">
                      <SelectItem value="deep" className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary">
                        Deep analysis
                      </SelectItem>
                      <SelectItem value="fast" className="rounded-lg text-sm focus:bg-secondary focus:text-txt-primary">
                        Fast analysis
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </SetupField>
              </div>

              <SetupField
                label="What do you want to analyze?"
                description="Choose whether the analysis should run on a folder or a specific file."
              >
                <div
                  className="inline-flex rounded-[18px] border bg-[#f3ede4] p-1"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  {[
                    { id: "folder", label: "Folder", icon: FolderGit2 },
                    { id: "file", label: "File", icon: FileCode2 },
                  ].map((option) => {
                    const Icon = option.icon;
                    const active = targetType === option.id;

                    return (
                      <button
                        key={option.id}
                        onClick={() => {
                          setTargetType(option.id as "folder" | "file");
                          setTargetPath("");
                        }}
                        className={`inline-flex items-center gap-2 rounded-[14px] border px-4 py-2 text-sm transition-colors ${
                          active
                            ? "border-[hsl(var(--border-soft))] bg-white text-txt-primary"
                            : "border-transparent bg-transparent text-txt-secondary hover:text-txt-primary"
                        }`}
                      >
                        <Icon size={15} />
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </SetupField>

              <SetupField
                label={targetType === "folder" ? "Folder target" : "File target"}
                description={
                  targetType === "folder"
                    ? "Choose the project root or any folder inside the project from your device."
                    : "Choose a concrete source file from your device so the analysis starts from that location."
                }
              >
                <div className="flex min-h-[234px] flex-col gap-3">
                  <button
                    onClick={pickPath}
                    disabled={pickingPath || !canBrowse}
                    className="inline-flex h-11 items-center gap-2 self-start rounded-[14px] border bg-[#f7f2ea] px-4 text-sm font-medium text-txt-primary transition-colors disabled:opacity-80"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    {pickingPath ? (
                      <>
                        <Loader variant="spin" className="size-4 text-txt-primary" />
                        Opening picker...
                      </>
                    ) : (
                      <>
                        {targetType === "folder" ? <FolderGit2 size={15} /> : <FileCode2 size={15} />}
                        {targetType === "folder" ? "Choose folder" : "Choose file"}
                      </>
                    )}
                  </button>
                  {!canBrowse && (
                    <p className="text-[13px] leading-6 text-txt-secondary">
                      File picking is available only after a full Electron restart with
                      <span className="mx-1 font-medium text-txt-primary">bun run electron:dev</span>
                      .
                    </p>
                  )}
                  <div
                    className="min-w-0 h-[78px] overflow-hidden rounded-[18px] border bg-[#fbf7f1] px-4 py-3"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">
                      Selected source
                    </p>
                    <p
                      className="mt-2 truncate whitespace-nowrap text-[14px] font-medium leading-6 text-txt-primary"
                      title={selectedTargetName}
                    >
                      {selectedTargetName}
                    </p>
                  </div>
                  <div
                    className="min-w-0 h-[88px] overflow-hidden rounded-[18px] border bg-[#fbf7f1] px-4 py-3"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                  >
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">Selected path</p>
                    <p
                      className="mt-2 truncate whitespace-nowrap font-mono text-[13px] leading-6 text-txt-primary"
                      title={targetPath || "Choose a source to preview its path here."}
                    >
                      {targetPath || "Choose a source to preview its path here."}
                    </p>
                  </div>
                </div>
              </SetupField>

            </div>

            <div className="min-w-0 flex flex-col space-y-4">
              <div
                className="rounded-[24px] border bg-[#fbf7f1] px-5 py-5 shadow-[0_10px_22px_rgba(52,42,28,0.025)]"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex items-center gap-2 text-txt-primary">
                  <ShieldCheck size={16} className="text-status-success" />
                  <p className="text-sm font-medium">Current analyst plan</p>
                </div>
                <div className="mt-4 space-y-2.5 text-sm text-txt-secondary">
                  <PlanRow label="Workspace" value={inferredWorkspace} />
                  <PlanRow label="Analysis mode" value={scanMode === "deep" ? "Deep analysis" : "Fast analysis"} />
                  <PlanRow label="Preset" value={selectedPreset.label} />
                  <PlanRow
                    label="Target type"
                    value={targetType === "folder" ? "Folder analysis" : "Single file analysis"}
                  />
                  <PlanRow label="Source" value={selectedTargetName} />
                </div>
                <div
                  className="mt-4 h-[156px] overflow-hidden rounded-[18px] border bg-card px-4 py-3"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">
                    What happens next
                  </p>
                  <p className="mt-2 h-[96px] overflow-hidden text-[13px] leading-6 text-txt-secondary">{scanSummary}</p>
                </div>
                <p className="mt-4 min-h-[48px] text-[13px] leading-6 text-txt-secondary">
                  {selectedPreset.description}
                </p>
                <button
                  onClick={handleStart}
                  disabled={loading || !targetPath}
                  className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-[16px] bg-primary px-5 text-sm font-medium text-primary-foreground shadow-[0_6px_16px_rgba(20,20,18,0.1)] transition-colors hover:bg-primary/95 disabled:opacity-90"
                >
                  {loading ? (
                    <>
                      <Loader variant="spin" className="size-4 text-primary-foreground" />
                      Starting analysis...
                    </>
                  ) : (
                    <>
                      <Play size={15} />
                      {targetPath ? "Start security analysis" : "Choose a source first"}
                    </>
                  )}
                </button>
              </div>

              <div
                className="flex flex-col rounded-[24px] border bg-card px-5 py-5 shadow-[0_10px_22px_rgba(52,42,28,0.025)]"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                  <div className="text-txt-primary">
                    <p className="text-sm font-medium">Recent sources</p>
                    <p className="mt-1 text-[13px] leading-6 text-txt-secondary">
                      Reuse one of your latest sources without opening the picker again.
                    </p>
                  </div>
                  <div className="mt-4 flex flex-col">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] text-txt-tertiary">
                        Showing the latest 2 {targetType === "folder" ? "folders" : "files"}, with scroll for older ones.
                      </p>
                      {recentSources.length > 0 && (
                        <button
                          onClick={() => clearRecentSources(targetType)}
                          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[12px] text-txt-secondary transition-colors hover:bg-[#f6f1ea] hover:text-txt-primary"
                        >
                          <Trash2 size={12} />
                          Clear history
                        </button>
                      )}
                    </div>
                    <div className="hide-scrollbar mt-3 h-[160px] overflow-y-auto pr-1">
                      <div className="grid gap-2">
                      {recentSources.length > 0 ? (
                        recentSources.map((item) => (
                          <div
                            key={`${item.type}:${item.path}`}
                            className="flex items-start gap-3 rounded-[18px] border bg-[#fbf7f1] px-4 py-3"
                            style={{ borderColor: "hsl(var(--border-soft))" }}
                          >
                            <button
                              onClick={() => setTargetPath(item.path)}
                              className="min-w-0 flex-1 text-left transition-colors hover:text-txt-primary"
                            >
                              <p className="truncate text-sm font-medium text-txt-primary">
                                {basename(item.path)}
                              </p>
                              <p className="truncate text-[13px] text-txt-secondary">{item.workspace}</p>
                            </button>
                            <div className="mt-0.5 flex shrink-0 items-center gap-2">
                              <div className="flex items-center gap-1 text-[12px] text-txt-tertiary">
                                <Clock3 size={12} />
                                Recent
                              </div>
                              <button
                                onClick={() => removeRecentSource(item.path, item.type)}
                                className="rounded-lg p-1 text-txt-tertiary transition-colors hover:bg-card hover:text-txt-primary"
                                aria-label={`Remove ${basename(item.path)} from history`}
                              >
                                <X size={13} />
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div
                          className="flex h-[160px] items-center rounded-[18px] border bg-[#fbf7f1] px-4 py-5 text-[13px] text-txt-tertiary"
                          style={{ borderColor: "hsl(var(--border-soft))" }}
                        >
                          No recent {targetType === "folder" ? "folders" : "files"} yet.
                        </div>
                      )}
                      </div>
                    </div>
                  </div>
                </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SetupField({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-full">
      <p className="text-[13px] font-medium text-txt-primary">{label}</p>
      <p className="mt-1 text-sm leading-6 text-txt-secondary flex-1">{description}</p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function PlanRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-txt-tertiary">{label}</span>
      <span className="max-w-[60%] text-right text-txt-primary">{value}</span>
    </div>
  );
}
