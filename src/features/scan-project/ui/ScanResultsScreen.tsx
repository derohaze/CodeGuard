import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import type { Finding } from "@/entities/finding/model/types";
import { buildApprovalQueue } from "@/entities/finding/lib/approval-queue";
import { orderFindingsByDecisionPriority } from "@/entities/finding/lib/finding-triage";
import { getRemediationStatusLabel, getRemediationStatusTone } from "@/entities/finding/lib/remediation-status";
import type { SessionAnnotation } from "@/entities/session/model/types";
import { SeverityBadge } from "@/entities/finding/ui/SeverityBadge";
import type { ScanSessionDetail } from "@/shared/api/security";
import { toAnalystCopy } from "@/shared/lib/analyst-copy";

interface Props {
  session: ScanSessionDetail | null;
  onSelectFinding: (finding: Finding) => void;
  onOpenApprovalQueue: () => void;
  onOpenOperationsConsole: () => void;
  onOpenAuditTrail: () => void;
}

export function ScanResultsScreen({ session, onSelectFinding, onOpenApprovalQueue, onOpenOperationsConsole, onOpenAuditTrail }: Props) {
  if (!session) return null;
  const safeVerdict = session.verdict === "safe";
  const hasFindings = session.findings.length > 0;
  const hasCoverageGap = session.session.coveragePercent < 100;
  const hasSecurityScore = typeof session.session.securityScore === "number";
  const excludedFiles = getExcludedFiles(session.session.coverageSnapshot);
  const orderedValidatedFindings = orderFindingsByDecisionPriority(session.findings);
  const filteredCandidateFindings = dedupeCandidateFindings(orderedValidatedFindings, session.candidateFindings);
  const hasCandidateFindings = filteredCandidateFindings.length > 0;
  const approvalQueue = buildApprovalQueue(orderedValidatedFindings);
  const approvalQueuedFindingIds = new Set(approvalQueue.map((item) => item.findingId));
  const surfacedValidatedFindings = orderedValidatedFindings.filter((finding) => !approvalQueuedFindingIds.has(finding.id));
  const activeFindingCounts = countSeverities(surfacedValidatedFindings);
  const activeValidatedCount = surfacedValidatedFindings.length;
  void onOpenApprovalQueue;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="hide-scrollbar flex-1 overflow-y-auto bg-surface px-6 py-6"
    >
      <div className="mx-auto max-w-5xl space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex items-center justify-between rounded-xl border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div>
            <p className="text-sm font-semibold text-txt-primary">{session.session.repo}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
              {session.session.scanMode === "deep" ? "Deep analysis" : "Fast analysis"} | {session.session.time}
            </p>
          </div>
          <div className="flex items-center gap-2 text-txt-secondary">
            <CheckCircle2 size={15} className={safeVerdict ? "text-status-success" : "text-txt-secondary"} />
            <span className="text-sm font-medium text-txt-primary">{safeVerdict ? "Reviewed" : "Completed"}</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className={`rounded-xl border px-5 py-4 ${safeVerdict ? "bg-[#f7fbf7]" : "bg-card"}`}
          style={{ borderColor: safeVerdict ? "rgba(94, 155, 110, 0.22)" : "hsl(var(--border-soft))" }}
        >
          <p className={`text-sm font-medium ${safeVerdict ? "text-status-success" : "text-txt-primary"}`}>
            {safeVerdict ? "No validated security issue was confirmed in the selected scope." : "Validated repository assessment"}
          </p>
          <p className="mt-2 text-sm leading-6 text-txt-secondary">
            {toAnalystCopy(session.session.repositorySummary) || (safeVerdict ? "The selected source was reviewed and no high-confidence issue was confirmed." : "Khwarizm completed the repository assessment.")}
          </p>
          {!hasFindings && hasCoverageGap && (
            <p className="mt-2 text-sm leading-6 text-txt-secondary">
              The score is below 100 because the reviewed coverage was partial. No confirmed finding was retained, but the selected scope was not fully covered.
              {hasCandidateFindings ? " Candidate findings are shown below for manual review." : ""}
            </p>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.16 }}
          className="rounded-xl border bg-card px-4 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="grid gap-3 xl:grid-cols-[280px_1fr] xl:items-stretch">
            <div className="rounded-lg border bg-[#f6f1e8] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">Security score</p>
              <div className="mt-2 flex items-end gap-2">
                <span className="text-[34px] font-semibold leading-none tracking-[-0.05em] text-txt-primary">
                  {hasSecurityScore ? session.session.securityScore : "â€”"}
                </span>
                <span className="pb-0.5 text-xs text-txt-tertiary">{hasSecurityScore ? "/100" : "unavailable"}</span>
              </div>
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#ded4c6]">
                <div className="h-full rounded-full bg-primary" style={{ width: `${hasSecurityScore ? session.session.securityScore : 0}%` }} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
              <ScoreIssueChip label="Open critical" value={activeFindingCounts.critical} tone="critical" />
              <ScoreIssueChip label="Open findings" value={activeValidatedCount} tone="high" />
              <ScoreIssueChip label="Review queue" value={approvalQueue.length} tone="medium" />
              <ScoreIssueChip label="Candidates" value={filteredCandidateFindings.length} tone="low" />
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
          className="rounded-xl border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-txt-primary">Review coverage</p>
            <span className="text-xs font-medium uppercase tracking-[0.16em] text-txt-tertiary">
              {session.session.coveragePercent}% covered
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-txt-secondary">
            {toAnalystCopy(session.session.coverageSummary) || "Coverage details were not captured for this analysis."}
          </p>
          <div className="mt-3 grid gap-2 text-xs text-txt-secondary sm:grid-cols-2">
            <span>Files reviewed: {session.session.reviewedFilesCount}/{session.session.eligibleFilesCount || session.session.reviewedFilesCount}</span>
            <span>Blocks reviewed: {session.session.reviewedBlocksCount}/{session.session.totalBlocksCount || session.session.reviewedBlocksCount}</span>
            <span>Paths traced: {session.session.tracedPathsCount}/{session.session.totalPathsCount || session.session.tracedPathsCount}</span>
            <span>Elapsed: {formatElapsedSeconds(session.session.elapsedSeconds)}</span>
          </div>
          {excludedFiles.length > 0 && (
            <div className="mt-4 rounded-lg border bg-[#f6f1e8] px-4 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
              <p className="text-xs font-medium uppercase tracking-[0.16em] text-txt-tertiary">Excluded files</p>
              <div className="mt-2 space-y-1.5 text-sm text-txt-secondary">
                {excludedFiles.slice(0, 6).map((item) => (
                  <p key={`${item.file}:${item.reason}`}>
                    <span className="font-mono text-txt-primary">{item.file}</span> - {item.reason}
                  </p>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {session.session.workflowSummary && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.19 }}
            className="rounded-lg border bg-card px-5 py-4"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-txt-primary">Workflow orchestration</p>
                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-txt-tertiary">{session.session.workflowSummary.label}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium uppercase tracking-[0.16em] text-txt-tertiary">
                  {session.session.workflowSummary.activeController}
                </span>
                <button
                  onClick={onOpenAuditTrail}
                  className="rounded-md border px-3 py-1.5 text-xs font-medium text-txt-primary transition-colors hover:bg-muted/30"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  Open audit trail
                </button>
                <button
                  onClick={onOpenOperationsConsole}
                  className="rounded-md border px-3 py-1.5 text-xs font-medium text-txt-primary transition-colors hover:bg-muted/30"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  Open operations
                </button>
              </div>
            </div>
            <p className="mt-2 text-sm leading-6 text-txt-secondary">{session.session.workflowSummary.summary}</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <InfoSummaryCard
                label="Next action"
                value={session.session.workflowSummary.nextAction}
                note={`${session.session.workflowSummary.blockingItems} active workflow blocker${session.session.workflowSummary.blockingItems === 1 ? "" : "s"}`}
              />
              <InfoSummaryCard
                label="Workflow state"
                value={session.session.workflowSummary.state}
                note={`Controlled by ${session.session.workflowSummary.activeController}${session.session.workflowSummary.plannerStage ? ` - planner stage ${session.session.workflowSummary.plannerStage}` : ""}`}
              />
            </div>
            {session.session.workflowSummary.operationsSummary && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Operations lane"
                  value={session.session.workflowSummary.operationsSummary.currentLane}
                  note={`Next lane ${session.session.workflowSummary.operationsSummary.nextLane ?? "none"} - ${session.session.workflowSummary.operationsSummary.activeItemCount} active item(s)`}
                />
                <InfoSummaryCard
                  label="Lane handoff"
                  value={session.session.workflowSummary.operationsSummary.pendingHandoff ? "Pending handoff" : "No handoff pending"}
                  note={session.session.workflowSummary.operationsSummary.handoffReason}
                />
              </div>
            )}
            {session.session.workflowSummary.operationsExecution && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Operations execution"
                  value={session.session.workflowSummary.operationsExecution.currentHandoff}
                  note={`Status ${session.session.workflowSummary.operationsExecution.handoffStatus} - owner ${session.session.workflowSummary.operationsExecution.owningController}`}
                />
                <InfoSummaryCard
                  label="Pending step"
                  value={session.session.workflowSummary.operationsExecution.pendingExecutionStep}
                  note={session.session.workflowSummary.operationsExecution.stepCompletionState}
                />
              </div>
            )}
            {session.session.workflowSummary.workflowClosure && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Workflow closure"
                  value={session.session.workflowSummary.workflowClosure.closureLabel}
                  note={`${session.session.workflowSummary.workflowClosure.closureState} - next ${session.session.workflowSummary.workflowClosure.nextClosureStep}`}
                />
                <InfoSummaryCard
                  label="Closure control"
                  value={session.session.workflowSummary.workflowClosure.autonomousReady ? "Autonomous-ready" : session.session.workflowSummary.workflowClosure.requiresHumanControl ? "Human control required" : "Controlled progression"}
                  note={session.session.workflowSummary.workflowClosure.closureReason}
                />
              </div>
            )}
            {session.session.workflowSummary.recoverySummary && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Recovery readiness"
                  value={session.session.workflowSummary.recoverySummary.retryAvailable ? "Retry available" : "Stable"}
                  note={`${session.session.workflowSummary.recoverySummary.retryableFindings} retryable finding(s) - ${session.session.workflowSummary.recoverySummary.attemptedStrategies} attempted strategies - ${session.session.workflowSummary.recoverySummary.controllerStatus}`}
                />
                <InfoSummaryCard
                  label="Latest recovery signal"
                  value={session.session.workflowSummary.recoverySummary.lastVerificationStatus ?? "No recent verification"}
                  note={session.session.workflowSummary.recoverySummary.latestFailureReason}
                />
              </div>
            )}
            {session.session.workflowSummary.recoverySummary && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Recovery transition"
                  value={session.session.workflowSummary.recoverySummary.nextTransition}
                  note={`Recovery state ${session.session.workflowSummary.recoverySummary.recoveryState}${session.session.workflowSummary.recoverySummary.plannerReentryReady ? " - planner re-entry is ready" : ""}`}
                />
                <InfoSummaryCard
                  label="Recovery controller"
                  value={session.session.workflowSummary.recoverySummary.controllerStatus}
                  note={session.session.workflowSummary.recoverySummary.retryAvailable ? "A recovery path is still active for this session." : "No active recovery path remains."}
                />
              </div>
            )}
            {session.session.workflowSummary.recoveryExecution && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Recovery path"
                  value={session.session.workflowSummary.recoveryExecution.selectedPath}
                  note={`Lane ${session.session.workflowSummary.recoveryExecution.executionLane} - state ${session.session.workflowSummary.recoveryExecution.executionState}`}
                />
                <InfoSummaryCard
                  label="Recovery execution"
                  value={session.session.workflowSummary.recoveryExecution.reenteredPlanner ? "Planner re-entry recorded" : "No planner re-entry"}
                  note={session.session.workflowSummary.recoveryExecution.pathReason}
                />
              </div>
            )}
            {session.session.workflowSummary.memorySummary && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <InfoSummaryCard
                  label="Session memory"
                  value={`${session.session.workflowSummary.memorySummary.attemptedStrategyCount} attempted strategies`}
                  note={`${session.session.workflowSummary.memorySummary.rejectedPathCount} rejected path(s) - ${session.session.workflowSummary.memorySummary.escalatedPathCount} escalated path(s) - ${session.session.workflowSummary.memorySummary.suppressedStrategyCount} suppressed strategy(s)`}
                />
                <InfoSummaryCard
                  label="Current constraint"
                  value={
                    session.session.workflowSummary.memorySummary.knownStrategyIds.length > 0
                      ? session.session.workflowSummary.memorySummary.knownStrategyIds.join(", ")
                      : "No stored strategy ids"
                  }
                  note={`${session.session.workflowSummary.memorySummary.suppressionState} memory - ${session.session.workflowSummary.memorySummary.nextMemoryAction}. ${session.session.workflowSummary.memorySummary.recentConstraint}`}
                />
              </div>
            )}
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="grid gap-3 md:grid-cols-3"
        >
          <InfoSummaryCard
            label="Framework profile"
            value={formatFrameworkValue(session.session.frameworkProfile)}
            note={formatFrameworkNote(session.session.frameworkProfile)}
          />
          <InfoSummaryCard
            label="Repository graph"
            value={`${Number(session.session.graphSummary?.import_edges ?? 0)} import edges`}
            note={`${Number(session.session.graphSummary?.route_files ?? 0)} route files and ${Number(session.session.graphSummary?.auth_files ?? 0)} auth files`}
          />
          <InfoSummaryCard
            label="Path tracing"
            value={`${Number(session.session.pathSummary?.candidate_path_count ?? 0)} candidate paths`}
            note={`${Number(session.session.pathSummary?.cross_file_paths ?? 0)} cross-file paths identified`}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.22 }}
          className="grid gap-3 md:grid-cols-3"
        >
          <InfoSummaryCard
            label="Analysis mode"
            value={session.session.scanMode === "deep" ? "Deep analysis" : "Fast analysis"}
            note={String(session.session.scanPlan?.work_unit_strategy?.paths ?? "Path-centric review")}
          />
          <InfoSummaryCard
            label="Review queue"
            value={`${Number(session.session.reviewQueueSummary?.ranked_review_items ?? 0)} review items`}
            note={`${Number(session.session.reviewQueueSummary?.ranked_path_units ?? 0)} ranked paths`}
          />
          <InfoSummaryCard
            label="Score rationale"
            value={
              session.session.status === "failed"
                ? "Unavailable"
                : `${activeValidatedCount} open`
            }
            note={
              session.session.status === "failed"
                ? toAnalystCopy(String(session.errorMessage ?? "The analysis did not complete, so no security score was produced."))
                : `Queue ${approvalQueue.length} item(s) - coverage ${Number(session.session.scoreRationale?.coverage_percent ?? session.session.coveragePercent)} percent - candidate pressure ${Number(session.session.scoreRationale?.candidate_pressure ?? 0)}`
            }
          />
        </motion.div>

        <FindingsCard
          title="Validated findings"
          subtitle={approvalQueue.length > 0 ? "Open findings only" : undefined}
          findings={surfacedValidatedFindings}
          emptyMessage={
            safeVerdict
              ? hasCoverageGap
                ? "No confirmed finding was retained, but the reviewed coverage was partial. The score stays below 100 until the selected scope is fully covered."
                : "The analysis finished with a score of 100/100. No high-confidence, confirmed security issue was found in the reviewed scope."
              : approvalQueue.length > 0
                ? "All validated findings in this session are already tracked in the review queue below."
                : "No confirmed findings were returned for this analysis."
          }
          onSelectFinding={onSelectFinding}
        />

        {hasCandidateFindings && (
          <FindingsCard
            title="Candidate findings"
            subtitle="Needs review"
            findings={filteredCandidateFindings}
            emptyMessage="No candidate finding was retained for manual review."
            onSelectFinding={onSelectFinding}
            lowConfidence
          />
        )}

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="rounded-xl border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-txt-primary">Approval queue</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-txt-tertiary">Review-required items</p>
            </div>
            <span className="text-xs font-medium uppercase tracking-[0.16em] text-txt-tertiary">
              {approvalQueue.length} queued
            </span>
          </div>
          <div className="mt-3 space-y-2.5">
            {approvalQueue.map((item) => {
              const finding = orderedValidatedFindings.find((entry) => entry.id === item.findingId);
              return (
                <button
                  key={item.findingId}
                  onClick={() => finding && onSelectFinding(finding)}
                  className="flex w-full items-start gap-4 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-muted/30"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="mt-0.5">
                    <SeverityBadge severity={item.severity} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-medium text-txt-primary">{item.title}</p>
                      <span className="shrink-0 text-xs uppercase tracking-[0.16em] text-txt-tertiary">{item.statusLabel}</span>
                    </div>
                    <p className="mt-1 text-xs text-txt-tertiary">{item.file}</p>
                    <p className="mt-2 text-sm leading-6 text-txt-secondary">{item.reason}</p>
                  </div>
                </button>
              );
            })}
            {approvalQueue.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">
                No finding is currently waiting in the approval queue for this saved analysis session.
              </p>
            )}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.26 }}
          className="rounded-xl border bg-card px-5 py-4"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-txt-primary">Line annotations</p>
            <span className="text-xs uppercase tracking-[0.16em] text-txt-tertiary">{session.session.annotations.length} ready</span>
          </div>
          <div className="mt-3 space-y-2.5">
            {session.session.annotations.slice(0, 6).map((annotation) => (
              <AnnotationRow key={`${annotation.file}:${annotation.lineStart}:${annotation.title}`} annotation={annotation} />
            ))}
            {session.session.annotations.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">No line-level annotations were produced for this analysis.</p>
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}

