import { motion } from "framer-motion";
import { useEffect, useState, type ComponentType } from "react";
import {
  CheckCircle2,
  ChevronRight,
  Cloud,
  FileCode2,
  Lock,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Finding, RemediationPlan } from "@/entities/finding/model/types";
import { buildPatchDecisionSummary } from "@/entities/finding/lib/decision-center";
import type { RemediationExecutionResult } from "@/shared/api/security";
import { Loader } from "@/shared/ui/Loader";
import { usePatchReview } from "../model/usePatchReview";
import { DiffViewer } from "./DiffViewer";

interface PatchReadyScreenProps {
  onApprove: (input: {
    strategyId: string | null;
    strategyLabel: string | null;
    file: string;
    beforeSnippet: string;
    afterSnippet: string;
    diff: string;
    fixType: "full_fix" | "partial_mitigation" | "temporary_guard" | "risky_workaround";
    summary: string;
    rationale: string;
    residualRisks: string[];
    manualEdit: boolean;
    mode: "single" | "batch";
  }) => Promise<RemediationExecutionResult | null>;
  onRollback: (checkpointId: string | null) => Promise<RemediationExecutionResult | null>;
  onReject: (strategyId: string | null) => Promise<RemediationExecutionResult | null>;
  onRetry: (input: { excludedStrategyIds: string[]; attemptedStrategyIds: string[] }) => Promise<RemediationPlan | null>;
  onViewResults: () => void;
  onOpenPolicyCenter: () => void;
  finding?: Finding | null;
  findings?: Finding[];
  mode?: "single" | "batch";
  plan?: RemediationPlan | null;
}

