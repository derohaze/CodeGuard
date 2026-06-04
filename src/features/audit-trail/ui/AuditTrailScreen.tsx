import { motion } from "framer-motion";
import { ArrowRight, Clock3, FileSearch, ShieldCheck } from "lucide-react";
import type { Finding } from "@/entities/finding/model/types";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { getRemediationStatusLabel } from "@/entities/finding/lib/remediation-status";
import { buildAuditTimeline, summarizeAuditTimeline } from "@/features/audit-trail/lib/audit-timeline";
import { buildRunAuditLog, summarizeRunAuditLog } from "@/features/audit-trail/lib/run-audit-log";
import type { ScanSessionDetail } from "@/shared/api/security";

interface Props {
  session: ScanSessionDetail | null;
  onSelectFinding: (finding: Finding) => void;
}

type AuditRow = {
  finding: Finding;
  decision: ReturnType<typeof buildFindingDecisionSummary>;
  timelineSummary: ReturnType<typeof summarizeAuditTimeline>;
  timelinePreview: ReturnType<typeof buildAuditTimeline>;
};

export function AuditTrailScreen({ session, onSelectFinding }: Props) {
  if (!session) return null;

  const auditRows = [...session.findings]
    .map<AuditRow>((finding) => {
      const timeline = buildAuditTimeline(finding);
      return {
        finding,
        decision: buildFindingDecisionSummary(finding),
        timelineSummary: summarizeAuditTimeline(timeline),
        timelinePreview: timeline.slice(0, 3),
      };
    })
    .sort((left, right) => {
      const riskDelta = right.decision.riskScore - left.decision.riskScore;
      if (riskDelta !== 0) return riskDelta;
      return left.finding.title.localeCompare(right.finding.title);
    });

  const workflow = session.session.workflowSummary;
  const closure = workflow?.workflowClosure;
  const operations = workflow?.operationsExecution;
  const recovery = workflow?.recoveryExecution;
  const runAuditLog = buildRunAuditLog(session);
  const runAuditSummary = summarizeRunAuditLog(runAuditLog);

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
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Audit trail</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{session.session.repo}</h2>
              <p className="mt-2 text-sm leading-6 text-txt-secondary">
                This surface consolidates workflow closure, approval history, policy outcomes, and remediation status into a single trail for the current security run.
              </p>
            </div>
            <span className="shrink-0 whitespace-nowrap rounded-full bg-[#eeeeee] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {auditRows.length} trail item{auditRows.length === 1 ? "" : "s"}
            </span>
          </div>
        </section>

        {(closure || operations || recovery) && (
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {closure ? (
              <AuditCard
                icon={ShieldCheck}
                label="Workflow closure"
                value={closure.closureLabel}
                note={`${closure.closureState} - next ${closure.nextClosureStep}`}
              />
            ) : null}
            {operations ? (
              <AuditCard
                icon={ArrowRight}
                label="Operations execution"
                value={operations.currentHandoff}
                note={`${operations.handoffStatus} - owner ${operations.owningController}`}
              />
            ) : null}
            {recovery ? (
              <AuditCard
                icon={Clock3}
                label="Recovery path"
                value={recovery.selectedPath}
                note={`${recovery.executionLane} - ${recovery.executionState}`}
              />
            ) : null}
          </section>
        )}

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AuditCard
            icon={ShieldCheck}
            label="Run audit log"
            value={`${runAuditSummary.eventCount} event(s)`}
            note={runAuditSummary.topEventLabel}
          />
          <AuditCard
            icon={Clock3}
            label="Critical run events"
            value={`${runAuditSummary.criticalEvents} event(s)`}
            note={`${runAuditSummary.recoveryEvents} recovery and ${runAuditSummary.operationsEvents} operations event(s) active.`}
          />
          <AuditCard
            icon={ArrowRight}
            label="Recovery events"
            value={`${runAuditSummary.recoveryEvents} event(s)`}
            note="Recovery lane activity captured from the workflow summary."
          />
          <AuditCard
            icon={FileSearch}
            label="Closure events"
            value={`${runAuditSummary.closureEvents} event(s)`}
            note="Closure decisions logged from the run-level controls."
          />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <Clock3 size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Run audit log</p>
          </div>
          <div className="space-y-3">
            {runAuditLog.length === 0 ? (
              <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4 text-sm text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                No run audit log has been recorded for this session.
              </div>
            ) : (
              runAuditLog.map((event) => (
                <div
                  key={event.id}
                  className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                  style={{ borderColor: "hsl(var(--border-soft))" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-txt-primary">{event.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                        {event.priority} - {event.eventClass}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <AuditRow label="Event detail" value={event.detail} />
                    <AuditRow label="Context" value={event.context} />
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <FileSearch size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Finding trail</p>
          </div>
          <div className="space-y-3">
            {auditRows.length === 0 ? (
              <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4 text-sm text-txt-secondary" style={{ borderColor: "hsl(var(--border-soft))" }}>
                No findings are available in this session trail yet.
              </div>
            ) : null}
            {auditRows.map(({ finding, decision, timelineSummary, timelinePreview }) => (
              <button
                key={finding.id}
                onClick={() => onSelectFinding(finding)}
                className="w-full rounded-2xl border bg-[#f7f7f7] px-4 py-4 text-left transition-colors hover:bg-card"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-txt-primary">{finding.title}</p>
                    <p className="mt-1 text-xs font-mono text-txt-tertiary">
                      {finding.file}:{finding.line}{finding.lineEnd > finding.line ? `-${finding.lineEnd}` : ""}
                    </p>
                  </div>
                  <span className="rounded-full bg-card px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
                    {getRemediationStatusLabel(finding.remediationStatus)}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <AuditRow label="Risk / triage" value={`${decision.riskScore}/100 - ${decision.triageBand}`} />
                  <AuditRow label="Policy" value={`${decision.policyOutcome} - ${decision.policySummary.label}`} />
                  <AuditRow label="Approval" value={`${finding.approvalStatus} - ${decision.approvalAuditSummary.label}`} />
                  <AuditRow label="Next control" value={decision.policySummary.nextControl} />
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <AuditRow label="Latest audit signal" value={timelineSummary.latestEventDetail} />
                  <AuditRow
                    label="Timeline coverage"
                    value={`${timelineSummary.totalEvents} events - ${timelineSummary.approvalEvents} approval / ${timelineSummary.remediationEvents} remediation / ${timelineSummary.auditEvents} audit`}
                  />
                </div>

                {timelinePreview.length > 0 ? (
                  <div className="mt-3 rounded-2xl border bg-card px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
                    <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">Recent timeline</p>
                    <div className="mt-3 space-y-2">
                      {timelinePreview.map((event) => (
                        <div key={event.id} className="rounded-xl bg-[#f7f7f7] px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-medium text-txt-primary">{event.label}</span>
                            <span className="text-[11px] uppercase tracking-[0.14em] text-txt-tertiary">
                              {event.timestamp ? formatTimestamp(event.timestamp) : event.source}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-txt-secondary">{event.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </section>

      </div>
    </motion.div>
  );
}

function AuditCard({
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

function AuditRow({
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

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: "UTC",
  });
}
