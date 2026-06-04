import { motion } from "framer-motion";
import { AlertTriangle, ClipboardList, Shield, Users } from "lucide-react";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { buildGovernanceQueue, summarizeGovernanceQueue } from "@/features/governance-center/lib/governance-queue";
import { buildGovernanceLedger, summarizeGovernanceLedger } from "@/features/governance-center/lib/governance-ledger";
import type { ScanSessionDetail } from "@/shared/api/security";

interface Props {
  session: ScanSessionDetail | null;
}

type GovernanceCountMap = Record<string, number>;

export function GovernanceCenterScreen({ session }: Props) {
  if (!session) return null;

  const decisions = session.findings.map((finding) => ({
    finding,
    decision: buildFindingDecisionSummary(finding),
  }));
  const governanceQueue = buildGovernanceQueue(session.findings);
  const queueSummary = summarizeGovernanceQueue(governanceQueue);
  const ledgerItems = buildGovernanceLedger(session.findings);
  const ledgerSummary = summarizeGovernanceLedger(ledgerItems);

  const approvalCounts = countBy(decisions.map(({ finding }) => finding.approvalStatus));
  const policyCounts = countBy(decisions.map(({ decision }) => decision.policyOutcome));
  const escalationCounts = countBy(decisions.map(({ decision }) => decision.escalationState));
  const closure = session.session.workflowSummary?.workflowClosure ?? null;
  const highRiskCount = decisions.filter(({ decision }) => decision.riskScore >= 85).length;
  const humanControlledCount = decisions.filter(({ decision }) => decision.policySummary.autoPathState !== "eligible").length;
  const pendingApprovalCount = decisions.filter(({ finding }) => finding.approvalStatus === "pending").length;
  const rejectedCount = decisions.filter(({ finding }) => finding.approvalStatus === "rejected").length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-5xl space-y-4">
        <section
          className="rounded-2xl border bg-card px-5 py-5 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Governance center</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{session.session.repo}</h2>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">
                This surface summarizes approval pressure, policy posture, escalation load, and control requirements for the current security run.
              </p>
            </div>
            <span className="shrink-0 whitespace-nowrap rounded-full bg-[#eeeeee] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {session.findings.length} governed finding{session.findings.length === 1 ? "" : "s"}
            </span>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <GovernanceCard
            icon={Shield}
            label="Workflow control"
            value={closure?.closureLabel ?? "No closure state"}
            note={closure?.closureReason ?? "Workflow closure is not available for this session."}
          />
          <GovernanceCard
            icon={Users}
            label="Human-controlled paths"
            value={`${humanControlledCount} finding(s)`}
            note={`${pendingApprovalCount} pending approval, ${rejectedCount} rejected`}
          />
          <GovernanceCard
            icon={AlertTriangle}
            label="High-risk findings"
            value={`${highRiskCount} finding(s)`}
            note="High-risk findings are counted at risk score 85 or above."
          />
          <GovernanceCard
            icon={ClipboardList}
            label="Escalations"
            value={`${(escalationCounts.required ?? 0) + (escalationCounts["already-escalated"] ?? 0)} finding(s)`}
            note={`${escalationCounts["already-escalated"] ?? 0} already escalated`}
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <GovernanceCard
            icon={ClipboardList}
            label="Queue pressure"
            value={`${queueSummary.queuedFindings} governed item(s)`}
            note={queueSummary.highestPriorityLabel}
          />
          <GovernanceCard
            icon={AlertTriangle}
            label="Critical review"
            value={`${queueSummary.criticalItems} critical item(s)`}
            note={`${queueSummary.escalationHolds} escalation hold(s) currently need governance review`}
          />
          <GovernanceCard
            icon={Users}
            label="Approval holds"
            value={`${queueSummary.approvalHolds} finding(s)`}
            note="These findings are blocked on explicit approval progression."
          />
          <GovernanceCard
            icon={Shield}
            label="Policy gates"
            value={`${queueSummary.policyGates} finding(s)`}
            note="These findings need a safer remediation path before governance can release them."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <GovernanceCard
            icon={ClipboardList}
            label="Governance ledger"
            value={`${ledgerSummary.itemCount} item(s)`}
            note={ledgerSummary.topItemLabel}
          />
          <GovernanceCard
            icon={AlertTriangle}
            label="Critical ledger"
            value={`${ledgerSummary.criticalItems} item(s)`}
            note={`${ledgerSummary.escalationItems} escalation / ${ledgerSummary.policyItems} policy items active.`}
          />
          <GovernanceCard
            icon={Users}
            label="Approval ledger"
            value={`${ledgerSummary.approvalItems} item(s)`}
            note="Approval pressure captured for governance review."
          />
          <GovernanceCard
            icon={Shield}
            label="Control ledger"
            value={`${ledgerSummary.controlItems} item(s)`}
            note="Human-control posture tracked for governance routing."
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <GovernanceTable
            title="Approval posture"
            rows={[
              { label: "Not required", value: approvalCounts.not_required ?? 0 },
              { label: "Pending", value: approvalCounts.pending ?? 0 },
              { label: "Approved", value: approvalCounts.approved ?? 0 },
              { label: "Rejected", value: approvalCounts.rejected ?? 0 },
              { label: "Escalated", value: approvalCounts.escalated ?? 0 },
            ]}
          />
          <GovernanceTable
            title="Policy posture"
            rows={[
              { label: "Auto-eligible", value: policyCounts["auto-eligible"] ?? 0 },
              { label: "Review required", value: policyCounts["review-required"] ?? 0 },
              { label: "Blocked by policy", value: policyCounts["blocked-by-policy"] ?? 0 },
            ]}
          />
          <GovernanceTable
            title="Escalation state"
            rows={[
              { label: "None", value: escalationCounts.none ?? 0 },
              { label: "Required", value: escalationCounts.required ?? 0 },
              { label: "Already escalated", value: escalationCounts["already-escalated"] ?? 0 },
            ]}
          />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ClipboardList size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Governance review queue</p>
          </div>
          <div className="space-y-3">
            {governanceQueue.length === 0 ? (
              <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4 text-sm text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                No governed findings currently require queue review.
              </div>
            ) : null}
            {governanceQueue.map(({ finding, decision, blockerClass, queuePriority, owner, nextReviewAction }) => (
                <div
                  key={finding.id}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{finding.title}</p>
                      <p className="mt-1 text-xs font-mono text-txt-tertiary">
                        {finding.file}:{finding.line}{finding.lineEnd > finding.line ? `-${finding.lineEnd}` : ""}
                      </p>
                    </div>
                    <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                      {decision.riskScore}/100
                    </span>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <GovernanceRow label="Approval" value={finding.approvalStatus} />
                    <GovernanceRow label="Policy outcome" value={decision.policyOutcome} />
                    <GovernanceRow label="Blocker class" value={blockerClass} />
                    <GovernanceRow label="Queue priority" value={`${queuePriority} - ${owner}`} />
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <GovernanceRow label="Escalation" value={decision.escalationState} />
                    <GovernanceRow label="Next review action" value={nextReviewAction} />
                  </div>
                </div>
              ))}
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ClipboardList size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Governance ledger</p>
          </div>
          <div className="space-y-3">
            {ledgerItems.map((item) => (
              <div
                key={`${item.ledgerClass}-${item.label}`}
                className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                    <p className="mt-1 text-xs text-txt-tertiary">
                      {item.priority} - {item.ledgerClass}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <GovernanceRow label="Evidence" value={item.evidence} />
                  <GovernanceRow label="Next action" value={item.nextAction} />
                </div>
              </div>
            ))}
            {ledgerItems.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">
                No governance ledger entries are active for the current run.
              </p>
            )}
          </div>
        </section>

      </div>
    </motion.div>
  );
}

function GovernanceCard({
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

function GovernanceTable({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: number }>;
}) {
  const activeRows = rows.filter((row) => row.value > 0);
  return (
    <section className="rounded-2xl border bg-card px-5 py-4 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-sm font-semibold text-txt-primary">{title}</p>
      {activeRows.length === 0 ? (
        <p className="mt-3 text-sm text-txt-secondary">No active items in this section.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {activeRows.map((row) => (
            <div key={row.label} className="flex items-center justify-between rounded-xl bg-[#f7f7f7] px-4 py-3">
              <span className="text-sm text-txt-secondary">{row.label}</span>
              <span className="text-sm font-semibold text-txt-primary">{row.value}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function GovernanceRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-sm leading-6 text-txt-secondary">{value}</p>
    </div>
  );
}

function countBy(values: string[]): GovernanceCountMap {
  return values.reduce<GovernanceCountMap>((accumulator, value) => {
    accumulator[value] = (accumulator[value] ?? 0) + 1;
    return accumulator;
  }, {});
}