function buildFindingFingerprint(finding: Finding): string {
  const category = finding.category.trim().toLowerCase();
  const title = finding.title.trim().toLowerCase();
  const evidence = finding.evidence.trim().toLowerCase().slice(0, 160);
  return [finding.file, category, title, evidence || `${finding.line}:${finding.lineEnd}`].join("|");
}

function dedupeCandidateFindings(validatedFindings: Finding[], candidateFindings: Finding[]): Finding[] {
  const validatedFingerprints = new Set(validatedFindings.map(buildFindingFingerprint));
  return candidateFindings.filter((finding) => !validatedFingerprints.has(buildFindingFingerprint(finding)));
}

function getExcludedFiles(coverageSnapshot: Record<string, unknown> | null): Array<{ file: string; reason: string }> {
  const rawItems = coverageSnapshot?.["excluded_files"];
  if (!Array.isArray(rawItems)) {
    return [];
  }

  return rawItems
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const file = "file" in item ? String(item.file ?? "").trim() : "";
      const reason = "reason" in item ? String(item.reason ?? "").trim() : "";
      if (!file || !reason) return null;
      return { file, reason };
    })
    .filter((item): item is { file: string; reason: string } => item !== null);
}

function FindingsCard({
  title,
  subtitle,
  findings,
  emptyMessage,
  onSelectFinding,
  action,
  lowConfidence = false,
}: {
  title: string;
  subtitle?: string;
  findings: Finding[];
  emptyMessage: string;
  onSelectFinding: (finding: Finding) => void;
  action?: ReactNode;
  lowConfidence?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden rounded-xl border bg-card"
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      <div className="px-5 pb-3 pt-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-txt-primary">{title}</h3>
            {subtitle && <p className="mt-1 text-xs uppercase tracking-[0.16em] text-txt-tertiary">{subtitle}</p>}
          </div>
          {action}
        </div>
      </div>
      <div className="divide-y" style={{ borderColor: "hsl(var(--border-soft))" }}>
        {findings.map((finding) => (
          <button
            key={`${title}-${finding.id}`}
            onClick={() => onSelectFinding(finding)}
            className="flex w-full items-start gap-4 px-5 py-4 text-left transition-colors duration-150 hover:bg-muted/30"
          >
            <div className="mt-0.5">
              <SeverityBadge severity={finding.severity} />
            </div>
            <div className="min-w-0">
              <p className="leading-snug text-sm font-medium text-txt-primary">{finding.title}</p>
              <p className="mt-1 text-xs text-txt-tertiary">
                {finding.file}:{formatFindingRange(finding)} - {finding.category}
              </p>
              {finding.remediationStatus !== "open" && (
                <p className={`mt-1 text-xs ${
                  getRemediationStatusTone(finding.remediationStatus) === "success"
                    ? "text-status-success"
                    : getRemediationStatusTone(finding.remediationStatus) === "warning"
                      ? "text-status-high"
                      : getRemediationStatusTone(finding.remediationStatus) === "progress"
                        ? "text-status-progress"
                        : "text-txt-secondary"
                }`}>
                  {getRemediationStatusLabel(finding.remediationStatus)}
                </p>
              )}
              {lowConfidence && (
                <p className="mt-1 text-xs text-txt-secondary">
                  Needs validation - confidence {finding.confidence}%
                </p>
              )}
            </div>
          </button>
        ))}
        {findings.length === 0 && (
          <div className="px-5 py-6 text-sm text-txt-secondary">{emptyMessage}</div>
        )}
      </div>
    </motion.div>
  );
}

