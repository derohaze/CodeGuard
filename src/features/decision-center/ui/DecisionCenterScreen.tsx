import { motion } from "framer-motion";
import { Gauge, ShieldAlert, ShieldCheck, ShieldX, Zap } from "lucide-react";
import type { Finding } from "@/entities/finding/model/types";
import { buildFindingDecisionSummary } from "@/entities/finding/lib/decision-center";
import { getRemediationStatusLabel } from "@/entities/finding/lib/remediation-status";

interface Props {
  finding: Finding | null;
  onBack: () => void;
  onSuggestFix: () => void;
  onOpenPolicyCenter: () => void;
}

export function DecisionCenterScreen({ finding, onBack, onSuggestFix, onOpenPolicyCenter }: Props) {
  if (!finding) return null;

  const decision = buildFindingDecisionSummary(finding);
  const approvalAudit = decision.approvalAuditSummary;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hide-scrollbar flex-1 overflow-y-auto dotted-bg px-8 py-8"
    >
      <div className="mx-auto max-w-3xl space-y-4">
        <section
          className="rounded-2xl border bg-card px-5 py-5 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-txt-tertiary">Decision center</p>
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
            This screen explains why Aegix recommends action on this finding, how much decision pressure remains, and what approval path should be followed next.
          </p>
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <DecisionCard icon={ShieldCheck} label={decision.validationLabel} value={decision.validationNote} />
          <DecisionCard
            icon={Gauge}
            label={`Risk score ${decision.riskScore}/100`}
            value={decision.riskLabel}
            tone={decision.riskScore >= 85 ? "danger" : "warning"}
          />
          <DecisionCard icon={ShieldAlert} label="Triage band" value={decision.triageBand} tone="warning" />
          <DecisionCard icon={ShieldX} label="Execution disposition" value={decision.executionDisposition} tone="danger" />
          <DecisionCard icon={ShieldCheck} label="Approval state" value={decision.approvalState} />
          <DecisionCard
            icon={ShieldX}
            label="Policy outcome"
            value={decision.policyOutcome}
            tone={decision.policyOutcome === "blocked-by-policy" ? "danger" : decision.policyOutcome === "review-required" ? "warning" : "default"}
          />
          <DecisionCard
            icon={ShieldX}
            label="Stop state"
            value={decision.stopState}
            tone={decision.stopState === "stop-and-regenerate" ? "danger" : decision.stopState === "hold-for-review" ? "warning" : "default"}
          />
          <DecisionCard
            icon={ShieldAlert}
            label="Apply readiness"
            value={decision.applyReadiness}
            tone={decision.applyReadiness === "blocked-before-apply" ? "danger" : decision.applyReadiness === "approval-required-before-apply" ? "warning" : "default"}
          />
          <DecisionCard
            icon={ShieldAlert}
            label="Escalation"
            value={decision.escalationState}
            tone={decision.escalationState === "already-escalated" || decision.escalationState === "required" ? "warning" : "default"}
          />
          <DecisionCard icon={Gauge} label="Residual risk" value={decision.residualRiskState} />
          <DecisionCard icon={Zap} label="Recommended action" value={decision.recommendedAction} tone="warning" />
          <DecisionCard icon={ShieldX} label="Approval path" value={decision.approvalPath} tone="danger" />
        </section>

        <section
          className="rounded-2xl border bg-card px-5 py-4 shadow-card"
          style={{ borderColor: "hsl(var(--border-soft))" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <ShieldAlert size={16} className="text-status-high" />
            <p className="text-sm font-semibold text-txt-primary">Why Aegix recommends this path</p>
          </div>
          <div className="space-y-3">
            <DecisionRow label="Fix strategy" value={decision.fixRecommendation} />
            <DecisionRow
              label="Policy reason"
              value={decision.policyReason}
              tone={decision.policyOutcome === "blocked-by-policy" ? "danger" : "default"}
            />
            <DecisionRow
              label={`Policy summary - ${decision.policySummary.label}`}
              value={decision.policySummary.summary}
              tone={decision.policySummary.posture === "block" ? "danger" : "default"}
            />
            <DecisionRow
              label="Policy controls"
              value={`Auto path: ${decision.policySummary.autoPathState} Â· Human path: ${decision.policySummary.humanPathState} Â· Next control: ${decision.policySummary.nextControl}`}
              tone={decision.policySummary.posture === "block" ? "danger" : "default"}
            />
            <DecisionRow
              label={`Approval audit - ${approvalAudit.label}`}
              value={approvalAudit.summary}
              tone={approvalAudit.status === "rejected" ? "danger" : "default"}
            />
            <DecisionRow
              label="Approval note"
              value={approvalAudit.note}
              tone={approvalAudit.status === "rejected" ? "danger" : "default"}
            />
            {decision.riskFactors.map((factor, index) => (
              <DecisionRow
                key={`${factor}-${index}`}
                label={`Factor ${index + 1}`}
                value={factor}
                tone={index === decision.riskFactors.length - 1 ? "danger" : "default"}
              />
            ))}
          </div>
        </section>

        <div className="flex items-center justify-end gap-3 border-t pt-4" style={{ borderColor: "hsl(var(--border-primary))" }}>
          <button
            onClick={onOpenPolicyCenter}
            className="rounded-xl border bg-card px-5 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Open policy center
          </button>
          <button
            onClick={onBack}
            className="rounded-xl border bg-card px-5 py-2 text-sm font-medium text-txt-primary"
            style={{ borderColor: "hsl(var(--border-primary))" }}
          >
            Back to finding
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

function DecisionCard({
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
    <div
      className={`rounded-2xl border px-4 py-4 ${tone === "danger" ? "bg-[#fff7f5]" : tone === "warning" ? "bg-[#f7f7f7]" : "bg-card"} shadow-card`}
      style={{ borderColor: "hsl(var(--border-soft))" }}
    >
      <div className="flex items-center gap-2 text-txt-secondary">
        <Icon size={15} className={tone === "danger" ? "text-status-critical" : tone === "warning" ? "text-status-high" : "text-txt-secondary"} />
        <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-txt-primary">{value}</p>
    </div>
  );
}

function DecisionRow({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "danger";
}) {
  return (
    <div className="rounded-2xl border bg-[#f7f7f7] px-4 py-4" style={{ borderColor: "hsl(var(--border-soft))" }}>
      <p className="text-[11px] uppercase tracking-[0.16em] text-txt-tertiary">{label}</p>
      <p className={`mt-2 text-sm leading-6 ${tone === "danger" ? "text-status-critical" : "text-txt-secondary"}`}>{value}</p>
    </div>
  );
}
