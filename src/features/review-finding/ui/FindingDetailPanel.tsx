import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, CircleAlert, FlaskConical, Gauge, ShieldCheck, ShieldX, Zap } from "lucide-react";
import { ShowMore } from "@/components/ui/show-more";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Finding, RemediationExplanation } from "@/entities/finding/model/types";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { getRemediationStatusLabel, getRemediationStatusTone } from "@/entities/finding/lib/remediation-status";
import { explainFinding } from "@/shared/api/security";
import { CodeBlock } from "@/shared/ui/CodeBlock";
import { Loader } from "@/shared/ui/Loader";
import { toast } from "@/components/ui/sonner";
import { DataFlowGraph } from "./DataFlowGraph";

interface Props {
  finding: Finding;
  sessionId?: string | null;
  onDismiss: () => void;
  onOpenDecisionCenter: () => void;
  onSuggestFix: () => void;
}

export function FindingDetailPanel({ finding, sessionId, onDismiss, onOpenDecisionCenter, onSuggestFix }: Props) {
  const [loading, setLoading] = useState(false);
  const [showAttackerStory, setShowAttackerStory] = useState(false);
  const [showFullAttackerStory, setShowFullAttackerStory] = useState(false);
  const [showAttackSimulation, setShowAttackSimulation] = useState(false);
  const [explanation, setExplanation] = useState<RemediationExplanation | null>(null);
  const [isExplanationLoading, setIsExplanationLoading] = useState(false);

  const attackerStory = useMemo(() => explanation?.attackSteps ?? [], [explanation?.attackSteps]);
  const remediationStatusTone = getRemediationStatusTone(finding.remediationStatus);
  const decisionSummary = useMemo(() => buildFindingDecisionSummary(finding), [finding]);

  const handleSuggestFix = () => {
    setLoading(true);
    setTimeout(() => {
      onSuggestFix();
    }, 500);
  };

  const handleToggleAttackerStory = async () => {
    if (showAttackerStory) {
      setShowAttackerStory(false);
      setShowFullAttackerStory(false);
      return;
    }

    setShowAttackerStory(true);
    if (explanation || !sessionId || isExplanationLoading) {
      return;
    }

    setIsExplanationLoading(true);
    try {
      const detail = await explainFinding({
        sessionId,
        findingId: finding.id,
      });
      setExplanation(detail);
    } catch (error) {
      console.error("[Khwarizm] Failed to explain finding", error);
      toast.error(error instanceof Error ? error.message : "Unable to explain this finding.");
    } finally {
      setIsExplanationLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface"
    >
      <div className="mx-auto max-w-3xl px-8 py-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-txt-primary">{finding.title}</h2>
            <p className="mt-2 text-sm font-mono text-txt-tertiary">
              {finding.file}:{finding.line}{finding.lineEnd > finding.line ? `-${finding.lineEnd}` : ""}
            </p>
            <div className="mt-3">
              <span
                className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] ${
                  remediationStatusTone === "success"
                    ? "bg-[#eef8ef] text-status-success"
                    : remediationStatusTone === "progress"
                      ? "bg-[#f4efe6] text-status-progress"
                      : remediationStatusTone === "warning"
                        ? "bg-[#fff6ef] text-status-high"
                        : remediationStatusTone === "muted"
                          ? "bg-[#f4efe7] text-txt-secondary"
                          : "bg-[#f6f1ea] text-txt-secondary"
                }`}
              >
                {getRemediationStatusLabel(finding.remediationStatus)}
              </span>
            </div>
          </div>
          <button
            onClick={() => void handleToggleAttackerStory()}
            className="rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            {isExplanationLoading ? (
              <span className="inline-flex items-center gap-2">
                <Loader variant="spin" className="size-4 text-txt-primary" />
                Generating...
              </span>
            ) : (
              "Explain like attacker"
            )}
          </button>
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
          <motion.div
            className="rounded-[20px] border bg-card px-4 py-4 transition-colors duration-200 hover:bg-[#fcf8f2]"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Gauge size={16} className="text-txt-secondary" />
                <p className="text-sm font-medium text-txt-primary">AI confidence</p>
              </div>
              <span className="text-sm font-semibold text-txt-primary">{finding.confidence}%</span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#ece3d6]">
              <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${finding.confidence}%` }} />
            </div>
          </motion.div>

          <motion.button
            whileTap={{ scale: 0.985 }}
            onClick={() => setShowAttackSimulation((current) => !current)}
            className="rounded-[20px] border bg-card px-4 py-4 text-left transition-colors hover:bg-[#fbf7f1]"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="flex items-center gap-2 text-txt-primary">
              <FlaskConical size={16} className="text-status-progress" />
              <p className="text-sm font-medium">Simulate attack</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-txt-secondary">
              Replay the input, execution path, and expected impact from the real analysis result.
            </p>
          </motion.button>
        </div>

        {showAttackerStory && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-[22px] border bg-[#fff9f6] px-5 py-4"
            style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}
          >
            <p className="mb-3 text-sm font-semibold text-txt-primary">Attacker story</p>
            {isExplanationLoading && (
              <LoadingNarrative />
            )}
            {!isExplanationLoading && attackerStory.length > 0 && (
              <div className="space-y-2.5">
                {(showFullAttackerStory ? attackerStory : attackerStory.slice(0, 2)).map((step, index) => (
                  <div key={step} className="min-w-0 flex gap-3 text-sm text-txt-secondary">
                    <span className="shrink-0 font-medium text-status-critical">{index + 1}.</span>
                    <span className="min-w-0 break-words [overflow-wrap:anywhere]">{step}</span>
                  </div>
                ))}
              </div>
            )}
            {!isExplanationLoading && attackerStory.length === 0 && (
              <p className="text-sm text-txt-secondary">No attacker narrative is available for this finding.</p>
            )}
            {!isExplanationLoading && attackerStory.length > 2 && (
              <ShowMore className="mt-4" onClick={() => setShowFullAttackerStory((current) => !current)}>
                {({ isSelected }) => (
                  <>
                    Show {isSelected ? "less" : "more"}
                    <ChevronDown
                      className={isSelected ? "rotate-180 transition-transform duration-200" : "transition-transform duration-200"}
                      size={16}
                    />
                  </>
                )}
              </ShowMore>
            )}
          </motion.div>
        )}

        {showAttackSimulation && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 grid gap-3 md:grid-cols-3">
            <SimulationCard
              label="Input"
              value={isExplanationLoading ? "Generating attacker input simulation..." : explanation?.requestExample || "No generated attacker input available yet."}
              tone="neutral"
            />
            <SimulationCard
              label="Execution"
              value={isExplanationLoading ? "Tracing the exploit execution path..." : explanation?.executionPath || "No generated execution path available yet."}
              tone="warning"
            />
            <SimulationCard
              label="Result"
              value={isExplanationLoading ? "Estimating exploit impact..." : explanation?.exploitScenario || "No generated exploit impact is available yet."}
              tone="danger"
            />
          </motion.div>
        )}

        <Tabs defaultValue="summary">
          <TabsList className="mb-6 h-auto rounded-2xl bg-[#f4ede4] p-1">
            <TabsTrigger value="summary" className="rounded-xl px-4 py-2 text-sm">Summary</TabsTrigger>
            <TabsTrigger value="decision" className="rounded-xl px-4 py-2 text-sm">Decision</TabsTrigger>
            <TabsTrigger value="flow" className="rounded-xl px-4 py-2 text-sm">Data flow</TabsTrigger>
            <TabsTrigger value="explanation" className="rounded-xl px-4 py-2 text-sm">Explanation</TabsTrigger>
            <TabsTrigger value="fix" className="rounded-xl px-4 py-2 text-sm">Fix</TabsTrigger>
          </TabsList>

          <TabsContent value="summary" className="mt-0">
            <div className="space-y-4">
              <Panel>
                <div className="grid gap-3 md:grid-cols-[1.15fr_0.85fr]">
                  <div>
                    <p className="text-[13px] leading-6 text-txt-secondary">{finding.summary}</p>
                  </div>
                  <div className="grid gap-2">
                    <StoryMiniCard icon={CircleAlert} label="Why it matters" value={finding.impact} tone="danger" />
                    <StoryMiniCard icon={ShieldX} label="Root cause" value={finding.explanation} />
                  </div>
                </div>
                <div className="mt-3 grid gap-2.5 md:grid-cols-2">
                  <InfoCard label="Severity" value={finding.severity} />
                  <InfoCard label="Impact" value={finding.impact} />
                  <InfoCard label="Category" value={finding.category} />
                  <InfoCard label="Location" value={`${finding.file}:${finding.line}${finding.lineEnd > finding.line ? `-${finding.lineEnd}` : ""}`} mono />
                </div>
              </Panel>

              <Panel>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">Risk story</p>
                  <span className="text-xs text-txt-tertiary">3-step summary</span>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <StoryStep step="1" title="Entry point" text={finding.attackSimulation.input} />
                  <StoryStep step="2" title="Unsafe execution" text={finding.attackSimulation.execution} tone="warning" />
                  <StoryStep step="3" title="Impact" text={finding.attackSimulation.result} tone="danger" />
                </div>
              </Panel>
            </div>
          </TabsContent>

          <TabsContent value="decision" className="mt-0">
            <div className="space-y-4">
              <Panel>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">Decision center</p>
                  <span className="text-xs text-txt-tertiary">Recommended path forward</span>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <StoryMiniCard icon={ShieldCheck} label={decisionSummary.validationLabel} value={decisionSummary.validationNote} />
                  <StoryMiniCard icon={Gauge} label={`Risk score ${decisionSummary.riskScore}/100`} value={decisionSummary.riskLabel} tone={decisionSummary.riskScore >= 85 ? "danger" : "warning"} />
                  <StoryMiniCard icon={Zap} label="Recommended action" value={decisionSummary.recommendedAction} tone="warning" />
                  <StoryMiniCard icon={ShieldX} label="Approval path" value={decisionSummary.approvalPath} tone="danger" />
                </div>
              </Panel>

              <Panel>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">Why Khwarizm recommends a fix</p>
                  <span className="text-xs text-txt-tertiary">Security-specific guidance</span>
                </div>
                <div className="space-y-3">
                  <ExplainRow label="Fix strategy" value={decisionSummary.fixRecommendation} />
                  {decisionSummary.riskFactors.map((factor, index) => (
                    <ExplainRow key={`${factor}-${index}`} label={`Factor ${index + 1}`} value={factor} tone={index === 2 ? "danger" : "default"} />
                  ))}
                </div>
              </Panel>
            </div>
          </TabsContent>

          <TabsContent value="flow" className="mt-0">
            <div className="space-y-4">
              <DataFlowGraph steps={explanation?.attackSteps} />
              <Panel>
                <div className="grid gap-3 md:grid-cols-3">
                  <StoryMiniCard icon={CircleAlert} label="Input" value={explanation?.entryPoint || "Generate the attacker explanation to inspect the real input path."} />
                  <StoryMiniCard icon={Zap} label="Propagation" value={explanation?.executionPath || "Generate the attacker explanation to inspect the propagation path."} tone="warning" />
                  <StoryMiniCard icon={ShieldX} label="Impact" value={explanation?.impact || "Generate the attacker explanation to inspect the resulting impact."} tone="danger" />
                </div>
              </Panel>
            </div>
          </TabsContent>

          <TabsContent value="explanation" className="mt-0">
            <div className="space-y-4">
              <Panel>
                <p className="text-sm leading-7 text-txt-secondary">
                  {explanation?.exploitScenario || "Generate the attacker explanation to view the code-aware exploit narrative for this finding."}
                </p>
              </Panel>

              <Panel>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">How Khwarizm explains it</p>
                  <span className="text-xs text-txt-tertiary">Cause to effect</span>
                </div>
                <div className="space-y-3">
                  <ExplainRow label="Cause" value={explanation?.summary || "Generate the attacker explanation to inspect the root cause."} />
                  <ExplainRow label="Boundary" value={explanation?.executionPath || "Generate the attacker explanation to inspect the trust-boundary crossing."} />
                  <ExplainRow label="Outcome" value={explanation?.impact || "Generate the attacker explanation to inspect the exploit outcome."} tone="danger" />
                  {explanation?.payloadExample ? <ExplainRow label="Payload" value={explanation.payloadExample} /> : null}
                </div>
              </Panel>
            </div>
          </TabsContent>

          <TabsContent value="fix" className="mt-0">
            <div className="space-y-4">
              <Panel>
                <p className="mb-4 text-sm leading-7 text-txt-secondary">
                  Generate a code-aware remediation plan from the real path and evidence to review concrete fix strategies and an actual patch diff.
                </p>
                <div className="grid gap-3 md:grid-cols-3">
                  <FixModeCard icon={Gauge} title="Refactor patch" description="Generate a structural fix tied to the traced source-to-sink path." />
                  <FixModeCard icon={ShieldCheck} title="Guard patch" description="Add validation or trust-boundary checks before the risky execution step." />
                  <FixModeCard icon={Zap} title="Sanitization patch" description="Apply the smallest effective sanitization or parameterization fix for this flow." />
                </div>
              </Panel>

              <Panel>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">Audit log</p>
                  <span className="text-xs text-txt-tertiary">Real analysis trace</span>
                </div>
                <div className="space-y-2.5">
                  {finding.auditLog.map((entry, index) => (
                    <div key={entry} className="flex gap-3 text-sm text-txt-secondary">
                      <span className="text-txt-tertiary">{String(index + 1).padStart(2, "0")}</span>
                      <span>{entry}</span>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel>
                <p className="mb-4 text-sm leading-7 text-txt-secondary">
                  Evidence captured from the real analysis result.
                </p>
                <CodeBlock
                  code={finding.evidence || "// No code evidence was returned for this finding."}
                  annotations={[
                    {
                      lineStart: finding.line,
                      lineEnd: finding.lineEnd,
                      tone: finding.severity === "critical" || finding.severity === "high" ? "red" : "yellow",
                    },
                  ]}
                />
              </Panel>
            </div>
          </TabsContent>
        </Tabs>

        <div className="mt-8 flex items-center justify-end gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          <motion.button
            whileTap={{ scale: 0.985 }}
            onClick={onOpenDecisionCenter}
            disabled={loading}
            className="rounded-xl border bg-card px-5 py-2 text-sm font-medium text-txt-primary disabled:opacity-50"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Decision center
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.985 }}
            onClick={onDismiss}
            disabled={loading}
            className="rounded-xl border bg-card px-5 py-2 text-sm font-medium text-txt-primary disabled:opacity-50"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Dismiss
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.985 }}
            onClick={handleSuggestFix}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-medium text-primary-foreground disabled:opacity-80"
          >
            {loading && <Loader variant="spin" className="size-4 text-primary-foreground" />}
            {loading ? "Loading..." : "Suggest fix"}
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
}

