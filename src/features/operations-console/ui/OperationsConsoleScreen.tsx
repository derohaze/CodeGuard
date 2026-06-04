import { motion } from "framer-motion";
import { Activity, ArrowRightLeft, Bot, ShieldAlert } from "lucide-react";
import type { ScanSessionDetail } from "@/shared/api/security";
import { buildOperationsAutonomySignals, summarizeOperationsAutonomySignals } from "../lib/operations-autonomy";
import { buildLearningSignals, summarizeLearningSignals } from "../lib/learning-signals";
import { buildOperationsControlDecisions, summarizeOperationsControlDecisions } from "../lib/operations-controls";
import { buildContinuousRemediationItems, summarizeContinuousRemediationItems } from "../lib/continuous-remediation";
import { buildMemoryCarryForwardItems, summarizeMemoryCarryForwardItems } from "../lib/memory-carry-forward";
import { buildRecommendationReuseItems, summarizeRecommendationReuseItems } from "../lib/recommendation-reuse";
import { buildContinuousExecutionCandidates } from "../lib/continuous-execution";
import { buildRecoveryPlaybookItems, summarizeRecoveryPlaybookItems } from "../lib/recovery-playbook";
import { buildSessionMemoryLedger, summarizeSessionMemoryLedger } from "../lib/session-memory-ledger";
import { buildSelfHealingControllerSignals, summarizeSelfHealingControllerSignals } from "../lib/self-healing-controller";

interface Props {
  session: ScanSessionDetail | null;
  onRunContinuousApply?: (input: {
    findingId: string;
    excludedStrategyIds: string[];
    attemptedStrategyIds: string[];
  }) => Promise<unknown> | unknown;
  isRunningContinuousApply?: boolean;
}

