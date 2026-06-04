import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Binary, Cloud, FileCode2, GitBranch, ShieldAlert, Sparkles } from "lucide-react";
import { ShinyText } from "@/components/ui/shiny-text";
import type { Finding, RemediationPlan } from "@/entities/finding/model/types";
import { generateBatchRemediation, generateFix } from "@/shared/api/security";
import { toast } from "@/components/ui/sonner";
import { toAnalystCopy } from "@/shared/lib/analyst-copy";

interface Props {
  onComplete: (plan: RemediationPlan) => void;
  onInvalidatedFinding?: () => Promise<void> | void;
  finding?: Finding | null;
  findings?: Finding[];
  mode?: "single" | "batch";
  sessionId?: string | null;
}

type TaskLine = {
  id: string;
  title: string;
  text: string;
  type: "done" | "status" | "pending";
  agent?: string;
};

export function SuggestFixScreen({ onComplete, onInvalidatedFinding, finding, findings = [], mode = "single", sessionId }: Props) {
  const [visibleLines, setVisibleLines] = useState(0);
  const [typedChars, setTypedChars] = useState(0);
  const [plan, setPlan] = useState<RemediationPlan | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [showPlanDetails, setShowPlanDetails] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [taskLines, setTaskLines] = useState<TaskLine[]>([
    { id: "context", title: "Building remediation context", text: "Collecting the minimal remediation context from the real analysis evidence.", type: "done", agent: "context_agent" },
    { id: "prepare", title: "Preparing orchestration", text: "Preparing the explain and fix agents.", type: "done", agent: "router" },
    { id: "generate", title: "Generating remediation", text: "Generating a code-aware remediation plan...", type: "status", agent: "fix_agent" },
  ]);

  const currentLine = taskLines[visibleLines];
  const findingCount = findings.length || (finding ? 1 : 0);
  const isBatch = mode === "batch";
  const isGenerating = !plan && !planError;

  useEffect(() => {
    let active = true;

    if (!sessionId) {
      toast.error("An analyst session is required to generate remediation.");
      return undefined;
    }

  const load = async () => {
    try {
      const plan = isBatch ? await generateBatchRemediation(sessionId) : await generateFix({
        sessionId,
        findingId: finding?.id ?? "",
      });

        if (!active) return;
        applyPlan(plan);
    } catch (error) {
      if (!active) return;
      console.error("[Aegix] Failed to generate remediation plan", error);
      if (error instanceof Error && error.message.toLowerCase().includes("invalidated during remediation preflight")) {
        await onInvalidatedFinding?.();
        return;
      }
      setPlan(null);
      setIsReady(false);
      const message = error instanceof Error ? error.message : "Unable to generate the remediation plan.";
      setPlanError(toAnalystCopy(message));
      toast.error(toAnalystCopy(message));
    }
  };

    void load();

    return () => {
      active = false;
    };
  }, [finding, findingCount, isBatch, mode, sessionId]);

  useEffect(() => {
    if (!currentLine) {
      return undefined;
    }

    if (typedChars < currentLine.text.length) {
      const timer = window.setTimeout(() => {
        setTypedChars((current) => current + 1);
      }, currentLine.type === "status" ? 24 : 16);

      return () => window.clearTimeout(timer);
    }

    if (visibleLines === taskLines.length - 1 && !plan) {
      return undefined;
    }

    const advanceTimer = window.setTimeout(() => {
      setVisibleLines((current) => current + 1);
      setTypedChars(0);
    }, currentLine.type === "status" ? 240 : 140);

    return () => window.clearTimeout(advanceTimer);
  }, [currentLine, plan, taskLines.length, typedChars, visibleLines]);

  useEffect(() => {
    if (!isGenerating) {
      return undefined;
    }

    const timelineDetails = buildGeneratingTimeline({ mode, findingCount, finding });
    let lineIndex = 0;
    const timer = window.setInterval(() => {
      setTaskLines((current) => {
        if (lineIndex >= timelineDetails.length) {
          return current;
        }

        const next = timelineDetails[lineIndex];
        lineIndex += 1;

        if (current.some((line) => line.id === next.id)) {
          return current;
        }

        return current.map((line, index) =>
          index === current.length - 1
            ? { ...line, type: "done" }
            : line,
        ).concat(next);
      });
    }, 3200);

    return () => window.clearInterval(timer);
  }, [finding, findingCount, isGenerating, mode]);

  const handleContinue = () => {
    if (plan && isReady) {
      onComplete(plan);
    }
  };

  const applyPlan = (nextPlan: RemediationPlan) => {
    const nextLines = buildTaskLines({
      mode,
      findingCount,
      finding,
      plan: nextPlan,
    });
    const hasStrategies = nextPlan.strategies.length > 0;
    const hasPatch = Boolean(nextPlan.patch?.afterSnippet?.trim()) && Boolean(nextPlan.patch?.diff?.trim());
    const isPlanValid = hasStrategies && hasPatch;
    setPlan(isPlanValid ? nextPlan : null);
    setTaskLines(nextLines);
    setIsReady(isPlanValid);
    setShowPlanDetails(false);
    setPlanError(isPlanValid ? null : buildPlanErrorMessage(nextPlan));
  };

  const handleRetry = async () => {
    if (!sessionId) return;
    setIsRetrying(true);
    setPlanError(null);
    try {
      const nextPlan = isBatch ? await generateBatchRemediation(sessionId) : await generateFix({
        sessionId,
        findingId: finding?.id ?? "",
      });
      applyPlan(nextPlan);
    } catch (error) {
      console.error("[Aegix] Failed to regenerate remediation plan", error);
      if (error instanceof Error && error.message.toLowerCase().includes("invalidated during remediation preflight")) {
        await onInvalidatedFinding?.();
        return;
      }
      const message = error instanceof Error ? error.message : "Unable to regenerate the remediation plan.";
      setPlan(null);
      setIsReady(false);
      setPlanError(toAnalystCopy(message));
      toast.error(toAnalystCopy(message));
    } finally {
      setIsRetrying(false);
    }
  };

  const headerText = useMemo(
    () =>
      isBatch
        ? `[Security Analyst] Batch remediation for ${findingCount} validated finding${findingCount === 1 ? "" : "s"}`
        : `[Security Analyst] Fix ${finding?.category.toLowerCase() ?? "security_issue"}: ${finding?.file ?? "Unknown file"}`,
    [finding?.category, finding?.file, findingCount, isBatch],
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.18 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg"
    >
      <div className="mx-auto max-w-6xl px-8 py-8">
        <div className="mb-8 flex items-start gap-3 text-left text-txt-primary">
          <div className="pt-0.5 text-txt-primary">
            <Cloud size={26} strokeWidth={2} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-medium tracking-[-0.02em] text-txt-primary">{headerText}</p>
            <p className="mt-1 text-sm text-txt-tertiary">
              {isBatch
                ? "Preparing a remediation plan across the validated findings in this analysis."
                : (finding?.file ?? "app/services/notifiers/script_runner.py")}
            </p>
          </div>
        </div>

        <div className="space-y-5 pl-10">
          {taskLines.slice(0, visibleLines).map((line, index) => (
            <div key={`${index}-${line.id}-${line.text}`}>
              <RenderedLine text={line.text} type={line.type} />
              {line.agent ? (
                <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                  {(line.agent ?? "agent").replaceAll("_", " ")}
                </p>
              ) : null}
            </div>
          ))}

          {currentLine && (
            <div>
              <RenderedLine text={currentLine.text.slice(0, typedChars)} type={currentLine.type} streaming />
              {currentLine.agent ? (
                <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                  {(currentLine.agent ?? "agent").replaceAll("_", " ")}
                </p>
              ) : null}
            </div>
          )}

          {plan && !planError ? (
            <div className="rounded-[24px] border bg-card/80 px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-txt-primary">Remediation plan ready</p>
                  <p className="mt-1 text-sm leading-6 text-txt-secondary">
                    The agents finished preparing the remediation plan. No workspace file changes have been applied yet. The patch is written only after you approve it in the next step.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => setShowPlanDetails((current) => !current)}
                    className="rounded-full border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-colors"
                    style={{ borderColor: "hsl(var(--border-primary))" }}
                  >
                    {showPlanDetails ? "Hide plan details" : "View plan details"}
                  </button>
                  <button
                    onClick={handleContinue}
                    disabled={!isReady || !plan}
                    className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors disabled:opacity-60"
                  >
                    Continue to patch review
                  </button>
                </div>
              </div>
            </div>
          ) : null}

          <AnimatePresence initial={false}>
            {showPlanDetails && plan?.metrics ? (
              <motion.div
                key="plan-metrics"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
                className="grid gap-3 pl-0 md:grid-cols-2 xl:grid-cols-4"
              >
                <MetricCard icon={FileCode2} label="Affected file" value={plan.metrics.file} />
                <MetricCard icon={ShieldAlert} label="Vulnerability" value={plan.metrics.vulnerabilityType} />
                <MetricCard icon={Binary} label="Analyzed lines" value={`${plan.metrics.analyzedLines} lines`} />
                <MetricCard icon={GitBranch} label="Execution path" value={`${plan.metrics.pathSteps} steps`} />
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence initial={false}>
            {showPlanDetails && plan?.steps?.length ? (
              <motion.div
                key="plan-steps"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="rounded-[24px] border bg-card/70 px-5 py-4"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="mb-3 flex items-center gap-2">
                  <p className="text-sm font-semibold text-txt-primary">Agent remediation reasoning</p>
                </div>
                <div className="space-y-3">
                  {plan.steps.map((step) => (
                    <div key={step.id} className="rounded-2xl border bg-[#f7f7f7] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-txt-primary">{step.title}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                            {step.agent.replaceAll("_", " ")}
                          </p>
                        </div>
                        <span className="rounded-full border bg-card px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                          {step.status}
                        </span>
                      </div>
                      {step.details.length ? (
                        <div className="mt-3 space-y-1.5">
                          {step.details.map((detail, index) => (
                            <p key={buildIndexedKey("plan-step-detail", detail, index)} className="text-[13px] leading-6 text-txt-secondary">{detail}</p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>

          {planError ? (
            <div className="rounded-[22px] border bg-[#fff7f5] px-5 py-4 text-sm text-status-critical" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
              <p>{planError}</p>
              <div className="mt-4">
                <button
                  onClick={() => void handleRetry()}
                  disabled={isRetrying}
                  className="rounded-full border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-colors disabled:opacity-60"
                  style={{ borderColor: "hsl(var(--border-primary))" }}
                >
                  {isRetrying ? "Regenerating..." : "Try another fix"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}

function buildTaskLines({
  mode,
  findingCount,
  finding,
  plan,
}: {
  mode: "single" | "batch";
  findingCount: number;
  finding?: Finding | null;
  plan: RemediationPlan;
}): TaskLine[] {
  const explanation = plan.explanation;
  return plan.steps.length
    ? plan.steps.map((step, index) => ({
        id: step.id,
        title: step.title,
        text: step.details[0]
          ?? (index === 0 && mode === "batch"
            ? `Collected remediation context for ${findingCount} validated findings.`
            : index === 0
              ? `Loaded the traced execution path for ${finding?.file ?? "the selected finding"}.`
              : step.title),
        type: "done",
        agent: step.agent,
      }))
    : [
        {
          id: "context",
          title: "Building remediation context",
          text:
            mode === "batch"
              ? `Collected remediation context for ${findingCount} validated finding${findingCount === 1 ? "" : "s"}.`
              : `Loaded the traced execution path for ${finding?.file ?? "the selected finding"}.`,
          type: "done",
          agent: "context_agent",
        },
        {
          id: "explain",
          title: "Analyzing vulnerability",
          text:
            explanation?.entryPoint
              ? `Mapped the exploit entry point as ${explanation.entryPoint}.`
              : "Mapped the relevant entry point from the real scan evidence.",
          type: "done",
          agent: "explain_agent",
        },
        {
          id: "final",
          title: "Preparing patch",
          text: `Prepared ${plan.strategies.length} code-aware strateg${plan.strategies.length === 1 ? "y" : "ies"} and a review-ready patch.`,
          type: "status",
          agent: "fix_agent",
        },
      ];
}

function buildGeneratingTimeline({
  mode,
  findingCount,
  finding,
}: {
  mode: "single" | "batch";
  findingCount: number;
  finding?: Finding | null;
}): TaskLine[] {
  const target = finding?.file ?? "the selected finding";
  return [
    {
      id: "explain",
      title: "Analyzing vulnerability",
      text:
        mode === "batch"
          ? `Explaining the shared exploit pattern across ${findingCount} validated finding${findingCount === 1 ? "" : "s"}.`
          : `Explaining the vulnerable execution path in ${target}.`,
      type: "status",
      agent: "explain_agent",
    },
    {
      id: "strategies",
      title: "Drafting strategies",
      text: "Drafting remediation strategies that preserve the existing behavior while removing the sink exposure.",
      type: "status",
      agent: "fix_agent",
    },
    {
      id: "patch-shape",
      title: "Preparing patch structure",
      text: "Preparing a review-ready patch shape and matching the diff to the traced lines.",
      type: "status",
      agent: "fix_agent",
    },
    {
      id: "validate",
      title: "Validating patch structure",
      text: "Validating the patch structure before it is shown for approval.",
      type: "status",
      agent: "validation_agent",
    },
    {
      id: "finalize",
      title: "Finalizing remediation plan",
      text: "Finalizing the remediation plan and rendering the code diff for review.",
      type: "status",
      agent: "fix_agent",
    },
  ];
}

function buildPlanErrorMessage(plan: RemediationPlan) {
  const reasons: string[] = [];
  if (!plan.strategies.length) {
    reasons.push("No remediation strategy was returned.");
  }
  if (!plan.patch) {
    reasons.push("No patch candidate was returned.");
  } else {
    if (!plan.patch.diff.trim()) {
      reasons.push("No patch diff was generated.");
    }
    if (!plan.patch.afterSnippet.trim()) {
      reasons.push("No updated code snippet was generated.");
    }
    for (const note of plan.patch.validationNotes.slice(0, 3)) {
      if (note && !reasons.includes(note)) {
        reasons.push(note);
      }
    }
  }
  if (!reasons.length) {
    reasons.push("The remediation plan is not review-ready yet.");
  }
  return reasons.join(" ");
}

function RenderedLine({
  text,
  type,
  streaming = false,
}: {
  text: string;
  type: "done" | "status" | "pending";
  streaming?: boolean;
}) {
  const className =
    type === "status"
      ? "text-[15px] font-medium text-status-progress"
      : type === "pending"
        ? "text-[15px] text-txt-tertiary"
        : "text-[15px] text-txt-secondary";

  return (
    <p className={className}>
      {streaming ? (
        <ShinyText
          text={text}
          className={className}
          color={type === "status" ? "#b5905a" : "#746b62"}
          shineColor="#eeeeee"
          speed={type === "status" ? 3.0 : 2.6}
          spread={90}
          disabled={type === "pending"}
        />
      ) : (
        text
      )}
      {streaming && <Cursor />}
    </p>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[20px] border bg-card/80 px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} />
        <p className="text-[11px] uppercase tracking-[0.16em]">{label}</p>
      </div>
      <p className="mt-2 text-sm font-medium text-txt-primary">{value}</p>
    </div>
  );
}

function Cursor() {
  return (
    <motion.span
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
      className="ml-0.5 inline-block text-txt-tertiary"
    >
      |
    </motion.span>
  );
}

function buildIndexedKey(prefix: string, value: string, index: number) {
  return `${prefix}-${index}-${value}`;
}