function ScoreIssueChip({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "critical" | "high" | "medium" | "low";
}) {
  const numberToneClass =
    tone === "critical"
      ? "text-status-critical"
      : tone === "high"
        ? "text-status-high"
        : tone === "medium"
          ? "text-[#9a7d57]"
          : "text-[#8f877a]";

  return (
    <div className="min-w-0 rounded-lg border bg-[#f6f1e8] px-3 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <div className="mt-3 flex min-h-[44px] items-center justify-center">
        <span
          className={`block min-w-0 max-w-full overflow-hidden text-center font-mono text-[26px] font-semibold leading-none tracking-[-0.05em] tabular-nums ${numberToneClass}`}
          style={{ overflowWrap: "anywhere" }}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

function InfoSummaryCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-lg border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-3 text-sm font-semibold text-txt-primary">{value}</p>
      <p className="mt-2 text-xs leading-5 text-txt-secondary">{note}</p>
    </div>
  );
}

function AnnotationRow({ annotation }: { annotation: SessionAnnotation }) {
  const toneClass = annotation.tone === "red" ? "bg-[#fff6f4] text-status-critical" : "bg-[#fbf7ee] text-status-high";
  return (
    <div className="rounded-lg border px-3 py-3" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-txt-primary">{annotation.title}</p>
          <p className="mt-1 text-xs text-txt-tertiary">
            {annotation.file}:{annotation.lineStart}{annotation.lineEnd > annotation.lineStart ? `-${annotation.lineEnd}` : ""} - {annotation.pathHint || "Reviewed evidence path"}
          </p>
        </div>
        <span className={`rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] ${toneClass}`}>
          {annotation.tone}
        </span>
      </div>
    </div>
  );
}