export function OperationsConsoleScreen({
  session,
  onRunContinuousApply,
  isRunningContinuousApply = false,
}: Props) {
  if (!session?.session.workflowSummary) return null;

  const workflow = session.session.workflowSummary;
  const operations = workflow.operationsSummary;
  const execution = workflow.operationsExecution;
  const recovery = workflow.recoveryExecution;
  const closure = workflow.workflowClosure;
  const autonomySignals = buildOperationsAutonomySignals(session);
  const autonomySummary = summarizeOperationsAutonomySignals(autonomySignals);
  const learningSignals = buildLearningSignals(session.findings);
  const learningSummary = summarizeLearningSignals(learningSignals);
  const memoryCarryForward = buildMemoryCarryForwardItems(session);
  const memorySummary = summarizeMemoryCarryForwardItems(memoryCarryForward);
  const recommendationReuse = buildRecommendationReuseItems(session);
  const recommendationSummary = summarizeRecommendationReuseItems(recommendationReuse);
  const continuousExecutionCandidates = buildContinuousExecutionCandidates(session);
  const recoveryPlaybook = buildRecoveryPlaybookItems(session);
  const recoverySummary = summarizeRecoveryPlaybookItems(recoveryPlaybook);
  const sessionMemoryLedger = buildSessionMemoryLedger(session);
  const sessionMemorySummary = summarizeSessionMemoryLedger(sessionMemoryLedger);
  const selfHealingSignals = buildSelfHealingControllerSignals(session);
  const selfHealingSummary = summarizeSelfHealingControllerSignals(selfHealingSignals);
  const controlDecisions = buildOperationsControlDecisions(session, autonomySignals, learningSignals);
  const controlSummary = summarizeOperationsControlDecisions(controlDecisions);
  const continuousRemediation = buildContinuousRemediationItems(session, autonomySignals, controlDecisions);
  const continuousSummary = summarizeContinuousRemediationItems(continuousRemediation);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-4xl space-y-4">
        <section
          className="rounded-2xl border bg-card px-5 py-5 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Operations console</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{session.session.repo}</h2>
              <p className="mt-2 text-sm text-txt-tertiary">
                This surface exposes the live workflow owner, handoff status, recovery path, and closure readiness for the current security run.
              </p>
            </div>
            <span className="rounded-full bg-[#eeeeee] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {workflow.label}
            </span>
          </div>
        </section>

        {closure && (
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <OperationsCard
              icon={Bot}
              label="Workflow closure"
              value={closure.closureLabel}
              note={`${closure.closureState} - next ${closure.nextClosureStep}`}
            />
            <OperationsCard
              icon={ShieldAlert}
              label="Control mode"
              value={closure.autonomousReady ? "Autonomous-ready" : closure.requiresHumanControl ? "Human control required" : "Controlled progression"}
              note={closure.closureReason}
            />
            <OperationsCard
              icon={Activity}
              label="Owning controller"
              value={workflow.activeController}
              note={workflow.nextAction}
            />
          </section>
        )}

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Autonomy signals"
            value={`${autonomySummary.signalCount} signal(s)`}
            note={autonomySummary.topSignalLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Critical drag"
            value={`${autonomySummary.criticalSignals} signal(s)`}
            note={`${autonomySummary.humanControlSignals} human-control and ${autonomySummary.recoveryDragSignals} recovery signal(s) remain active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Handoff drag"
            value={`${autonomySummary.handoffDragSignals} signal(s)`}
            note="Workflow handoffs still shaping autonomous progression."
          />
          <OperationsCard
            icon={Activity}
            label="Ready signals"
            value={`${autonomySummary.autonomousReadySignals} signal(s)`}
            note="Signals indicating the run can advance with minimal manual intervention."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={ShieldAlert}
            label="Control decisions"
            value={`${controlSummary.decisionCount} decision(s)`}
            note={controlSummary.topDecisionLabel}
          />
          <OperationsCard
            icon={Bot}
            label="Hold / recover"
            value={`${controlSummary.holdDecisions + controlSummary.recoverDecisions} decision(s)`}
            note={`${controlSummary.criticalDecisions} critical control decision(s) remain active.`}
          />
          <OperationsCard
            icon={Activity}
            label="Stabilize"
            value={`${controlSummary.stabilizeDecisions} decision(s)`}
            note="Learning-derived controls before expanding autonomy."
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Advance windows"
            value={`${controlSummary.advanceDecisions} decision(s)`}
            note="Low-risk windows that may allow controlled autonomous progression."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Recommendation reuse"
            value={`${recommendationSummary.itemCount} item(s)`}
            note={recommendationSummary.topItemLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Reuse blockers"
            value={`${recommendationSummary.criticalItems} item(s)`}
            note={`${recommendationSummary.suppressedReuseItems} suppressed strategy item(s) remain blocked from automatic reuse.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Ready reuse"
            value={`${recommendationSummary.readyReuseItems} item(s)`}
            note="Verified-safe strategies that may seed the next low-risk recommendation."
          />
          <OperationsCard
            icon={Activity}
            label="Guarded reuse"
            value={`${recommendationSummary.guardedReuseItems} item(s)`}
            note="Stored strategies that still need guarded review before reuse."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Carry-forward memory"
            value={`${memorySummary.itemCount} item(s)`}
            note={memorySummary.topItemLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Critical memory"
            value={`${memorySummary.criticalItems} item(s)`}
            note={`${memorySummary.suppressionItems} suppression and ${memorySummary.escalationItems} escalation memory item(s) remain active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Reuse memory"
            value={`${memorySummary.reuseItems} item(s)`}
            note="Stored strategies that may seed the next controlled remediation path."
          />
          <OperationsCard
            icon={Activity}
            label="Constraints"
            value={`${memorySummary.constraintItems} item(s)`}
            note="Recorded constraints that should shape the next learning-aware remediation pass."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Continuous workflow"
            value={`${continuousSummary.workflowCount} workflow(s)`}
            note={continuousSummary.topWorkflowLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Held windows"
            value={`${continuousSummary.heldWorkflows} workflow(s)`}
            note={`${continuousSummary.criticalWorkflows} critical workflow gate(s) remain active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Recovery-owned"
            value={`${continuousSummary.recoveryWorkflows} workflow(s)`}
            note="Continuous execution is still deferred to an active recovery lane."
          />
          <OperationsCard
            icon={Activity}
            label="Eligible windows"
            value={`${continuousSummary.eligibleWorkflows} workflow(s)`}
            note="Low-risk autonomous passes that can proceed under policy and verification control."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={ShieldAlert}
            label="Recovery playbook"
            value={`${recoverySummary.itemCount} item(s)`}
            note={recoverySummary.topItemLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Critical recovery"
            value={`${recoverySummary.criticalItems} item(s)`}
            note={`${recoverySummary.manualItems} manual and ${recoverySummary.terminalItems} terminal recovery item(s) remain active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Retry lanes"
            value={`${recoverySummary.retryItems} item(s)`}
            note="Guarded retry paths still shaping recovery readiness."
          />
          <OperationsCard
            icon={Activity}
            label="Planner re-entry"
            value={`${recoverySummary.plannerItems} item(s)`}
            note="Planner re-entry steps that keep the recovery controller active."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Learning signals"
            value={`${learningSummary.signalCount} signal(s)`}
            note={learningSummary.topSignalLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Critical learning"
            value={`${learningSummary.criticalSignals} signal(s)`}
            note={`${learningSummary.suppressionSignals} suppression and ${learningSummary.approvalPatterns} approval pattern(s) remain active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Reuse candidates"
            value={`${learningSummary.reuseSignals} signal(s)`}
            note="Verified paths that may become future recommendation seeds."
          />
          <OperationsCard
            icon={Activity}
            label="Verification memory"
            value={`${learningSummary.verificationPatterns} signal(s)`}
            note="Signals showing incomplete verification or reusable verification notes."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={Bot}
            label="Self-healing controller"
            value={`${selfHealingSummary.signalCount} signal(s)`}
            note={selfHealingSummary.topSignalLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Approval holds"
            value={`${selfHealingSummary.approvalHoldSignals} signal(s)`}
            note={`${selfHealingSummary.policyBlockSignals} policy block(s) still gate autonomous remediation.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Verification holds"
            value={`${selfHealingSummary.verificationHoldSignals} signal(s)`}
            note="Verification gaps that pause self-healing readiness."
          />
          <OperationsCard
            icon={Activity}
            label="Auto-heal windows"
            value={`${selfHealingSummary.autoHealSignals} signal(s)`}
            note="Low-risk windows ready for a guarded self-healing pass."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationsCard
            icon={ShieldAlert}
            label="Session memory ledger"
            value={`${sessionMemorySummary.itemCount} item(s)`}
            note={sessionMemorySummary.topItemLabel}
          />
          <OperationsCard
            icon={ShieldAlert}
            label="Critical memory"
            value={`${sessionMemorySummary.criticalItems} item(s)`}
            note={`${sessionMemorySummary.suppressionItems} suppression and ${sessionMemorySummary.escalationItems} escalation memory item(s) active.`}
          />
          <OperationsCard
            icon={ArrowRightLeft}
            label="Attempt history"
            value={`${sessionMemorySummary.attemptItems} item(s)`}
            note="Strategy attempt history shaping the next remediation cycle."
          />
          <OperationsCard
            icon={Activity}
            label="Constraint memory"
            value={`${sessionMemorySummary.constraintItems} item(s)`}
            note="Recorded constraints that still shape the next remediation step."
          />
        </section>

        {operations && execution && (
          <section
            className="rounded-2xl border bg-card px-5 py-4 shadow-card"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="mb-3 flex items-center gap-2">
              <ArrowRightLeft size={16} className="text-txt-secondary" />
              <p className="text-sm font-semibold text-txt-primary">Live operations</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <OperationsRow
                label="Lane flow"
                value={`${operations.currentLane} -> ${operations.nextLane ?? "none"}`}
              />
              <OperationsRow
                label="Lane handoff"
                value={operations.pendingHandoff ? "Pending handoff" : "No handoff pending"}
                note={operations.handoffReason}
              />
              <OperationsRow
                label="Current handoff"
                value={execution.currentHandoff}
              />
              <OperationsRow
                label="Execution status"
                value={`${execution.handoffStatus} - ${execution.stepCompletionState}`}
                note={`Owner ${execution.owningController}`}
              />
              <OperationsRow
                label="Pending execution step"
                value={execution.pendingExecutionStep}
              />
              <OperationsRow
                label="Active workflow items"
                value={`${operations.activeItemCount} item(s)`}
              />
            </div>
          </section>
        )}

        {autonomySignals.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Bot size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Autonomy readiness queue</p>
          </div>
          <div className="space-y-3">
            {autonomySignals.map((item) => (
                <div
                  key={`${item.signalClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.signalClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Operational note" value={item.note} />
                    <OperationsRow label="Next action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {selfHealingSignals.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Activity size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Self-healing controller queue</p>
          </div>
          <div className="space-y-3">
            {selfHealingSignals.map((item) => (
                <div
                  key={`${item.signalClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.signalClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Self-healing note" value={item.note} />
                    <OperationsRow label="Next controller action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {continuousExecutionCandidates.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Continuous execution queue</p>
          </div>
          <div className="space-y-3">
            {continuousExecutionCandidates.map((item) => (
                <div
                  key={item.finding.id}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.finding.remediationStatus}
                      </p>
                    </div>
                    {onRunContinuousApply ? (
                      <button
                        onClick={() =>
                          void onRunContinuousApply({
                            findingId: item.finding.id,
                            excludedStrategyIds: item.excludedStrategyIds,
                            attemptedStrategyIds: item.attemptedStrategyIds,
                          })
                        }
                        disabled={isRunningContinuousApply}
                        className="rounded-xl border bg-card px-4 py-2 text-sm font-medium text-txt-primary disabled:opacity-60"
                        style={{ borderColor: "hsl(var(--border-primary))" }}
                      >
                        {isRunningContinuousApply ? "Running controlled apply..." : "Run controlled apply"}
                      </button>
                    ) : null}
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Execution reason" value={item.reason} />
                    <OperationsRow label="Next execution action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {sessionMemoryLedger.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Bot size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Session memory ledger</p>
          </div>
          <div className="space-y-3">
            {sessionMemoryLedger.map((item) => (
                <div
                  key={`${item.memoryClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.memoryClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Memory reason" value={item.reason} />
                    <OperationsRow label="Next memory action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {recoveryPlaybook.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Recovery playbook</p>
          </div>
          <div className="space-y-3">
            {recoveryPlaybook.map((item) => (
                <div
                  key={`${item.recoveryClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.recoveryClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Recovery reason" value={item.reason} />
                    <OperationsRow label="Next recovery action" value={item.nextAction} />
                    <OperationsRow label="Lane status" value={item.laneSummary} />
                    <OperationsRow label="Controller status" value={item.controllerStatus} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {recommendationReuse.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ArrowRightLeft size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Recommendation reuse queue</p>
          </div>
          <div className="space-y-3">
            {recommendationReuse.map((item) => (
                <div
                  key={`${item.reuseClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.reuseClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Reuse reason" value={item.reason} />
                    <OperationsRow label="Next reuse action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {memoryCarryForward.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Bot size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Memory carry-forward</p>
          </div>
          <div className="space-y-3">
            {memoryCarryForward.map((item) => (
                <div
                  key={`${item.memoryClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.memoryClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Memory reason" value={item.reason} />
                    <OperationsRow label="Next memory action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {continuousRemediation.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ArrowRightLeft size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Continuous remediation workflow</p>
          </div>
          <div className="space-y-3">
            {continuousRemediation.map((item) => (
                <div
                  key={`${item.workflowClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.workflowClass} - {item.workflowState}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Workflow reason" value={item.reason} />
                    <OperationsRow label="Next workflow action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {learningSignals.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Activity size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Remediation history signals</p>
          </div>
          <div className="space-y-3">
            {learningSignals.map((item) => (
                <div
                  key={`${item.finding.id}-${item.signalClass}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.signalClass}
                      </p>
                    </div>
                    <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                      {item.finding.remediationStatus}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Learning note" value={item.note} />
                    <OperationsRow label="Next action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {controlDecisions.length > 0 && (
        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Autonomous control plan</p>
          </div>
          <div className="space-y-3">
            {controlDecisions.map((item) => (
                <div
                  key={`${item.controlClass}-${item.label}`}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {item.priority} - {item.controlClass} - {item.controlMode}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <OperationsRow label="Control reason" value={item.reason} />
                    <OperationsRow label="Next control action" value={item.nextAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>
        )}

        {recovery && (
          <section
            className="rounded-2xl border bg-card px-5 py-4 shadow-card"
            style={{ borderColor: "hsl(var(--border-soft))" }}
          >
            <div className="mb-3 flex items-center gap-2">
              <ShieldAlert size={16} className="text-status-high" />
              <p className="text-sm font-semibold text-txt-primary">Recovery execution</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <OperationsRow label="Recovery path" value={recovery.selectedPath} />
              <OperationsRow label="Execution lane" value={`${recovery.executionLane} - ${recovery.executionState}`} />
              <OperationsRow label="Planner re-entry" value={recovery.reenteredPlanner ? "Recorded" : "Not selected"} />
              <OperationsRow label="Path reason" value={recovery.pathReason} />
            </div>
          </section>
        )}

      </div>
    </motion.div>
  );
}

function OperationsCard({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-4 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm font-semibold text-txt-primary">{value}</p>
      <p className="mt-2 text-xs leading-5 text-txt-secondary">{note}</p>
    </div>
  );
}

function OperationsRow({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-sm leading-6 text-txt-primary">{value}</p>
      {note ? <p className="mt-2 text-xs leading-5 text-txt-secondary">{note}</p> : null}
    </div>
  );
}