function LoadingNarrative() {
  return (
    <div className="mb-3 rounded-2xl border bg-card/60 px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-sm text-txt-secondary">
        <Loader variant="spin" className="size-4 text-txt-primary" />
        <span>Generating a code-aware attacker narrative from the traced path...</span>
      </div>
    </div>
  );
}

function SimulationCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "neutral" | "warning" | "danger";
}) {
  const toneClass =
    tone === "danger"
      ? "bg-[#fff7f5]"
      : tone === "warning"
        ? "bg-[#fbf7f1]"
        : "bg-card";

  return (
    <div className={`min-w-0 rounded-[20px] border px-4 py-4 transition-colors duration-200 ${toneClass}`} style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-txt-tertiary">{label}</p>
      <p className="mt-3 min-w-0 break-words text-[13px] leading-6 text-txt-secondary [overflow-wrap:anywhere]">{value}</p>
    </div>
  );
}

function StoryMiniCard({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
  tone?: "default" | "warning" | "danger";
}) {
  return (
    <div className={`rounded-2xl border px-4 py-3 ${tone === "danger" ? "bg-[#fff7f5]" : "bg-[#fbf7f1]"}`} style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={14} className={tone === "danger" ? "text-status-critical" : tone === "warning" ? "text-status-high" : "text-txt-secondary"} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-[13px] leading-6 text-txt-primary [overflow-wrap:anywhere]">{value}</p>
    </div>
  );
}