export function PatchReadyScreen({ onApprove, onRollback, onReject, onRetry, onViewResults, onOpenPolicyCenter, finding, findings = [], mode = "single", plan }: PatchReadyScreenProps) {
  const {
    draftCode,
    isEditing,
    isReviewDetailsVisible,
    pendingAction,
    reviewState,
    selectedSuggestion,
    selectedVariant,
    setDraftCode,
    setIsEditing,
    setIsReviewDetailsVisible,
    setPendingAction,
    setReviewState,
    setSelectedVariant,
  } = usePatchReview(plan);
  const [lastExecution, setLastExecution] = useState<RemediationExecutionResult | null>(null);

  useEffect(() => {
    setLastExecution(null);
  }, [plan]);

  const findingCount = findings.length || (finding ? 1 : 0);
  const isBatch = mode === "batch";
  const patch = plan?.patch;
  const recommendedSuggestion =
    plan?.strategies.find((suggestion) => suggestion.id === plan?.recommendedStrategyId)
    ?? plan?.strategies.find((suggestion) => suggestion.recommended)
    ?? null;
  const activeDiff = isEditing
    ? buildUnifiedDiffFromSnippets(patch?.beforeSnippet ?? "", draftCode)
    : (selectedSuggestion?.diff || patch?.diff || "");
  const additions = countDiffLines(activeDiff, "+");
  const removals = countDiffLines(activeDiff, "-");
  const confidence = selectedSuggestion?.confidence ?? 0;
  const showConfidence = Boolean(
    selectedSuggestion
    && confidence > 0
    && selectedSuggestion.policyCompliant
    && (plan?.score?.confidence ?? 0) > 0,
  );
  const activeFixType = selectedSuggestion?.fixType ?? patch?.fixType ?? "partial_mitigation";
  const activeResidualRisks = selectedSuggestion?.residualRisks?.length ? selectedSuggestion.residualRisks : (patch?.residualRisks ?? []);
  const activeRationale = selectedSuggestion?.selectionReason || patch?.rationale || selectedSuggestion?.rationale || "";
  const activeValidationNotes = [
    ...(patch?.validationNotes ?? []),
    ...((selectedSuggestion?.policyViolations ?? []).filter(Boolean)),
  ];
  const patchHasDiff = Boolean(activeDiff.trim());
  const patchHasAfter = Boolean((draftCode || "").trim());
  const patchIsValid = Boolean(patch) && patchHasAfter && patchHasDiff;
  const hasCompliantStrategy = Boolean(plan?.strategies.some((suggestion) => suggestion.policyCompliant));
  const selectedStrategyBlocked = Boolean(
    selectedSuggestion
    && !selectedSuggestion.policyCompliant
    && hasCompliantStrategy
    && !isEditing,
  );
  const canApprove = patchIsValid && !selectedStrategyBlocked;
  const selectedStrategyMessage = getSelectedStrategyMessage({
    isEditing,
    selectedSuggestion,
    recommendedSuggestion,
    hasCompliantStrategy,
  });
  const patchDecision = buildPatchDecisionSummary({
    finding,
    patch,
    selectedStrategy: selectedSuggestion,
    mode,
  });
  const approvalAudit = patchDecision.approvalAuditSummary;

  const handleApprove = async () => {
    if (!patch || !canApprove) return;
    setPendingAction("approve");
    setReviewState("applying");
    try {
      const result = await onApprove({
        strategyId: selectedSuggestion?.id ?? plan?.recommendedStrategyId ?? null,
        strategyLabel: selectedSuggestion?.label ?? null,
        file: patch.file,
        beforeSnippet: patch.beforeSnippet,
        afterSnippet: draftCode,
        diff: activeDiff,
        fixType: activeFixType,
        summary: patch.summary,
        rationale: patch.rationale || activeRationale,
        residualRisks: activeResidualRisks,
        manualEdit: isEditing,
        mode,
      });
      setLastExecution(result);
      setReviewState(result?.action.status === "applied" ? "applied" : "idle");
    } catch {
      setReviewState("idle");
    } finally {
      setPendingAction(null);
    }
  };

  const handleReject = async () => {
    setPendingAction("reject");
    const result = await onReject(selectedSuggestion?.id ?? plan?.recommendedStrategyId ?? null);
    setPendingAction(null);
    if (result?.action.status === "rejected") {
      setReviewState("rejected");
    }
  };

  const handleRollback = async () => {
    const checkpointId = lastExecution?.action.checkpointId ?? null;
    if (!checkpointId) return;
    setPendingAction("rollback");
    setReviewState("rolling_back");
    const result = await onRollback(checkpointId);
    setPendingAction(null);
    setLastExecution(result);
    setReviewState(result?.action.status === "rolled_back" ? "rolled_back" : "applied");
  };

  const handleRetry = async () => {
    setPendingAction("retry");
    setReviewState("retrying");
    await onRetry({
      excludedStrategyIds: [selectedSuggestion?.id ?? plan?.recommendedStrategyId ?? ""].filter(Boolean),
      attemptedStrategyIds: finding?.attemptedStrategyIds ?? [],
    });
    setPendingAction(null);
    setReviewState("idle");
    setIsEditing(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface"
    >
      <div className="mx-auto w-full max-w-[1180px] px-8 py-8">
        <div className="min-w-0">
          <div className="mb-6 flex items-start gap-3 text-left text-txt-primary">
            <div className="pt-0.5 text-txt-primary">
              <Cloud size={26} strokeWidth={2} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-medium tracking-[-0.02em] text-txt-primary">
                {isBatch
                  ? `[Security Analyst] Batch remediation review: ${findingCount} validated finding${findingCount === 1 ? "" : "s"}`
                  : `[Security Analyst] Fix ${finding?.category.toLowerCase() ?? "security_issue"}: ${patch?.file ?? finding?.file ?? "Unknown file"}`}
              </p>
              <p className="mt-1 text-sm text-txt-tertiary">
                {isBatch
                  ? "Review the consolidated remediation plan before applying the patch to the selected workspace."
                  : (patch?.file ?? finding?.file ?? "Unknown file")}
              </p>
            </div>
          </div>

          <section className="mb-6">
            <h3 className="mb-3 text-sm font-semibold text-txt-primary">Patch review</h3>
            <p className="mb-4 text-sm leading-relaxed text-txt-secondary">
              {plan?.reviewSummary ?? "Review the generated remediation patch and apply it to the selected workspace when ready."}
            </p>
          </section>

          <div
            className="mb-6 rounded-[22px] border bg-[#f7f7f7] px-5 py-4"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-txt-primary">Decision flow</p>
              <span className="text-xs text-txt-tertiary">
                {reviewState === "applied" ? "Applied to workspace" : reviewState === "rejected" ? "Rejected" : "Awaiting review"}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <DecisionStep label="Inspect diff" active />
              <ChevronRight size={14} className="text-txt-tertiary" />
              <DecisionStep label="Choose strategy" active={Boolean(selectedSuggestion)} />
              <ChevronRight size={14} className="text-txt-tertiary" />
              <DecisionStep label="Apply to workspace" active={reviewState === "applying" || reviewState === "applied"} />
            </div>
            {selectedSuggestion ? (
              <p className="mt-4 text-[13px] leading-6 text-txt-secondary">
                Current choice: <span className="font-medium text-txt-primary">{selectedSuggestion.label}</span>{" "}
                using the <span className="font-medium text-txt-primary">{selectedSuggestion.kind}</span> strategy.
              </p>
            ) : null}
          </div>

          <div className="relative mb-6">
            <DiffViewer
              filePath={patch?.file ?? finding?.file ?? "Unknown file"}
              beforeCode={patch?.beforeSnippet ?? ""}
              afterCode={draftCode}
              unifiedDiff={activeDiff}
            />
            <div className="pointer-events-none absolute inset-y-0 -right-16 hidden items-center xl:flex">
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => setIsReviewDetailsVisible((current) => !current)}
                    className="pointer-events-auto flex h-28 w-11 flex-col items-center justify-center gap-2 rounded-[18px] border bg-card text-txt-secondary transition-colors hover:bg-secondary hover:text-txt-primary"
                    style={{ borderColor: "hsl(var(--border-soft))" }}
                    aria-label="Toggle review details"
                  >
                    {isReviewDetailsVisible ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
                    <span className="[writing-mode:vertical-rl] rotate-180 text-[11px] font-medium tracking-[0.14em]">
                      Review
                    </span>
                  </button>
                </TooltipTrigger>
                <TooltipContent
                  side="left"
                  className="rounded-xl border border-border-soft bg-surface px-3 py-1.5 text-xs text-txt-primary shadow-md"
                >
                  Toggle review details
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {!patchIsValid && (
            <div className="mb-6 rounded-[22px] border bg-[#fff7f5] px-5 py-4 text-sm text-status-critical" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
              The draft remediation does not contain a valid patch diff or updated code snippet yet. Generate another fix strategy before applying.
            </div>
          )}

          {selectedStrategyMessage && (
            <div className="mb-6 rounded-[22px] border bg-[#fff7f5] px-5 py-4 text-sm text-status-critical" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
              {selectedStrategyMessage}
            </div>
          )}

          {isReviewDetailsVisible && (
            <>
              <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetaCard label="Fix type" value={formatFixTypeLabel(activeFixType)} />
                <MetaCard label="Patch scope" value={patch?.file ?? finding?.file ?? "Unknown file"} />
                <MetaCard label="Lines changed" value={`+${additions} / -${removals}`} />
                <MetaCard label="Confidence" value={showConfidence ? `${confidence}%` : "Policy-validated"} />
              </div>

              {plan?.score ? (
                <div className="mb-6 rounded-[22px] border bg-card px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
                  <div className="mb-4 flex items-end justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">Remediation score</p>
                      <p className="mt-1 text-sm text-txt-secondary">A quality signal for the selected fix, not a replacement for human review.</p>
                    </div>
                    <div className="text-right">
                      <p className="text-4xl font-semibold tracking-[-0.03em] text-txt-primary">{plan.score.total}</p>
                      <p className="text-sm text-txt-tertiary">/100</p>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                    <ScoreCard label="Strategy" value={plan.score.strategyQuality} />
                    <ScoreCard label="Completeness" value={plan.score.fixCompleteness} />
                    <ScoreCard label="Sink alignment" value={plan.score.sinkAlignment} />
                    <ScoreCard label="Residual risk" value={plan.score.residualRisk} />
                    <ScoreCard label="Confidence" value={plan.score.confidence} />
                  </div>
                  {plan.score.rationale.length ? (
                    <div className="mt-4 space-y-2">
                      {plan.score.rationale.map((entry, index) => (
                        <p key={buildIndexedKey("score-rationale", entry, index)} className="text-sm leading-6 text-txt-secondary">{entry}</p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <p className="mb-6 text-sm text-txt-secondary">{patch?.summary ?? "A patch is ready for your review."}</p>

              <div className="mb-6 grid gap-3 md:grid-cols-2">
                <DecisionInsightCard
                  label="Write scope"
                  value={lastExecution?.action.writeScope || `Write scope is limited to ${patch?.file ?? finding?.file ?? "the selected file"} within the selected project.`}
                />
                <DecisionInsightCard
                  label="Network policy"
                  value={lastExecution?.action.networkPolicy || "Patch apply and rollback do not call external services. Network access is used only during AI analysis."}
                />
              </div>

              <div className="mb-6 rounded-[22px] border bg-card px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-txt-primary">Decision center</p>
                  <span className="text-xs text-txt-tertiary">Patch approval guidance</span>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <DecisionInsightCard
                    label={`Risk score ${patchDecision.riskScore}/100`}
                    value={patchDecision.riskLabel}
                  />
                  <DecisionInsightCard
                    label="Decision status"
                    value={patchDecision.decisionStatus}
                  />
                  <DecisionInsightCard
                    label="Approval state"
                    value={patchDecision.approvalState}
                  />
                  <DecisionInsightCard
                    label="Apply readiness"
                    value={patchDecision.applyReadiness}
                  />
                  <DecisionInsightCard
                    label="Escalation"
                    value={patchDecision.escalationState}
                  />
                  <DecisionInsightCard
                    label="Stop state"
                    value={patchDecision.stopState}
                  />
                  <DecisionInsightCard
                    label="Policy outcome"
                    value={patchDecision.policyOutcome}
                  />
                  <DecisionInsightCard
                    label="Recommended action"
                    value={patchDecision.recommendedAction}
                  />
                  <DecisionInsightCard
                    label="Approval path"
                    value={patchDecision.approvalPath}
                  />
                </div>
                <div className="mt-3">
                  <DecisionInsightCard
                    label="Rollout guidance"
                    value={patchDecision.rolloutGuidance}
                  />
                </div>
                <div className="mt-3">
                  <DecisionInsightCard
                    label={`Policy summary - ${patchDecision.policySummary.label}`}
                    value={patchDecision.policySummary.summary}
                  />
                </div>
                <div className="mt-3">
                  <DecisionInsightCard
                    label="Policy controls"
                    value={`Auto path: ${patchDecision.policySummary.autoPathState} · Human path: ${patchDecision.policySummary.humanPathState} · Next control: ${patchDecision.policySummary.nextControl}`}
                  />
                </div>
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={onOpenPolicyCenter}
                    className="rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary"
                    style={{ borderColor: "hsl(var(--border-primary))" }}
                  >
                    Open policy center
                  </button>
                </div>
                <div className="mt-3">
                  <DecisionInsightCard
                    label={`Approval audit - ${approvalAudit.label}`}
                    value={approvalAudit.summary}
                  />
                </div>
                <div className="mt-3">
                  <DecisionInsightCard
                    label="Approval note"
                    value={approvalAudit.note}
                  />
                </div>
              </div>
            </>
          )}

          {isReviewDetailsVisible && plan?.strategies?.length ? (
            <div className="mb-6 rounded-[22px] border bg-card px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-txt-primary">Fix strategies</p>
                <span className="text-xs text-txt-tertiary">Code-aware remediation options</span>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {plan.strategies.map((suggestion) => (
                  <button
                    key={suggestion.id}
                    onClick={() => setSelectedVariant(suggestion.id)}
                    className={`rounded-2xl border px-4 py-4 text-left transition-colors duration-200 ${
                      selectedVariant === suggestion.id ? "bg-[#f8f2e9]" : "bg-[#f7f7f7]"
                    }`}
                    style={{ borderColor: selectedVariant === suggestion.id ? "rgba(196, 161, 118, 0.42)" : "hsl(var(--border-soft))" }}
                  >
                    <p className="text-sm font-medium text-txt-primary">{suggestion.label}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                      {formatFixTypeLabel(suggestion.fixType)} | {suggestion.securityStrength} strength | {suggestion.regressionRisk} regression risk
                    </p>
                    <p className="mt-3 text-[13px] leading-6 text-txt-secondary">{suggestion.summary}</p>
                    <p className="mt-2 text-xs leading-5 text-txt-tertiary">{suggestion.recommended ? suggestion.selectionReason || suggestion.rationale : suggestion.nonSelectionReason || suggestion.rationale}</p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {isReviewDetailsVisible && (
            <div className="mb-6 rounded-[22px] border bg-card px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-txt-primary">Patch decision</p>
                <span className="text-xs text-txt-tertiary">Why this remediation was chosen</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <DecisionInsightCard
                  label="Selected because"
                  value={activeRationale || "This strategy was selected because it offers the strongest security improvement for the traced path."}
                />
                <DecisionInsightCard
                  label="Fix classification"
                  value={`${formatFixTypeLabel(activeFixType)}${patch?.manualReviewRequired ? " Ã‚Â· manual review required" : ""}`}
                />
                <DecisionInsightCard
                  label="Policy status"
                  value={selectedSuggestion?.policyCompliant === false ? "Below the enforced security policy. Manual review is required." : "Aligned with the enforced security policy for this vulnerability."}
                />
                <DecisionInsightCard
                  label="Selection status"
                  value={selectedSuggestion?.recommended ? "This is the recommended remediation strategy." : "This is an alternate strategy, not the recommended default."}
                />
                <DecisionInsightCard
                  label="Patch rationale"
                  value={patch?.rationale || activeRationale || "The patch is grounded in the traced sink and nearby code evidence."}
                />
              </div>
              {activeResidualRisks.length ? (
                <div className="mt-4 rounded-2xl border bg-[#fff7f5] px-4 py-4" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
                  <p className="text-sm font-semibold text-txt-primary">Residual risks</p>
                  <div className="mt-3 space-y-2">
                    {activeResidualRisks.map((entry, index) => (
                      <p key={buildIndexedKey("residual-risk", entry, index)} className="text-sm leading-6 text-txt-secondary">
                        {index + 1}. {entry}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
              {activeValidationNotes.length ? (
                <div className="mt-4 space-y-2.5">
                  <p className="text-sm font-semibold text-txt-primary">Validation notes</p>
                  {activeValidationNotes.map((entry, index) => (
                    <div key={buildIndexedKey("validation-note", entry, index)} className="flex gap-3 text-sm text-txt-secondary">
                      <span className="text-txt-tertiary">{String(index + 1).padStart(2, "0")}</span>
                      <span>{entry}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          <div className="mb-8 rounded-[22px] border bg-card px-5 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => void handleApprove()}
                disabled={!canApprove || reviewState === "applied" || pendingAction !== null}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-transform duration-200 active:scale-[0.985] disabled:opacity-60"
              >
                {pendingAction === "approve" && <Loader variant="spin" className="size-4 text-primary-foreground" />}
                {reviewState === "applying" ? "Applying patch..." : reviewState === "applied" ? "Applied to workspace" : "Approve fix"}
              </button>
              <button
                onClick={() => void handleReject()}
                disabled={reviewState === "applied" || pendingAction !== null}
                className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-transform duration-200 active:scale-[0.985] disabled:opacity-50"
                style={{ borderColor: "hsl(var(--border-primary))" }}
              >
                {pendingAction === "reject" ? (
                  <Loader variant="spin" className="size-4 text-status-critical" />
                ) : (
                  <XCircle size={15} className="text-status-critical" />
                )}
                {pendingAction === "reject" ? "Rejecting..." : "Reject"}
              </button>
              <button
                onClick={() => void handleRetry()}
                disabled={pendingAction !== null}
                className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-transform duration-200 active:scale-[0.985] disabled:opacity-50"
                style={{ borderColor: "hsl(var(--border-primary))" }}
              >
                {pendingAction === "retry" ? (
                  <Loader variant="spin" className="size-4 text-txt-secondary" />
                ) : (
                  <RotateCcw size={15} className="text-txt-secondary" />
                )}
                {pendingAction === "retry" ? "Generating another fix..." : "Try another fix"}
              </button>
              <button
                onClick={() => setIsEditing((current) => !current)}
                disabled={reviewState === "applied" || pendingAction !== null}
                className="rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-transform duration-200 active:scale-[0.985] disabled:opacity-50"
                style={{ borderColor: "hsl(var(--border-primary))" }}
              >
                {isEditing ? "Close editor" : "Edit manually"}
              </button>
              {reviewState === "applied" && lastExecution?.action.rollbackAvailable ? (
                <button
                  onClick={() => void handleRollback()}
                  disabled={pendingAction !== null}
                  className="inline-flex items-center gap-2 rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-transform duration-200 active:scale-[0.985] disabled:opacity-50"
                  style={{ borderColor: "hsl(var(--border-primary))" }}
                >
                  {pendingAction === "rollback" ? (
                    <Loader variant="spin" className="size-4 text-txt-secondary" />
                  ) : (
                    <RotateCcw size={15} className="text-txt-secondary" />
                  )}
                  {pendingAction === "rollback" ? "Rolling back..." : "Undo patch"}
                </button>
              ) : null}
              {(reviewState === "applied" || reviewState === "rolled_back") ? (
                <button
                  onClick={onViewResults}
                  className="rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary transition-transform duration-200 active:scale-[0.985]"
                  style={{ borderColor: "hsl(var(--border-primary))" }}
                >
                  View updated results
                </button>
              ) : null}
            </div>
          </div>

          {reviewState === "applied" ? (
            <div className="mb-6 flex items-start gap-3 rounded-2xl border bg-[#f6fbf4] px-4 py-3" style={{ borderColor: "rgba(132, 177, 118, 0.26)" }}>
              <CheckCircle2 size={18} className="mt-0.5 text-status-success" />
              <div>
                <p className="text-sm font-medium text-txt-primary">Patch applied to workspace</p>
                <p className="mt-1 text-sm text-txt-secondary">
                  The selected fix was written directly to the selected project file in this workspace. No Git or PR workflow was triggered.
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <ExecutionInsight
                    icon={ShieldCheck}
                    label="Verification"
                    value={
                      lastExecution?.action.verificationStatus === "verified"
                        ? "Deterministic verification passed for the patched file."
                        : "Follow-up verification still requires manual review."
                    }
                  />
                  <ExecutionInsight
                    icon={Lock}
                    label="Scope"
                    value={lastExecution?.action.writeScope || "The patch was limited to the selected project file."}
                  />
                </div>
                {lastExecution?.action.verificationNotes?.length ? (
                  <div className="mt-3 space-y-1.5">
                    {lastExecution.action.verificationNotes.map((entry, index) => (
                      <p key={buildIndexedKey("verification-note", entry, index)} className="text-sm leading-6 text-txt-secondary">{entry}</p>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {reviewState === "rolled_back" ? (
            <div className="mb-6 flex items-start gap-3 rounded-2xl border bg-[#fff7f5] px-4 py-3" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
              <RotateCcw size={18} className="mt-0.5 text-txt-secondary" />
              <div>
                <p className="text-sm font-medium text-txt-primary">Patch rolled back</p>
                <p className="mt-1 text-sm text-txt-secondary">The original file content and the previous saved scan state were restored.</p>
              </div>
            </div>
          ) : null}

          {reviewState === "rejected" ? (
            <div className="mb-6 flex items-start gap-3 rounded-2xl border bg-[#fff7f5] px-4 py-3" style={{ borderColor: "rgba(214, 131, 114, 0.22)" }}>
              <XCircle size={18} className="mt-0.5 text-status-critical" />
              <div>
                <p className="text-sm font-medium text-txt-primary">Patch rejected</p>
                <p className="mt-1 text-sm text-txt-secondary">No file changes were applied.</p>
              </div>
            </div>
          ) : null}
        </div>

        {isEditing && (
          <div className="mb-8 rounded-[22px] border bg-card p-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
            <div className="mb-3">
              <h4 className="text-sm font-semibold text-txt-primary">Manual edit draft</h4>
              <p className="mt-1 text-sm text-txt-secondary">Adjust the proposed patch before applying it to the selected workspace.</p>
            </div>
            <Textarea
              value={draftCode}
              onChange={(event) => setDraftCode(event.target.value)}
              className="min-h-[220px] rounded-2xl border bg-surface-code font-mono text-[13px] leading-6 text-txt-primary focus-visible:ring-accent/20"
              style={{ borderColor: "hsl(var(--border-soft))" }}
            />
          </div>
        )}

        <div className="flex items-center gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          <motion.span
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center rounded-lg border bg-card px-3 py-1.5 text-xs font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Diffs <span className="ml-1.5 text-status-success">+{additions}</span> <span className="ml-1 text-status-critical">-{removals}</span>
          </motion.span>
          <p className="text-sm text-txt-tertiary">
            {reviewState === "applied"
              ? "Patch written to the workspace and session state refreshed"
              : reviewState === "rolled_back"
                ? "Rollback restored the original file and session state"
                : isEditing
                  ? "Manual edits are reflected in the live diff preview"
                  : "Review the patch carefully before applying it"}
          </p>
        </div>
      </div>
    </motion.div>
  );
}

function getSelectedStrategyMessage({
  isEditing,
  selectedSuggestion,
  recommendedSuggestion,
  hasCompliantStrategy,
}: {
  isEditing: boolean;
  selectedSuggestion: RemediationPlan["strategies"][number] | null;
  recommendedSuggestion: RemediationPlan["strategies"][number] | null;
  hasCompliantStrategy: boolean;
}) {
  if (isEditing || !selectedSuggestion || selectedSuggestion.policyCompliant) {
    return null;
  }
  if (
    hasCompliantStrategy
    && recommendedSuggestion
    && recommendedSuggestion.policyCompliant
    && recommendedSuggestion.id !== selectedSuggestion.id
  ) {
    return "The selected strategy is below the enforced security policy for this vulnerability. Switch to the recommended compliant strategy or edit the patch manually before approval.";
  }
  return "The generated remediation plan does not currently contain a policy-compliant strategy for this vulnerability. You can still apply this patch in the selected workspace, but it should be treated as a risky workaround and reviewed carefully.";
}

function buildIndexedKey(prefix: string, value: string, index: number) {
  return `${prefix}-${index}-${value}`;
}

function countDiffLines(diff: string, prefix: "+" | "-") {
  return diff
    .split("\n")
    .filter((line) => line.startsWith(prefix) && !line.startsWith(prefix.repeat(3)))
    .length;
}

function buildUnifiedDiffFromSnippets(before: string, after: string) {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const max = Math.max(beforeLines.length, afterLines.length);
  const rows = ["@@ remediation diff @@"];

  for (let index = 0; index < max; index += 1) {
    const left = beforeLines[index];
    const right = afterLines[index];
    if (left === right && left !== undefined) {
      rows.push(` ${left}`);
      continue;
    }
    if (left !== undefined) {
      rows.push(`-${left}`);
    }
    if (right !== undefined) {
      rows.push(`+${right}`);
    }
  }

  return rows.join("\n");
}

function formatFixTypeLabel(fixType?: string) {
  switch (fixType) {
    case "full_fix":
      return "full fix";
    case "temporary_guard":
      return "temporary guard";
    case "risky_workaround":
      return "risky workaround";
    default:
      return "partial mitigation";
  }
}

function DecisionStep({ label, active }: { label: string; active?: boolean }) {
  return (
    <div
      className={`inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-medium ${
        active ? "bg-card text-txt-primary" : "text-txt-tertiary"
      }`}
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      {label}
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <FileCode2 size={14} />
        <p className="text-[11px] uppercase tracking-[0.16em]">{label}</p>
      </div>
      <p className="mt-1 text-sm font-medium text-txt-primary">{value}</p>
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{value}</p>
      <div className="mt-2 h-2 rounded-full bg-[rgba(207,196,180,0.42)]">
        <div
          className="h-2 rounded-full bg-primary transition-all duration-300"
          style={{ width: `${Math.max(4, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

function DecisionInsightCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-sm leading-6 text-txt-secondary">{value}</p>
    </div>
  );
}

function ExecutionInsight({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={14} />
        <p className="text-[11px] uppercase tracking-[0.16em]">{label}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-txt-secondary">{value}</p>
    </div>
  );
}