function formatFindingRange(finding: Finding) {
  return finding.lineEnd > finding.line ? `${finding.line}-${finding.lineEnd}` : `${finding.line}`;
}

function formatFrameworkNote(profile: Record<string, unknown> | null) {
  if (!profile) {
    return "No framework markers were recorded.";
  }
  const supportMatrix = profile.support_matrix;
  const supportStack =
    supportMatrix && typeof supportMatrix === "object" && supportMatrix !== null && "primary" in supportMatrix
      ? String((supportMatrix.primary as { stack?: unknown })?.stack ?? "")
      : "";
  if (String(profile.primary_framework ?? "unknown") === "unknown" && supportStack && supportStack !== "unknown") {
    return `No explicit framework markers were recorded. Classified from the primary language as ${supportStack}.`;
  }
  const frameworks = Array.isArray(profile.frameworks) ? profile.frameworks.map(String).join(", ") : "";
  return frameworks || "No framework markers were recorded.";
}

function formatFrameworkValue(profile: Record<string, unknown> | null) {
  if (!profile) {
    return "unknown";
  }
  const primaryFramework = String(profile.primary_framework ?? "unknown");
  if (primaryFramework !== "unknown") {
    return primaryFramework;
  }
  const supportMatrix = profile.support_matrix;
  const supportStack =
    supportMatrix && typeof supportMatrix === "object" && supportMatrix !== null && "primary" in supportMatrix
      ? String((supportMatrix.primary as { stack?: unknown })?.stack ?? "unknown")
      : "unknown";
  return supportStack || "unknown";
}

function formatElapsedSeconds(value: number) {
  const totalSeconds = Math.max(0, value);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function countSeverities(findings: Finding[]) {
  return findings.reduce(
    (summary, finding) => {
      summary[finding.severity] += 1;
      return summary;
    },
    {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    } satisfies Record<Finding["severity"], number>,
  );
}
