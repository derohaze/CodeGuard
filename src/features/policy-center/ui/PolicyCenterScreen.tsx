import { motion } from "framer-motion";
import { ArrowRight, ShieldAlert, ShieldCheck, ShieldX } from "lucide-react";
import type { Finding } from "@/entities/finding/model/types";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { getRemediationStatusLabel } from "@/entities/finding/lib/remediation-status";
import { buildPreMergeGuidance, summarizePreMergeGuidance } from "../lib/pre-merge-guidance";
import { buildPreventionLedger, summarizePreventionLedger } from "../lib/prevention-ledger";

interface Props {
  finding: Finding | null;
  onBack: () => void;
  onSuggestFix: () => void;
}

export function PolicyCenterScreen({ finding, onBack, onSuggestFix }: Props) {
  if (!finding) return null;

  const decision = buildFindingDecisionSummary(finding);
  const policy = decision.policySummary;
  const approvalAudit = decision.approvalAuditSummary;
  const preMergeGuidance = buildPreMergeGuidance(finding);
  const guidanceSummary = summarizePreMergeGuidance(preMergeGuidance);
  const preventionLedger = buildPreventionLedger({ finding, decision, preMergeGuidance });
  const preventionSummary = summarizePreventionLedger(preventionLedger);

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
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Policy center</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-txt-primary">{finding.title}</h2>
              <p className="mt-2 text-sm font-mono text-txt-tertiary">
                {finding.file}:{finding.line}{finding.lineEnd > finding.line ? `-${finding.lineEnd}` : ""}
              </p>
            </div>
            <span className="rounded-full bg-[#eeeeee] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-txt-secondary">
              {getRemediationStatusLabel(finding.remediationStatus)}
            </span>
          </div>
          <p className="mt-4 text-sm leading-6 text-txt-secondary">
            This surface explains the current policy posture, the allowed automation path, the required human control, and the next policy gate before remediation can advance.
          </p>
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PolicyCard
            icon={policy.posture === "block" ? ShieldX : policy.posture === "review" ? ShieldAlert : ShieldCheck}
            label={`Policy summary - ${policy.label}`}
            value={policy.summary}
            tone={policy.posture}
          />
          <PolicyCard
            icon={ShieldCheck}
            label="Auto path"
            value={policy.autoPathState}
            tone={policy.autoPathState === "forbidden" ? "block" : policy.autoPathState === "gated" ? "review" : "allow"}
          />
          <PolicyCard
            icon={ShieldAlert}
            label="Human path"
            value={policy.humanPathState}
            tone={policy.humanPathState === "regenerate-required" ? "block" : policy.humanPathState === "standard-review" ? "allow" : "review"}
          />
          <PolicyCard
            icon={ArrowRight}
            label="Next control"
            value={policy.nextControl}
            tone={policy.nextControl === "generate-a-stronger-patch" ? "block" : policy.nextControl === "proceed-with-local-apply" ? "allow" : "review"}
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PolicyCard
            icon={ShieldAlert}
            label="Pre-merge guidance"
            value={`${guidanceSummary.guidanceCount} guidance item(s)`}
            tone={guidanceSummary.criticalGuidance > 0 ? "block" : guidanceSummary.reviewGates > 0 || guidanceSummary.verificationGates > 0 ? "review" : "allow"}
          />
          <PolicyCard
            icon={ShieldX}
            label="Merge blockers"
            value={`${guidanceSummary.mergeBlockers} blocker(s)`}
            tone={guidanceSummary.mergeBlockers > 0 ? "block" : "allow"}
          />
          <PolicyCard
            icon={ShieldAlert}
            label="Review gates"
            value={`${guidanceSummary.reviewGates + guidanceSummary.verificationGates} gate(s)`}
            tone={guidanceSummary.reviewGates + guidanceSummary.verificationGates > 0 ? "review" : "allow"}
          />
          <PolicyCard
            icon={ArrowRight}
            label="Top guidance"
            value={guidanceSummary.topGuidanceLabel}
            tone={guidanceSummary.criticalGuidance > 0 ? "block" : "review"}
          />
        </section>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PolicyCard
            icon={ShieldAlert}
            label="Prevention ledger"
            value={`${preventionSummary.itemCount} item(s)`}
            tone={preventionSummary.criticalItems > 0 ? "block" : preventionSummary.verificationItems > 0 || preventionSummary.approvalItems > 0 ? "review" : "allow"}
          />
          <PolicyCard
            icon={ShieldAlert}
            label="Critical prevention"
            value={`${preventionSummary.criticalItems} item(s)`}
            tone={preventionSummary.criticalItems > 0 ? "block" : "allow"}
          />
          <PolicyCard
            icon={ShieldCheck}
            label="Approval guards"
            value={`${preventionSummary.approvalItems} item(s)`}
            tone={preventionSummary.approvalItems > 0 ? "review" : "allow"}
          />
          <PolicyCard
            icon={ArrowRight}
            label="Verification guards"
            value={`${preventionSummary.verificationItems} item(s)`}
            tone={preventionSummary.verificationItems > 0 ? "review" : "allow"}
          />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-status-high" />
            <p className="text-sm font-semibold text-txt-primary">Policy controls</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <PolicyRow label="Policy outcome" value={decision.policyOutcome} tone={decision.policyOutcome === "blocked-by-policy" ? "danger" : "default"} />
            <PolicyRow label="Policy reason" value={decision.policyReason} tone={decision.policyOutcome === "blocked-by-policy" ? "danger" : "default"} />
            <PolicyRow label="Apply readiness" value={decision.applyReadiness} tone={decision.applyReadiness === "blocked-before-apply" ? "danger" : "default"} />
            <PolicyRow label="Escalation" value={decision.escalationState} tone={decision.escalationState === "none" ? "default" : "warning"} />
            <PolicyRow label="Approval path" value={decision.approvalPath} tone="warning" />
            <PolicyRow label="Stop state" value={decision.stopState} tone={decision.stopState === "stop-and-regenerate" ? "danger" : decision.stopState === "hold-for-review" ? "warning" : "default"} />
            <PolicyRow
              label={`Approval audit - ${approvalAudit.label}`}
              value={approvalAudit.summary}
              tone={approvalAudit.status === "rejected" ? "danger" : approvalAudit.status === "escalated" ? "warning" : "default"}
            />
            <PolicyRow label="Approval note" value={approvalAudit.note} tone={approvalAudit.status === "rejected" ? "danger" : "default"} />
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Decision bridge</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <PolicyRow label="Triage band" value={decision.triageBand} />
            <PolicyRow label={`Risk score ${decision.riskScore}/100`} value={decision.riskLabel} />
            <PolicyRow label="Residual risk" value={decision.residualRiskState} />
          </div>
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ArrowRight size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Pre-merge guidance</p>
          </div>
          <div className="space-y-3">
            {preMergeGuidance.map((item) => (
              <div key={`${item.guidanceClass}-${item.label}`} className="rounded-2xl border bg-[#f7f7f7] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                      {item.priority} - {item.guidanceClass}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <PolicyRow label="Guidance" value={item.guidance} tone={item.priority === "critical" ? "danger" : item.priority === "high" ? "warning" : "default"} />
                  <PolicyRow label="Merge condition" value={item.mergeCondition} tone={item.priority === "critical" ? "danger" : "default"} />
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
            <ShieldAlert size={16} className="text-txt-secondary" />
            <p className="text-sm font-semibold text-txt-primary">Prevention ledger</p>
          </div>
          <div className="space-y-3">
            {preventionLedger.map((item) => (
              <div
                key={`${item.ledgerClass}-${item.label}`}
                className="rounded-2xl border bg-[#f7f7f7] px-4 py-4"
                style={{ borderColor: "hsl(var(--border-soft))" }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-txt-primary">{item.label}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-txt-tertiary">
                      {item.priority} - {item.ledgerClass}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <PolicyRow label="Evidence" value={item.evidence} tone={item.priority === "critical" ? "danger" : "default"} />
                  <PolicyRow label="Next prevention action" value={item.nextAction} tone={item.priority === "critical" ? "danger" : "default"} />
                </div>
              </div>
            ))}
            {preventionLedger.length === 0 && (
              <p className="text-sm leading-6 text-txt-secondary">
                No prevention ledger entries are active for this finding.
              </p>
            )}
          </div>
        </section>

        <div className="flex items-center justify-end gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          <button
            onClick={onBack}
            className="rounded-xl border bg-card px-5 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Back
          </button>
          <button
            onClick={onSuggestFix}
            className="rounded-xl bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
          >
            Suggest fix
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function PolicyCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ size?: string | number; className?: string }>;
  label: string;
  value: string;
  tone: "allow" | "review" | "block";
}) {
  return (
    <div
      className={`rounded-2xl border px-4 py-4 ${tone === "block" ? "bg-[#fff7f5]" : tone === "review" ? "bg-[#f7f7f7]" : "bg-card"} shadow-card`}
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} className={tone === "block" ? "text-status-critical" : tone === "review" ? "text-status-high" : "text-txt-secondary"} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-txt-primary">{value}</p>
    </div>
  );
}

function PolicyRow({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warning" | "danger";
}) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className={`mt-2 text-sm leading-6 ${tone === "danger" ? "text-status-critical" : tone === "warning" ? "text-status-high" : "text-txt-secondary"}`}>{value}</p>
    </div>
  );
}
