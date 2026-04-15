import { motion } from "framer-motion";
import { BarChart3, CheckCircle2, Clock3, ShieldAlert } from "lucide-react";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { buildAnalyticsHotspots, summarizeAnalyticsHotspots } from "@/features/analytics-dashboard/lib/analytics-insights";
import { buildAnalyticsLedger, summarizeAnalyticsLedger } from "@/features/analytics-dashboard/lib/analytics-ledger";
import type { ScanSessionDetail } from "@/shared/api/security";

interface Props {
  session: ScanSessionDetail | null;
  onBack: () => void;
  onOpenRepoOverview: () => void;
}

type CountMap = Record<string, number>;

export function AnalyticsDashboardScreen({ session, onBack, onOpenRepoOverview }: Props) {
  if (!session) return null;

  const enrichedFindings = session.findings.map((finding) => ({
    finding,
    decision: buildFindingDecisionSummary(finding),
  }));
  const hotspots = buildAnalyticsHotspots(session.findings);
  const hotspotSummary = summarizeAnalyticsHotspots(hotspots);
  const ledgerItems = buildAnalyticsLedger(session.findings);
  const ledgerSummary = summarizeAnalyticsLedger(ledgerItems);

  const remediationCounts = countBy(enrichedFindings.map(({ finding }) => finding.remediationStatus));
  const approvalCounts = countBy(enrichedFindings.map(({ finding }) => finding.approvalStatus));
  const policyCounts = countBy(enrichedFindings.map(({ decision }) => decision.policyOutcome));
  const riskBands = {
    immediate: enrichedFindings.filter(({ decision }) => decision.riskScore >= 85).length,
    review: enrichedFindings.filter(({ decision }) => decision.riskScore >= 65 && decision.riskScore < 85).length,
    schedule: enrichedFindings.filter(({ decision }) => decision.riskScore < 65).length,
  };

  const verifiedFixedCount = remediationCounts.verified_fixed ?? 0;
  const pendingApprovalCount = approvalCounts.pending ?? 0;
  const blockedPolicyCount = policyCounts["blocked-by-policy"] ?? 0;
  const partialOrFailedCount = (remediationCounts.verified_partial ?? 0) + (remediationCounts.validation_failed ?? 0);

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
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Analytics dashboard</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{session.session.repo}</h2>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">
                This surface summarizes remediation throughput, approval bottlenecks, policy pressure, and current risk distribution for the active security run.
              </p>
            </div>
            <span className="shrink-0 whitespace-nowrap rounded-full bg-[#f4efe7] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {session.findings.length} analyzed finding{session.findings.length === 1 ? "" : "s"}
            </span>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AnalyticsCard
            icon={CheckCircle2}
            label="Verified fixed"
            value={`${verifiedFixedCount} finding(s)`}
            note="Findings marked as fully verified after remediation."
          />
          <AnalyticsCard
            icon={Clock3}
            label="Approval bottleneck"
            value={`${pendingApprovalCount} pending`}
            note="Pending approvals are the current governance bottleneck."
          />
          <AnalyticsCard
            icon={ShieldAlert}
            label="Policy blocked"
            value={`${blockedPolicyCount} blocked`}
            note="Blocked findings require a stronger patch or manual handling."
          />
          <AnalyticsCard
            icon={BarChart3}
            label="Partial / failed"
            value={`${partialOrFailedCount} finding(s)`}
            note="Includes partial verification and validation failures."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AnalyticsCard
            icon={BarChart3}
            label="Hotspot queue"
            value={`${hotspotSummary.hotspotCount} item(s)`}
            note={hotspotSummary.topHotspotLabel}
          />
          <AnalyticsCard
            icon={ShieldAlert}
            label="Critical drag"
            value={`${hotspotSummary.criticalHotspots} item(s)`}
            note={`${hotspotSummary.verificationDrag} verification / ${hotspotSummary.approvalDrag} approval / ${hotspotSummary.policyDrag} policy`}
          />
          <AnalyticsCard
            icon={Clock3}
            label="Verification drag"
            value={`${hotspotSummary.verificationDrag} finding(s)`}
            note="These findings still degrade remediation reliability."
          />
          <AnalyticsCard
            icon={CheckCircle2}
            label="Approval drag"
            value={`${hotspotSummary.approvalDrag} finding(s)`}
            note="These findings still wait on approval progression."
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AnalyticsCard
            icon={BarChart3}
            label="Analytics ledger"
            value={`${ledgerSummary.itemCount} item(s)`}
            note={ledgerSummary.topItemLabel}
          />
          <AnalyticsCard
            icon={ShieldAlert}
            label="Critical ledger"
            value={`${ledgerSummary.criticalItems} item(s)`}
            note={`${ledgerSummary.policyItems} policy / ${ledgerSummary.approvalItems} approval entries active.`}
          />
          <AnalyticsCard
            icon={Clock3}
            label="Verification ledger"
            value={`${ledgerSummary.verificationItems} item(s)`}
            note="Verification drag mapped into the analytics ledger."
          />
          <AnalyticsCard
            icon={CheckCircle2}
            label="Throughput ledger"
            value={`${ledgerSummary.throughputItems} item(s)`}
            note="Remediation throughput signals used for run-level guidance."
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-3">
          <AnalyticsTable
            title="Remediation outcomes"
            rows={[
              { label: "Open", value: remediationCounts.open ?? 0 },
              { label: "Plan ready", value: remediationCounts.patch_generated ?? 0 },
              { label: "Applied", value: remediationCounts.applied ?? 0 },
              { label: "Verified fixed", value: remediationCounts.verified_fixed ?? 0 },
              { label: "Verified partial", value: remediationCounts.verified_partial ?? 0 },
              { label: "Validation failed", value: remediationCounts.validation_failed ?? 0 },
            ]}
          />
          <AnalyticsTable
            title="Approval distribution"
            rows={[
              { label: "Not required", value: approvalCounts.not_required ?? 0 },
              { label: "Pending", value: approvalCounts.pending ?? 0 },
              { label: "Approved", value: approvalCounts.approved ?? 0 },
              { label: "Rejected", value: approvalCounts.rejected ?? 0 },
              { label: "Escalated", value: approvalCounts.escalated ?? 0 },
            ]}
          />
          <AnalyticsTable
            title="Risk distribution"
            rows={[
              { label: "Immediate attention", value: riskBands.immediate },
              { label: "Needs remediation", value: riskBands.review },
              { label: "Review and schedule", value: riskBands.schedule },
            ]}
          />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Policy pressure</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <AnalyticsRow label="Auto-eligible" value={`${policyCounts["auto-eligible"] ?? 0} finding(s)`} />
            <AnalyticsRow label="Review required" value={`${policyCounts["review-required"] ?? 0} finding(s)`} />
            <AnalyticsRow label="Blocked by policy" value={`${policyCounts["blocked-by-policy"] ?? 0} finding(s)`} />
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Analytics hotspots</p>
          </div>
          <div className="space-y-3">
            {hotspots.map((item) => (
              <div
                key={item.finding.id}
                className="rounded-2xl border bg-[#fbf7f1] px-4 py-4"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-txt-primary">{item.finding.title}</p>
                    <p className="mt-1 text-xs text-txt-tertiary">
                      {item.pressurePriority} - {item.pressureClass}
                    </p>
                  </div>
                  <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                    {item.decision.riskScore}/100
                  </span>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <AnalyticsRow label="Approval" value={item.finding.approvalStatus} />
                  <AnalyticsRow label="Policy" value={item.decision.policyOutcome} />
                  <AnalyticsRow label="Remediation" value={item.finding.remediationStatus} />
                  <AnalyticsRow label="Next action" value={item.nextAction} />
                </div>
              </div>
            ))}
            {hotspots.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">
                No active analytics hotspot remains for this saved analysis session.
              </p>
            )}
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Analytics ledger</p>
          </div>
          <div className="space-y-3">
            {ledgerItems.map((item) => (
              <div
                key={`${item.ledgerClass}-${item.label}`}
                className="rounded-2xl border bg-[#fbf7f1] px-4 py-4"
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
                  <AnalyticsRow label="Evidence" value={item.evidence} />
                  <AnalyticsRow label="Next action" value={item.nextAction} />
                </div>
              </div>
            ))}
            {ledgerItems.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">
                No analytics ledger entries are active for this run.
              </p>
            )}
          </div>
        </section>
      </div>
    </motion.div>
  );
}

function AnalyticsCard({
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

function AnalyticsTable({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; value: number }>;
}) {
  return (
    <section className="rounded-2xl border bg-card px-5 py-4 shadow-card" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-sm font-semibold text-txt-primary">{title}</p>
      <div className="mt-3 space-y-2">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between rounded-xl bg-[#fbf7f1] px-4 py-3">
            <span className="text-sm text-txt-secondary">{row.label}</span>
            <span className="text-sm font-semibold text-txt-primary">{row.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function AnalyticsRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border bg-[#fbf7f1] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className="mt-2 text-sm leading-6 text-txt-secondary">{value}</p>
    </div>
  );
}

function countBy(values: string[]): CountMap {
  return values.reduce<CountMap>((accumulator, value) => {
    accumulator[value] = (accumulator[value] ?? 0) + 1;
    return accumulator;
  }, {});
}