function StoryStep({
  step,
  title,
  text,
  tone = "default",
}: {
  step: string;
  title: string;
  text: string;
  tone?: "default" | "warning" | "danger";
}) {
  return (
    <div className={`min-w-0 rounded-2xl border px-4 py-4 ${tone === "danger" ? "bg-[#fff7f5]" : tone === "warning" ? "bg-[#fbf7f1]" : "bg-card"}`} style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#f6f1ea] text-[11px] font-semibold text-txt-primary">
          {step}
        </div>
        <p className="text-sm font-medium text-txt-primary">{title}</p>
      </div>
      <p className="mt-3 min-w-0 break-words text-[13px] leading-6 text-txt-secondary [overflow-wrap:anywhere]">{text}</p>
    </div>
  );
}

function ExplainRow({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "danger";
}) {
  return (
    <div className="grid min-w-0 gap-2 rounded-2xl border bg-[#fbf7f1] px-4 py-3 md:grid-cols-[110px_minmax(0,1fr)]" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className={`min-w-0 break-words text-[13px] leading-6 [overflow-wrap:anywhere] ${tone === "danger" ? "text-status-critical" : "text-txt-secondary"}`}>{value}</p>
    </div>
  );
}

function SuggestionIcon({ profile }: { profile: "safe" | "fast" | "recommended" }) {
  if (profile === "safe") return <ShieldCheck size={15} className="text-status-success" />;
  if (profile === "fast") return <Zap size={15} className="text-status-high" />;
  return <Gauge size={15} className="text-status-progress" />;
}

function FixModeCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="min-w-0 rounded-2xl border bg-[#fbf7f1] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-card/80">
          <Icon size={15} className="text-txt-secondary" />
        </div>
        <p className="text-sm font-medium text-txt-primary">{title}</p>
      </div>
      <p className="mt-3 min-w-0 break-words text-[13px] leading-6 text-txt-secondary [overflow-wrap:anywhere]">{description}</p>
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-[20px] border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      {children}
    </div>
  );
}

function InfoCard({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-2xl border bg-[#fbf7f1] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-txt-tertiary">{label}</p>
      <p className={`mt-1.5 min-w-0 max-w-full overflow-hidden break-words text-[13px] leading-6 text-txt-primary ${mono ? "font-mono [overflow-wrap:anywhere]" : "[overflow-wrap:anywhere]"}`}>
        {value}
      </p>
    </div>
  );
}
